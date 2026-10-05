# Asistente RAG Agéntico Empresarial

Solución a la prueba técnica. Agente RAG empresarial sobre AWS.

* Decisiones técnicas (resumen): [docs/decisiones_short.md](docs/decisiones_short.md)
* Decisiones técnicas (completas): [docs/decisiones_full.md](docs/decisiones_full.md)
* Documentación de la API: [docs/api.md](docs/api.md)
* Evaluación de calidad: [docs/evaluacion.md](docs/evaluacion.md)
* Mejoras futuras: [docs/mejoras-futuras.md](docs/mejoras-futuras.md)
* Riesgos y consideraciones para producción: [docs/riesgos-produccion.md](docs/riesgos-produccion.md)

> **Aviso:** la redacción y generación de la documentación fueron asistidas por IA Generativa, y yo revisé todo el contenido y me encagué 100% del diseño de la solución.

## Arquitectura

![Diagrama de arquitectura](docs/diagrama_arquitectura.svg)

Toda la solución se despliega en AWS (`us-east-1`). Los números corresponden a los marcadores del diagrama.

### Frontend y autenticación

1. **Frontend.** El usuario realiza todas las operaciones desde el frontend, construido en React con Cloudscape y servido por una distribución de Amazon CloudFront y su bucket de S3. La página de inicio de sesión es el *managed login* de Amazon Cognito.
2. **Identidad.** La autenticación y la identidad se gestionan con un *user pool* de Cognito. Un Lambda *Pre SignUp* restringe el registro a cuentas aprobadas o a dominios de correo corporativos.
3. **API.** El frontend se comunica con el backend mediante una API REST en Amazon API Gateway, protegida con el mismo *user pool* de Cognito. La única excepción es la carga de documentos para la base de conocimiento, que va directo a S3 mediante URLs prefirmadas.

### Ingesta documental

4. **URL prefirmada.** El frontend obtiene la URL prefirmada desde un endpoint dedicado.
5. **Carga.** El documento se sube al bucket de documentos de S3 usando esa URL.
6. **Sincronización.** La carga genera un evento que dispara un Lambda para sincronizar la base de conocimiento con el nuevo documento. Si ya hay una sincronización en curso, se omite. Como respaldo ante sincronizaciones fallidas, el frontend ofrece un botón y un endpoint de sincronización manual.
7. **Sincronización incremental.** La sincronización es incremental y los documentos se leen únicamente del bucket de documentos (detalles de la base de conocimiento en el paso 14).

### Conversación con el agente

8. **Conversaciones.** El contexto de cada conversación lo administran AgentCore Runtime y AgentCore Memory por sessionId. Un conjunto de endpoints y una tabla de DynamoDB registran los turnos para que cada usuario consulte su historial.
9. **Converse.** La conversación con el agente ocurre en el endpoint de conversación.
10. **Swarm de agentes.** Se usa Strands Agents con el patrón *swarm*, desplegado en Amazon Bedrock AgentCore Runtime. El agente conversacional dialoga con el usuario, gestiona las solicitudes y recupera información de la base de conocimiento. El agente de modernización y el agente recomendador de servicios cloud son agentes especializados para esos casos de uso.
11. **Modelo.** Todos los agentes usan Amazon Nova 2 Lite, por costo: es por mucho el modelo más barato disponible en Amazon Bedrock. El modelo juez de la evaluación es el mismo.
12. **Guardrails.** Amazon Bedrock Guardrails detecta y bloquea ataques de *prompt injection*. Cuando bloquea uno, el usuario recibe un mensaje indicando que la respuesta fue bloqueada por los guardrails.
13. **Gateway de herramientas.** Todas las herramientas se exponen a los agentes mediante un gateway MCP de AgentCore.
14. **Recuperación (RAG).** La herramienta de recuperación consulta la base de conocimiento e incluye las fuentes para referenciarlas en la respuesta. La base de conocimiento es una Amazon Bedrock Knowledge Base administrada: el vector store, los embeddings, el *chunking*, el *parsing*, la ingesta y el almacenamiento los gestiona el servicio.
15. **Búsqueda web.** Los agentes especializados tienen la herramienta de búsqueda web de AgentCore, con una lista de dominios permitidos limitada a la documentación de AWS y Azure, para evitar desviaciones. El agente conversacional no tiene búsqueda web: responde solo con la información de la base de conocimiento.
16. **Herramientas de solicitudes.** Herramientas basadas en Lambda gestionan las solicitudes (tickets) del sistema. Para cada solicitud el agente puede crearla, consultarla o listarlas, actualizarla con un resumen, con un nivel de prioridad, con un nivel de esfuerzo estimado o con un nuevo estado. La prioridad y el esfuerzo los decide el LLM, con tres niveles posibles: bajo, medio y alto. El agente no puede eliminar solicitudes.

### Evaluación agéntica

17. **Ejecución.** La evaluación agéntica se lanza desde el frontend y corre como una tarea de AWS Fargate orquestada por AWS Step Functions, con Strands Evals y AgentCore Evaluations. Por costo, el modelo juez es el mismo de los agentes, así que puede haber sesgo de autoevaluación (ADR-032). Las pruebas se describen en [docs/evaluacion.md](docs/evaluacion.md). Ejecuta todas las evaluaciones requeridas: precisión, *groundedness*, respuesta adecuada cuando no hay información suficiente y *prompt injection*.
18. **Resultados.** El progreso y los resultados se registran en una tabla de DynamoDB de evaluaciones y se visualizan en el frontend.
19. **Consulta.** Un endpoint de la API permite leer los resultados de evaluaciones anteriores.

### Despliegue

20. **CDK.** La solución se despliega con AWS CDK en Python, en varios stacks separados por dominio. Las buenas prácticas de seguridad se validan con los paquetes de reglas de cdk-nag para *serverless* y *AWS Solutions*.
21. **CloudFormation.** CDK despliega todos los recursos a través de AWS CloudFormation.
22. **Assets y configuración.** Los documentos de ejemplo para la base de conocimiento y otros assets se despliegan con el construct `BucketDeployment` de S3. Las 10 solicitudes de ejemplo, definidas en un archivo JSON, se precargan en DynamoDB con un *custom resource*; el frontend solo accede a las solicitudes a través del agente. Los valores de configuración de runtime se despliegan como parámetros de SSM Parameter Store.
23. **Trazabilidad del despliegue.** El despliegue queda trazado en Amazon CloudWatch y AWS CloudTrail.

### Observabilidad y seguridad

24. **Observabilidad de agentes.** Los logs y la telemetría de los agentes en AgentCore Runtime se envían a CloudWatch, estructurados con el soporte de OpenTelemetry de AgentCore.
25. **Logging.** Todo componente que registra logs lo hace en CloudWatch, y los logs se pueden consultar desde el frontend. El registro de invocaciones de modelos de Bedrock se envía a CloudWatch (3 meses de retención) y a un bucket de S3 que se conserva aunque se elimine la solución.
26. **Visor de logs.** El frontend funciona como un visor básico de CloudWatch: se elige un *log group* y se muestra su contenido como texto plano. Solo se listan los *log groups* que tienen las etiquetas de la aplicación.
27. **Secretos e IAM.** Los valores sensibles, como los correos y dominios permitidos para el registro, se guardan en AWS Secrets Manager. Cada recurso tiene su propio rol de IAM con el principio de mínimo privilegio.

## Instalación y despliegue

### Requisitos

* Una cuenta de AWS con acceso en `us-east-1` a Amazon Nova 2 Lite en Amazon Bedrock, y la cuenta y región con *bootstrap* de CDK (`cdk bootstrap`).
* Credenciales de AWS configuradas en la terminal (por ejemplo, `aws login` o un perfil SSO).
* Python 3.13 o superior, [uv](https://docs.astral.sh/uv/), Node.js 22 o superior, [pnpm](https://pnpm.io/) y AWS CDK CLI (`npm install -g aws-cdk`).
* Docker con Buildx, en ejecución: CDK construye las imágenes ARM64 del runtime de agentes y de la tarea de evaluación.

### Configuración

Toda la configuración está en `config.json`, que no se versiona. Copia el ejemplo y completa los valores:

```bash
cp config.json.example config.json
```

| Clave | Descripción |
|---|---|
| `project_name` | Prefijo de los recursos y de los parámetros de SSM. |
| `account`, `region` | Cuenta y región de despliegue (`us-east-1`, ADR-004). |
| `tags` | Etiquetas de todos los recursos. El visor de logs solo muestra los *log groups* que las tienen (ADR-037). |
| `nag` | Paquetes de reglas de cdk-nag que se ejecutan en `cdk synth`. |
| `auth.domain_prefix` | Prefijo del dominio del *managed login* de Cognito; debe ser único en la región. |
| `auth.allowed_emails`, `auth.allowed_domains` | Correos y dominios que pueden registrarse; se guardan en Secrets Manager (ADR-007, ADR-027). Se puede usar cualquiera de las dos listas o ambas: por ejemplo, solo tu correo y ninguna lista de dominios. |
| `models.agent_model_id`, `models.judge_model_id` | Modelo de los agentes y modelo juez (ADR-016, ADR-032). Preferencia: perfil de inferencia global (`global.`), luego geográfico (`us.`) y, si el modelo no tiene perfiles, el ID del modelo. |
| `web_search.allowed_domains` | Dominios permitidos para la búsqueda web de los agentes especializados (ADR-023). |
| `api`, `logs` | Límite de tasa de la API y retención de los logs en días. |

### Despliegue

```bash
uv venv .venv
uv pip install -r requirements.txt
.venv\Scripts\activate      # en Linux o macOS: source .venv/bin/activate
cdk deploy --all
```

`cdk deploy` compila el frontend con pnpm, construye las imágenes de los agentes y despliega los 8 stacks. Al terminar, la salida `SiteUrl` del stack `*-WebHosting` es la URL del frontend. Los documentos de ejemplo se sincronizan en la base de conocimiento automáticamente y las 10 solicitudes de ejemplo quedan precargadas.

Para eliminar todo: `cdk destroy --all`. El registro de invocaciones de modelos de Bedrock es una configuración de la cuenta y región, y se desactiva al eliminar el stack de observabilidad.

### Desarrollo local

```bash
uv pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest      # pruebas de CDK, Lambdas y agentes
.venv/Scripts/ruff check .          # lint de Python
cd frontend && pnpm install && pnpm test && pnpm lint && pnpm build
```

Para ejecutar el frontend contra un despliegue existente, crea `frontend/public/config.json` a partir de `config.json.example` con las salidas de los stacks y ejecuta `pnpm dev` (`http://localhost:5173`, ya registrado como URL de retorno en Cognito).

### Estructura del repositorio

| Ruta | Contenido |
|---|---|
| `app.py`, `pruebatecnica/` | App de CDK: un stack por dominio (`stacks/`) y constructs reutilizables (`constructs/`). |
| `backend/` | Lambdas de Powertools: API (`api/`), herramientas de solicitudes (`tools/`) y triggers (`triggers/`). |
| `agents/` | Swarm de Strands para AgentCore Runtime (`swarm_agent/`) y evaluación agéntica (`evaluation/`). |
| `frontend/` | Frontend en React con Cloudscape. |
| `assets/` | Documentos de ejemplo de la base de conocimiento y solicitudes de ejemplo. |
| `DISCREPANCIES.md` | Supuestos tomados durante la implementación, para revisar. |
