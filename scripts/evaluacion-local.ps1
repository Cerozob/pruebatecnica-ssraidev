<#
.SYNOPSIS
    Ejecuta la tarea de evaluación agéntica en Docker local, contra los recursos ya desplegados.

.DESCRIPTION
    Usa la misma imagen (agents/Dockerfile.evaluation) y el mismo runner que la tarea de Fargate, con las
    credenciales de AWS de la terminal en lugar del rol de la tarea. No pasa por Step Functions: registra la
    evaluación en la tabla de evaluaciones, ejecuta el contenedor y, si falla, marca la evaluación como FAILED.
    Los resultados quedan en la misma tabla de DynamoDB y se ven en el frontend.

    Requiere los stacks *-Agents y *-Evaluation desplegados, Docker en ejecución y credenciales de AWS válidas.
    Cuesta lo mismo que una evaluación lanzada desde el frontend (modelo de los agentes, juez y AgentCore).

.PARAMETER Perfil
    Perfil de la CLI de AWS. Por defecto, las credenciales activas de la terminal.

.PARAMETER SoloConstruir
    Construye la imagen y termina, sin tocar AWS.

.EXAMPLE
    .\scripts\evaluacion-local.ps1
    .\scripts\evaluacion-local.ps1 -Perfil default
    .\scripts\evaluacion-local.ps1 -SoloConstruir
#>
param(
    [string]$Perfil,
    [switch]$SoloConstruir
)

# Sin $ErrorActionPreference = "Stop": en PowerShell 5.1 convierte la salida de error de docker y aws en
# excepciones aunque terminen bien. Cada llamada nativa revisa $LASTEXITCODE.
$raiz = Split-Path -Parent $PSScriptRoot
$config = Get-Content (Join-Path $raiz "config.json") -Raw -Encoding UTF8 -ErrorAction Stop | ConvertFrom-Json
$region = $config.region
$proyecto = $config.project_name
$imagen = "$proyecto-evaluacion:local"

# PowerShell 5.1 pierde las comillas de los JSON que se pasan a programas nativos: se pasan por archivo.
function ConvertTo-AwsFile($valor) {
    $archivo = New-TemporaryFile
    [IO.File]::WriteAllText($archivo, ($valor | ConvertTo-Json -Compress -Depth 5))
    return "file://$archivo"
}

function Invoke-Aws {
    $argumentos = @($args) + @("--region", $region, "--output", "text")
    if ($Perfil) { $argumentos += @("--profile", $Perfil) }
    $salida = & aws @argumentos
    if ($LASTEXITCODE -ne 0) { throw "Falló: aws $($args -join ' ')" }
    return $salida
}

# Imagen nativa de la máquina local: en Fargate es ARM64, pero el código es el mismo.
docker build -f (Join-Path $raiz "agents/Dockerfile.evaluation") -t $imagen (Join-Path $raiz "agents")
if ($LASTEXITCODE -ne 0) { throw "Falló docker build" }
if ($SoloConstruir) { return }

# Mismo nombre de stack que pruebatecnica/app_builder.py.
$prefijo = (($proyecto -split "-") | ForEach-Object { $_.Substring(0, 1).ToUpper() + $_.Substring(1) }) -join ""
$tabla = Invoke-Aws cloudformation describe-stack-resources --stack-name "$prefijo-Evaluation" `
    --query "StackResources[?ResourceType=='AWS::DynamoDB::GlobalTable'].PhysicalResourceId | [0]"
if (-not $tabla -or $tabla -eq "None") { throw "No se encontró la tabla de evaluaciones en el stack $prefijo-Evaluation" }

# Credenciales temporales de la terminal (SSO o aws login). Se pasan al contenedor como variables de
# entorno heredadas, así no quedan en la línea de comandos ni en la imagen.
$exportar = @("configure", "export-credentials", "--format", "env-no-export")
if ($Perfil) { $exportar += @("--profile", $Perfil) }
$credenciales = & aws @exportar
if ($LASTEXITCODE -ne 0) { throw "No hay credenciales de AWS válidas: ejecuta 'aws login' o 'aws sso login'" }
$nombresCredenciales = @()
foreach ($linea in $credenciales) {
    $nombre, $valor = $linea -split "=", 2
    if ($nombre -and $valor) {
        Set-Item -Path "Env:$nombre" -Value $valor
        $nombresCredenciales += $nombre
    }
}

# Mismas variables que el contenedor de la tarea de Fargate (stacks/evaluation_stack.py y agents_stack.py).
$ssm = "/$proyecto"
$entorno = [ordered]@{
    AWS_REGION                       = $region
    EVALUATIONS_TABLE_NAME           = $tabla
    MODEL_ID_PARAM                   = "$ssm/agents/model-id"
    GUARDRAIL_ID_PARAM               = "$ssm/agents/guardrail-id"
    GUARDRAIL_VERSION_PARAM          = "$ssm/agents/guardrail-version"
    GATEWAY_URL_PARAM                = "$ssm/agents/gateway-url"
    BLOCKED_MESSAGE_PARAM            = "$ssm/agents/blocked-message"
    JUDGE_MODEL_ID_PARAM             = "$ssm/evaluation/judge-model-id"
    GROUNDEDNESS_EVALUATOR_ARN_PARAM = "$ssm/evaluation/groundedness-evaluator-arn"
    KNOWLEDGE_TARGET                 = "conocimiento"
    WEB_SEARCH_TARGET                = "busqueda-web"
    REQUESTS_TARGET_PREFIX           = "solicitudes"
}

# Mismo elemento inicial que crea POST /evaluations, para que la evaluación aparezca en el frontend.
$evaluacion = "local-" + (Get-Date).ToUniversalTime().ToString("yyyyMMddHHmmss")
$creada = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$entorno.EVALUATION_ID = $evaluacion
$elemento = @{
    evaluationId = @{ S = $evaluacion }
    status       = @{ S = "RUNNING" }
    createdAt    = @{ S = $creada }
}
Invoke-Aws dynamodb put-item --table-name $tabla --item (ConvertTo-AwsFile $elemento) | Out-Null

$argumentos = @("run", "--rm")
foreach ($nombre in $entorno.Keys) { $argumentos += @("-e", "$nombre=$($entorno[$nombre])") }
foreach ($nombre in $nombresCredenciales) { $argumentos += @("-e", $nombre) }
$argumentos += $imagen

Write-Host "Evaluación $evaluacion en la tabla $tabla"
& docker @argumentos
$codigo = $LASTEXITCODE

if ($codigo -ne 0) {
    Invoke-Aws dynamodb update-item --table-name $tabla `
        --key (ConvertTo-AwsFile @{ evaluationId = @{ S = $evaluacion } }) `
        --update-expression "SET #status = :status, #error = :error" `
        --expression-attribute-names (ConvertTo-AwsFile @{ "#status" = "status"; "#error" = "error" }) `
        --expression-attribute-values (ConvertTo-AwsFile @{
            ":status" = @{ S = "FAILED" }
            ":error"  = @{ S = "El contenedor local terminó con código $codigo" }
        }) | Out-Null
    throw "La evaluación $evaluacion falló (código $codigo)"
}
Write-Host "Evaluación $evaluacion completada: los resultados se ven en el frontend (Evaluaciones)."
