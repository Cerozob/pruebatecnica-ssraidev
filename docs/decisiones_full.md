# Documento de Decisiones de Arquitectura

* Autor: **Camilo Rozo**

Cada decisión sigue el formato ADR: contexto, decisión, consecuencias y cumplimiento. Los números de paso hacen referencia al [diagrama de arquitectura](../README.md#arquitectura). Las mejoras que quedaron fuera están en [mejoras-futuras.md](mejoras-futuras.md).

## Tabla de Contenidos

1. [ADR-001: AWS como plataforma](#adr-001-aws-como-plataforma)
2. [ADR-002: Cómputo serverless con escalado a cero](#adr-002-cómputo-serverless-con-escalado-a-cero)
3. [ADR-003: API con Lambdas de Powertools detrás de API Gateway](#adr-003-api-con-lambdas-de-powertools-detrás-de-api-gateway)
4. [ADR-004: Región us-east-1](#adr-004-región-us-east-1)
5. [ADR-005: Frontend web en React](#adr-005-frontend-web-en-react)
6. [ADR-006: Inicio de sesión administrado de Cognito](#adr-006-inicio-de-sesión-administrado-de-cognito)
7. [ADR-007: Registro restringido con un Lambda Pre SignUp](#adr-007-registro-restringido-con-un-lambda-pre-signup)
8. [ADR-008: API REST de API Gateway en lugar de HTTP API](#adr-008-api-rest-de-api-gateway-en-lugar-de-http-api)
9. [ADR-009: Carga de documentos directa a S3 con URLs prefirmadas](#adr-009-carga-de-documentos-directa-a-s3-con-urls-prefirmadas)
10. [ADR-010: Sincronización de la base de conocimiento por eventos](#adr-010-sincronización-de-la-base-de-conocimiento-por-eventos)
11. [ADR-011: Base de conocimiento administrada de Bedrock con configuración por defecto](#adr-011-base-de-conocimiento-administrada-de-bedrock-con-configuración-por-defecto)
12. [ADR-012: Strands Agents como framework de agentes](#adr-012-strands-agents-como-framework-de-agentes)
13. [ADR-013: Patrón *swarm* para la colaboración entre agentes](#adr-013-patrón-swarm-para-la-colaboración-entre-agentes)
14. [ADR-014: Tres agentes: conversacional, de modernización y recomendador de servicios cloud](#adr-014-tres-agentes-conversacional-de-modernización-y-recomendador-de-servicios-cloud)
15. [ADR-015: Amazon Bedrock AgentCore Runtime para ejecutar los agentes](#adr-015-amazon-bedrock-agentcore-runtime-para-ejecutar-los-agentes)
16. [ADR-016: Amazon Nova 2 Lite como modelo de lenguaje](#adr-016-amazon-nova-2-lite-como-modelo-de-lenguaje)
17. [ADR-017: Contexto de la conversación en AgentCore e historial en DynamoDB](#adr-017-contexto-de-la-conversación-en-agentcore-e-historial-en-dynamodb)
18. [ADR-018: Respuestas síncronas](#adr-018-respuestas-síncronas)
19. [ADR-019: Herramientas expuestas por AgentCore Gateway (MCP)](#adr-019-herramientas-expuestas-por-agentcore-gateway-mcp)
20. [ADR-020: Herramientas de solicitudes implementadas en Lambda](#adr-020-herramientas-de-solicitudes-implementadas-en-lambda)
21. [ADR-021: Sin operación de eliminación de solicitudes](#adr-021-sin-operación-de-eliminación-de-solicitudes)
22. [ADR-022: Prioridad y esfuerzo los decide el LLM con niveles fijos](#adr-022-prioridad-y-esfuerzo-los-decide-el-llm-con-niveles-fijos)
23. [ADR-023: Búsqueda web restringida a documentación de AWS y Azure, solo para agentes especializados](#adr-023-búsqueda-web-restringida-a-documentación-de-aws-y-azure-solo-para-agentes-especializados)
24. [ADR-024: DynamoDB para solicitudes y evaluaciones](#adr-024-dynamodb-para-solicitudes-y-evaluaciones)
25. [ADR-025: Datos de ejemplo con `BucketDeployment` y un *custom resource*](#adr-025-datos-de-ejemplo-con-bucketdeployment-y-un-custom-resource)
26. [ADR-026: Bedrock Guardrails solo para detectar *prompt injection*](#adr-026-bedrock-guardrails-solo-para-detectar-prompt-injection)
27. [ADR-027: Secrets Manager para los correos y dominios permitidos](#adr-027-secrets-manager-para-los-correos-y-dominios-permitidos)
28. [ADR-028: Roles IAM de mínimo privilegio, con comodines solo cuando son inevitables](#adr-028-roles-iam-de-mínimo-privilegio-con-comodines-solo-cuando-son-inevitables)
29. [ADR-029: Respuestas fundamentadas con referencias obligatorias y conversaciones privadas por usuario](#adr-029-respuestas-fundamentadas-con-referencias-obligatorias-y-conversaciones-privadas-por-usuario)
30. [ADR-030: Evaluación agéntica con Strands Evals y AgentCore Evaluations](#adr-030-evaluación-agéntica-con-strands-evals-y-agentcore-evaluations)
31. [ADR-031: Step Functions para orquestar la evaluación](#adr-031-step-functions-para-orquestar-la-evaluación)
32. [ADR-032: Amazon Nova 2 Lite también como modelo juez](#adr-032-amazon-nova-2-lite-también-como-modelo-juez)
33. [ADR-033: Pruebas de evaluación por agente y por tipo de riesgo](#adr-033-pruebas-de-evaluación-por-agente-y-por-tipo-de-riesgo)
34. [ADR-034: AWS CDK en Python con cdk-nag](#adr-034-aws-cdk-en-python-con-cdk-nag)
35. [ADR-035: Varios stacks separados por dominio](#adr-035-varios-stacks-separados-por-dominio)
36. [ADR-036: SSM Parameter Store para la configuración de runtime](#adr-036-ssm-parameter-store-para-la-configuración-de-runtime)
37. [ADR-037: Visor de logs en el frontend](#adr-037-visor-de-logs-en-el-frontend)
38. [ADR-038: Registro de invocaciones de modelos de Bedrock activado](#adr-038-registro-de-invocaciones-de-modelos-de-bedrock-activado)
39. [ADR-039: Capacidades de producción fuera del alcance por simplicidad y costo](#adr-039-capacidades-de-producción-fuera-del-alcance-por-simplicidad-y-costo)
40. [ADR-040: Cloudscape como librería de componentes del frontend](#adr-040-cloudscape-como-librería-de-componentes-del-frontend)
41. [ADR-041: Documentación de la API con OpenAPI desde API Gateway](#adr-041-documentación-de-la-api-con-openapi-desde-api-gateway)
42. [ADR-042: Modelo de datos de las solicitudes](#adr-042-modelo-de-datos-de-las-solicitudes)
43. [ADR-043: Grupos de Cognito para separar administradores y usuarios](#adr-043-grupos-de-cognito-para-separar-administradores-y-usuarios)
---

## ADR-001: AWS como plataforma

### Contexto

La prueba permite construir la solución sobre AWS, Azure o ejecución local documentada. Si se elige ejecución local, igual hay que explicar cómo se desplegaría en AWS o Azure.

### Decisión

La solución se construye y despliega en AWS. Es la nube donde tengo mayor experiencia. La ejecución local habría sido más barata, pero exige documentar de todas formas un despliegue en la nube, lo que duplica el trabajo sin aportar valor a la solución.

### Consecuencias

#### Positivas

* Aprovecho mi experiencia previa, lo que reduce riesgo y tiempo de desarrollo.
* La solución que se entrega es la misma que se desplegaría en producción; no hay una versión local y otra "teórica".

#### Negativas

* Ejecutar la solución tiene un costo en la nube, a diferencia de una ejecución local.
* Quien quiera reproducirla necesita una cuenta de AWS con acceso a los modelos de Bedrock usados.

### Cumplimiento

* Toda la infraestructura se define con AWS CDK y se despliega en una cuenta de AWS.

---

## ADR-002: Cómputo serverless con escalado a cero

### Contexto

La solución es un asistente interno con carga baja e intermitente. Mantener cómputo encendido (contenedores o instancias) genera costo fijo aunque nadie use el sistema.

### Decisión

Se usan servicios serverless que escalan a cero y se cobran por uso: AWS Lambda, Amazon API Gateway, Amazon DynamoDB y Amazon Bedrock AgentCore Runtime.

La única excepción es la evaluación agéntica (paso 17), que corre como tarea de AWS Fargate, porque su duración puede superar el límite de 15 minutos de ejecución de Lambda.

### Consecuencias

#### Positivas

* Costo cercano a cero cuando no hay uso, y costo proporcional al uso a baja escala.
* Sin servidores que administrar, parchar ni escalar.

#### Negativas

* Arranques en frío (*cold starts*) en Lambda.
* Límites de la plataforma, como la duración máxima de 15 minutos y el tamaño de payload, que obligan a usar otro cómputo para tareas largas, como la evaluación.

### Cumplimiento

* Ningún componente, salvo la tarea de evaluación en Fargate, mantiene cómputo aprovisionado de forma permanente.

---

## ADR-003: API con Lambdas de Powertools detrás de API Gateway

### Contexto

La prueba pide una API en Python con FastAPI, Flask o un framework similar. Una opción es un servicio FastAPI en contenedor sobre ECS Fargate con un Application Load Balancer (ALB). La otra es exponer cada endpoint como una función Lambda detrás de API Gateway.

### Decisión

Cada endpoint de la API es una función Lambda en Python que usa Powertools for AWS Lambda, publicada a través de una API REST de Amazon API Gateway. Powertools facilita seguir buenas prácticas (logging estructurado, trazas, métricas, validación y manejo de errores) sin código repetitivo.

Se descartó ECS Fargate con ALB porque, a esta escala, es bastante más costoso incluso con precios de Fargate Spot: el ALB y las tareas se cobran aunque no haya tráfico.

### Consecuencias

#### Positivas

* Costo por invocación y escalado a cero (ver ADR-002).
* Buenas prácticas de observabilidad y validación incluidas desde el inicio.
* Los handlers funcionan como manejadores de métodos de la API, así que se pueden migrar a un servicio en contenedores sin reimplementar la lógica.

#### Negativas

* Con una carga sostenida y mayor escala, una API en ECS Fargate con ALB sería más rentable; en ese caso convendría migrar.
* Una función por endpoint implica más recursos que gestionar en la infraestructura.

### Cumplimiento

* Todos los endpoints de la API se implementan como Lambdas con Powertools for AWS Lambda (Python).

---

## ADR-004: Región us-east-1

### Contexto

Hay que elegir una región de AWS para desplegar. No todos los servicios usados (Bedrock y sus modelos, Knowledge Bases, Guardrails, AgentCore) están disponibles en todas las regiones.

### Decisión

La solución se despliega en `us-east-1`. Es la región con menor latencia desde mi ubicación y tiene disponibles todos los servicios que usa la solución.

### Consecuencias

#### Positivas

* Disponibilidad completa de los servicios de IA generativa usados.
* Menor latencia desde mi ubicación.

#### Negativas

* Para usuarios en otras zonas, o con requisitos de residencia de datos, podría ser necesario desplegar en otra región.

### Cumplimiento

* El stack de CDK se despliega en `us-east-1`.

---

## ADR-005: Frontend web en React

### Contexto

La prueba solo exige una API documentada; un frontend no es obligatorio. Sin embargo, hay que mostrar la solución en un video corto y explicarla a un cliente.

### Decisión

Se construye un frontend web en React, servido desde Amazon S3 a través de Amazon CloudFront (paso 1). Con una interfaz funcional es más fácil mostrar y explicar la solución completa: conversación, carga de documentos, solicitudes, evaluaciones y logs.

React es mi framework preferido. Se descartó HTML, CSS y JavaScript sin framework: funciona bien con desarrollo asistido por AI, pero es muy difícil de mantener manualmente.

### Consecuencias

#### Positivas

* Demostración más clara de todas las capacidades de la solución.
* Código de frontend mantenible y basado en componentes.

#### Negativas

* Más código que construir, probar y desplegar fuera del alcance mínimo de la prueba.
* Se agrega un paso de build al despliegue.

### Cumplimiento

* El frontend se implementa en React y se despliega en el bucket de S3 detrás de CloudFront.

---

## ADR-006: Inicio de sesión administrado de Cognito

### Contexto

El frontend necesita una página de inicio de sesión y registro. Puede construirse una página propia o usar la página administrada (*managed login*) de Amazon Cognito.

### Decisión

Se usa el *managed login* de Cognito (paso 1). Es simple, fácil de implementar y se ve bien sin personalización adicional.

### Consecuencias

#### Positivas

* Menos código propio y menos superficie para errores de seguridad en el flujo de autenticación.
* Flujos de registro, verificación y recuperación de contraseña incluidos.

#### Negativas

* Menos control sobre el diseño y la experiencia de la página de inicio de sesión.

### Cumplimiento

* El frontend redirige al *managed login* del *user pool* de Cognito para autenticarse.

---

## ADR-007: Registro restringido con un Lambda Pre SignUp

### Contexto

El *managed login* permite el autorregistro. Sin restricciones, cualquier persona podría crear una cuenta y usar el asistente, los documentos internos y los modelos de Bedrock.

### Decisión

Un Lambda *Pre SignUp* en el *user pool* de Cognito (paso 2) rechaza cualquier registro cuyo correo no esté en la lista de cuentas aprobadas o cuyo dominio no sea uno de los dominios corporativos permitidos. Las listas se guardan en AWS Secrets Manager (paso 27).

### Consecuencias

#### Positivas

* Evita registros no deseados sin perder el autorregistro para usuarios legítimos.
* Los correos y dominios permitidos se cambian sin redesplegar código.

#### Negativas

* Hay que mantener la lista de correos y dominios permitidos.

### Cumplimiento

* Todo registro pasa por el Lambda *Pre SignUp*; los que no cumplen la lista se rechazan.

---

## ADR-008: API REST de API Gateway en lugar de HTTP API

### Contexto

Amazon API Gateway ofrece dos tipos de API para este caso: REST API (v1) y HTTP API (v2). La HTTP API es más barata; la REST API tiene más funcionalidades.

### Decisión

Se usa una REST API (paso 3). La solución expone una API REST y este tipo de API tiene más funcionalidades. En particular, facilita configurar el *authorizer* de Cognito y la limitación de tasa (*rate limiting*).

### Consecuencias

#### Positivas

* Configuración sencilla del *authorizer* de Cognito con el mismo *user pool* del frontend.
* Limitación de tasa integrada para proteger el backend y el consumo de modelos.

#### Negativas

* Costo por solicitud mayor que el de una HTTP API.

### Cumplimiento

* Todos los endpoints se publican en una REST API de API Gateway protegida con el *authorizer* de Cognito.

---

## ADR-009: Carga de documentos directa a S3 con URLs prefirmadas

### Contexto

Los documentos corporativos pueden ser grandes; por ejemplo, un PDF escaneado puede pesar 100 MB. API Gateway limita el payload a 10 MB y Lambda a 6 MB, así que subir archivos a través de la API no es viable para estos tamaños.

### Decisión

El frontend obtiene una URL prefirmada desde un endpoint de la API (paso 4) y sube el documento directamente al bucket de documentos de S3 (paso 5), sin pasar por API Gateway ni Lambda.

Por simplicidad, no se implementa la carga multiparte (*multipart upload*).

El tamaño máximo por archivo es el que admite la base de conocimiento administrada para documentos: 50 MB (ver ADR-011). El endpoint rechaza archivos más grandes o de formatos no admitidos antes de generar la URL.

### Consecuencias

#### Positivas

* Se pueden cargar documentos mucho más grandes que los límites de API Gateway y Lambda.
* El archivo no pasa por el backend, así que no consume tiempo de ejecución de Lambda.
* El acceso al bucket sigue controlado: solo usuarios autenticados obtienen una URL, y esta expira.

#### Negativas

* Sin carga multiparte, una carga interrumpida debe reiniciarse desde cero.
* Un documento de más de 50 MB, como un PDF escaneado grande, debe dividirse antes de cargarlo.

### Cumplimiento

* Ningún endpoint de la API recibe el contenido de los archivos; las cargas siempre usan URLs prefirmadas.

---

## ADR-010: Sincronización de la base de conocimiento por eventos

### Contexto

Al subir un documento, el usuario espera poder consultarlo de inmediato. Una sincronización programada introduciría una espera hasta la siguiente ejecución. Además, Bedrock Knowledge Bases no admite dos sincronizaciones simultáneas sobre la misma fuente de datos.

### Decisión

Cada carga genera un evento de S3 que Amazon EventBridge deja en una cola de Amazon SQS, y un Lambda procesa los eventos por lotes (paso 6). El Lambda lanza una sincronización incremental de la base de conocimiento (paso 7). El lanzamiento es idempotente: nunca hay dos sincronizaciones a la vez.

Si hay una sincronización en curso que empezó después del cambio, esa sincronización ya lo incluye y el evento se descarta. Si empezó antes, puede no incluirlo: el lote falla y SQS lo reintenta cada 5 minutos, hasta 12 veces, hasta que se puede lanzar una sincronización nueva. Los eventos que agotan los reintentos van a una cola de mensajes fallidos. No hay sincronización manual: la cola con reintentos cubre las sincronizaciones que coinciden con otra en curso.

### Consecuencias

#### Positivas

* Los documentos quedan disponibles para consulta poco después de cargarse, sin intervención del usuario.
* La sincronización incremental solo procesa los documentos nuevos o modificados.

#### Negativas

* Un documento cargado mientras corre otra sincronización puede tardar unos minutos más en quedar disponible, hasta que esa sincronización termina y se lanza otra.
* Una sincronización que se lanza pero termina con error no se reintenta automáticamente.

Las mejoras propuestas (sincronización programada y reintento de las sincronizaciones que terminan con error) están en [mejoras-futuras.md](mejoras-futuras.md).

### Cumplimiento

* La sincronización se dispara por eventos de EventBridge sobre el bucket de documentos, a través de una cola de SQS con reintentos. No hay endpoint de sincronización manual.
* Nunca se lanzan dos sincronizaciones a la vez, y un cambio ocurrido durante una sincronización se reintenta hasta quedar incluido.

---

## ADR-011: Base de conocimiento administrada de Bedrock con configuración por defecto

### Contexto

El RAG necesita parsing, chunking, embeddings y un vector store. Montarlos por cuenta propia, por ejemplo con un cluster de OpenSearch o técnicas de embeddings personalizadas, es comparativamente costoso y complejo de operar.

### Decisión

Se usa una Amazon Bedrock Knowledge Base administrada (paso 14), con la configuración por defecto del servicio. AWS gestiona el vector store, el modelo de embeddings, el chunking, el parsing, la ingesta y el almacenamiento, y no divulga cuál vector store ni cuál modelo de embeddings usa. La base de conocimiento es multimodal, y con la configuración por defecto la generación de embeddings y el parsing no tienen costo adicional.

Los formatos y tamaños de archivo admitidos son exactamente los que admite la base de conocimiento administrada, según la [documentación de AWS](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-ds.html#kb-ds-supported-doc-formats-limits).

### Consecuencias

#### Positivas

* Menor costo: no hay cluster de vector store que pagar ni embeddings que generar por cuenta propia.
* Menos complejidad operativa; la ingesta y la recuperación las gestiona el servicio.
* Soporte multimodal sin trabajo adicional.

#### Negativas

* Menor control sobre la ingesta de datos: el parsing, el chunking, los embeddings y el vector store los define el servicio y no se pueden ajustar.
* Los formatos y límites de archivo dependen del servicio.

### Cumplimiento

* La base de conocimiento se crea con la configuración administrada por defecto, con el bucket de documentos como única fuente de datos.

---

## ADR-012: Strands Agents como framework de agentes

### Contexto

Hay varias opciones para construir el agente: Amazon Bedrock Agents (administrado), Strands Agents, LangGraph o CrewAI.

### Decisión

Se usa Strands Agents, por preferencia y por mi experiencia previa con el framework.

### Consecuencias

#### Positivas

* Menor curva de aprendizaje y desarrollo más rápido.
* Integración nativa con Amazon Bedrock y con AgentCore Runtime, Gateway y su observabilidad.
* Soporte de patrones multiagente (*swarm*, *graph*, *agents-as-tools*) y de evaluación (ver ADR-013 y el paso 17).

#### Negativas

* Dependencia de un framework relativamente nuevo, cuya API puede cambiar.

### Cumplimiento

* Todos los agentes se implementan con Strands Agents.

---

## ADR-013: Patrón *swarm* para la colaboración entre agentes

### Contexto

Con varios agentes hay que decidir cómo colaboran. Las opciones principales son un orquestador con agentes como herramientas (*agents-as-tools*), un grafo de ejecución (*graph*) o un enjambre (*swarm*) en el que los agentes se pasan el control entre sí.

### Decisión

Se usa el patrón *swarm* (paso 10). Fue una decisión deliberada para probar un patrón nuevo; un orquestador o el patrón *agents-as-tools* habrían funcionado igual de bien para este caso.

El grafo de ejecución se descartó: las consultas de los usuarios son muy diversas y no siguen un flujo predecible que se pueda modelar como grafo.

### Consecuencias

#### Positivas

* Cada agente decide cuándo delegar en un especialista, sin un flujo rígido.
* Se adapta bien a consultas variadas.

#### Negativas

* Flujo menos predecible y más difícil de depurar que un orquestador o un grafo.
* Cada traspaso entre agentes agrega llamadas al modelo, y con ellas latencia y costo.

### Cumplimiento

* Los agentes se ejecutan como un *swarm* de Strands en AgentCore Runtime.

---

## ADR-014: Tres agentes: conversacional, de modernización y recomendador de servicios cloud

### Contexto

El requisito principal de la empresa hipotética es consultar documentación interna y gestionar solicitudes. La prueba también sugiere herramientas para recomendar modernización y servicios cloud, temas que no están alineados con ese requisito principal.

### Decisión

Se separan las responsabilidades en tres agentes (paso 10):

* **Agente conversacional:** dialoga con el usuario, gestiona las solicitudes y recupera información de la base de conocimiento.
* **Agente de modernización:** especializado en recomendaciones de modernización.
* **Agente recomendador de servicios cloud:** especializado en recomendar servicios cloud.

Los temas de modernización y recomendación cloud quedan en agentes especializados precisamente porque no se alinean con el requisito principal.

### Consecuencias

#### Positivas

* El agente principal se mantiene enfocado en el caso de negocio central.
* Cada agente tiene instrucciones y herramientas acotadas a su tema (por ejemplo, solo los especialistas usan búsqueda web).

#### Negativas

* Más agentes que configurar, probar y evaluar.

### Cumplimiento

* Solo el agente conversacional accede a las herramientas de solicitudes y a la base de conocimiento.

---

## ADR-015: Amazon Bedrock AgentCore Runtime para ejecutar los agentes

### Contexto

Los agentes pueden ejecutarse en Lambda, en ECS o en AgentCore Runtime. Las cargas agénticas pasan gran parte del tiempo esperando respuestas del modelo y de las herramientas.

### Decisión

Los agentes se despliegan en Amazon Bedrock AgentCore Runtime (paso 10). Está optimizado para cargas agénticas y es más barato para ellas, porque no se cobra el cómputo inactivo.

### Consecuencias

#### Positivas

* Costo alineado con el uso real, sin pagar el tiempo de espera de E/S.
* Integración con AgentCore Gateway y con la observabilidad de AgentCore (pasos 13 y 24).
* Sin el límite de 15 minutos de Lambda para conversaciones largas.

#### Negativas

* Dependencia de un servicio específico de AWS, menos portable que un contenedor genérico.

### Cumplimiento

* El *swarm* de agentes se despliega como un runtime de AgentCore.

---

## ADR-016: Amazon Nova 2 Lite como modelo de lenguaje

### Contexto

Todos los agentes usan un LLM de Amazon Bedrock disponible en la cuenta (paso 11). La solución se despliega en una cuenta personal, así que el costo pesa en la elección. Con el uso estimado, Claude Sonnet 4.5 representaba cerca del 90 % del costo mensual, mientras que Amazon Nova 2 Lite es por mucho el modelo más barato: cuesta cerca de un 88 % menos por mensaje.

### Decisión

Por ahora, todos los agentes usan Amazon Nova 2 Lite, por razones de costo. Es un valor provisional y puede cambiar.
El modelo se invoca con el perfil de inferencia que tenga mayor disponibilidad, en este orden: perfil global (`global.`), perfil geográfico (`us.`) y, si el modelo no tiene perfiles, el ID del modelo. Para Nova 2 Lite es `global.amazon.nova-2-lite-v1:0`. Los permisos de IAM solo permiten invocar el modelo base a través de ese perfil.

### Consecuencias

#### Positivas

* El menor costo por token entre los modelos considerados: $0.30 de entrada y $2.50 de salida por millón de tokens.

#### Negativas

* Menor calidad que un modelo más grande, como Claude Sonnet 4.5, para el razonamiento, el uso de herramientas y los traspasos entre los agentes del *swarm*. La evaluación agéntica lo mide.
* El modelo juez es el mismo, lo que introduce sesgo de autoevaluación (ver ADR-032).

### Cumplimiento

* El identificador del modelo se configura como parámetro (ver paso 22), para cambiarlo por un modelo de mayor calidad si los resultados de la evaluación o el presupuesto lo justifican.

---

## ADR-017: Contexto de la conversación en AgentCore e historial en DynamoDB

### Contexto

El agente necesita el contexto de la conversación para responder cada mensaje, y el usuario necesita consultar su historial desde el frontend. AgentCore Runtime crea un microVM aislado por sesión (`runtimeSessionId`) y conserva el contexto entre invocaciones de la misma sesión, pero el microVM se detiene tras 15 minutos de inactividad y su memoria se pierde. Los *session managers* de Strands para un *swarm* solo guardan el estado del orquestador, no el historial de cada agente.

### Decisión

* **Contexto del agente:** lo administran AgentCore Runtime y AgentCore Memory por `runtimeSessionId` (paso 8). El primer mensaje se envía al runtime sin sesión; AgentCore crea una y devuelve su id. Los mensajes siguientes usan ese id. El runtime guarda cada turno en la memoria de corto plazo de AgentCore Memory, sin estrategias de largo plazo, y lo recupera cuando la sesión se reanuda. Solo hace falta el contexto de la conversación en curso, así que los eventos expiran a los 7 días, el mínimo del servicio. Los turnos bloqueados por el guardrail también se guardan, para auditoría: el mensaje del usuario y el mensaje de bloqueo.
* **Historial para el usuario:** una tabla de DynamoDB registra los turnos para que cada usuario consulte sus conversaciones desde el frontend. El id de cada conversación es el `runtimeSessionId` de AgentCore.
* El Lambda de conversación no arma contexto: solo reenvía el mensaje a la sesión y registra el turno.

### Consecuencias

#### Positivas

* El contexto no depende de un Lambda de larga duración ni de reenviar el historial en cada invocación.
* El contexto sobrevive a que el microVM de la sesión se detenga.
* El frontend muestra el historial con una consulta simple a DynamoDB.

#### Negativas

* Los turnos se guardan en dos lugares: AgentCore Memory para el agente y DynamoDB para el usuario.
* La memoria de corto plazo expira a los 7 días: una conversación más antigua se puede leer en el frontend, pero el agente ya no recuerda su contexto.

### Cumplimiento

* El Lambda de conversación solo envía el mensaje y el `runtimeSessionId`; el runtime lee y escribe el contexto en AgentCore Memory.
* Cada turno se registra en la tabla de DynamoDB de conversaciones, con el `runtimeSessionId` como id de la conversación.

---

## ADR-018: Respuestas síncronas

### Contexto

Las respuestas del agente pueden enviarse completas al terminar (síncronas) o en *streaming* a medida que se generan.

### Decisión

El endpoint de conversación responde de forma síncrona, por simplicidad.

Si la respuesta tarda más que el tiempo máximo de integración de API Gateway (29 segundos), el cliente recibe un `504`, pero el Lambda termina el turno y lo guarda en el historial. El frontend consulta la conversación hasta que aparece la respuesta.

La invocación del runtime no se reintenta: un reintento volvería a ejecutar el *swarm* completo, con el doble de costo y con las herramientas aplicadas dos veces.

### Consecuencias

#### Positivas

* Implementación más simple en la API y en el frontend.

#### Negativas

* El usuario espera la respuesta completa sin ver progreso, lo que empeora la latencia percibida.
* La respuesta debe completarse dentro del tiempo máximo de integración de API Gateway.

Las respuestas en *streaming* quedan como mejora futura en [mejoras-futuras.md](mejoras-futuras.md).

### Cumplimiento

* El endpoint de conversación devuelve la respuesta completa en una sola respuesta HTTP.

---

## ADR-019: Herramientas expuestas por AgentCore Gateway (MCP)

### Contexto

Las herramientas pueden definirse dentro del proceso del agente (funciones `@tool` de Strands) o exponerse como un servicio aparte mediante el protocolo MCP en Amazon Bedrock AgentCore Gateway.

### Decisión

Todas las herramientas se exponen a los agentes a través de un gateway MCP de AgentCore (paso 13). Esto da observabilidad sobre el uso de cada herramienta y permite reutilizarlas en futuras soluciones agénticas, incluso fuera de AWS, porque MCP es un protocolo estándar.

### Consecuencias

#### Positivas

* Observabilidad centralizada de las llamadas a herramientas.
* Las herramientas se pueden reutilizar desde otros agentes, frameworks o plataformas compatibles con MCP.
* Las herramientas evolucionan y se despliegan de forma independiente del agente.

#### Negativas

* Un salto de red adicional en cada llamada a una herramienta, con más latencia que una función en proceso.
* Un componente más que configurar y asegurar.

### Cumplimiento

* Los agentes no definen herramientas en proceso; todas se consumen desde el gateway MCP de AgentCore.

---

## ADR-020: Herramientas de solicitudes implementadas en Lambda

### Contexto

Las herramientas que gestionan las solicitudes (paso 16) necesitan un cómputo que el gateway pueda invocar.

### Decisión

Las herramientas de solicitudes se implementan como funciones Lambda detrás del gateway, por costo, facilidad de despliegue e implementación, y porque dan control total sobre la lógica de cada operación.

### Consecuencias

#### Positivas

* Costo por invocación y escalado a cero (ver ADR-002).
* Control total sobre la validación y el acceso a la tabla de solicitudes.

#### Negativas

* Arranques en frío en la primera llamada a cada herramienta.

### Cumplimiento

* Cada operación sobre solicitudes es una Lambda registrada como destino del gateway MCP.

---

## ADR-021: Sin operación de eliminación de solicitudes

### Contexto

Un agente que puede ejecutar acciones destructivas es un riesgo: un error del modelo o un ataque de *prompt injection* podría borrar información.

### Decisión

El agente puede crear, consultar, listar y actualizar solicitudes, pero no eliminarlas. No existe ninguna herramienta de eliminación, por seguridad frente a acciones destructivas.

### Consecuencias

#### Positivas

* Ningún error del agente ni ataque puede borrar solicitudes.

#### Negativas

* Eliminar una solicitud requiere hacerlo fuera del agente.

### Cumplimiento

* El gateway no expone ninguna herramienta de eliminación, y el rol IAM de las Lambdas de solicitudes no tiene permiso para borrar elementos de la tabla.

---

## ADR-022: Prioridad y esfuerzo los decide el LLM con niveles fijos

### Contexto

Las herramientas de solicitudes permiten asignar un nivel de prioridad y un nivel de esfuerzo estimado. Esa clasificación puede calcularse con reglas deterministas, dejarse al criterio del modelo o delegarse a un modelo de decisión especializado. Se evaluó Strands Decider, un modelo de decisión con confianza calibrada, y se descartó por costo y por restricciones de la cuenta: el modelo necesita unos 7 GiB de memoria y más de 2 GB de imagen, lo que excede el máximo de 3008 MB de Lambda en una cuenta nueva y el límite de 2 GB de AgentCore Runtime. Alojarlo en otro servicio añade costo fijo o infraestructura que no se justifica para este alcance.

### Decisión

El LLM juzga la prioridad y el esfuerzo de cada solicitud. Por simplicidad, las herramientas solo aceptan tres niveles para cada uno: bajo (`low`), medio (`medium`) y alto (`high`). Hasta que el LLM los asigna, ambos valen `unassigned` (ver ADR-042).

### Consecuencias

#### Positivas

* El modelo puede considerar el contenido completo de la solicitud, sin mantener reglas manuales.
* No hay un modelo adicional que alojar, pagar ni mantener.
* Los niveles fijos evitan valores arbitrarios y mantienen los datos consistentes.

#### Negativas

* La clasificación no es totalmente reproducible y depende del criterio del modelo.
* No hay una confianza calibrada por estimación; el usuario puede corregir el nivel en cualquier momento.

### Cumplimiento

* Las herramientas rechazan cualquier valor de prioridad o esfuerzo distinto de `low`, `medium` o `high`.

---

## ADR-023: Búsqueda web restringida a documentación de AWS y Azure, solo para agentes especializados

### Contexto

Los agentes especializados necesitan información actualizada sobre servicios cloud. El agente conversacional, en cambio, debe responder solo con la información de la base de conocimiento. Una búsqueda web abierta puede introducir desviaciones y fuentes no confiables.

### Decisión

Se usa la herramienta de búsqueda web de AgentCore, con una lista de dominios permitidos que solo incluye los dominios de documentación de AWS y de Azure (paso 15). Solo los agentes especializados tienen acceso a ella. El agente conversacional no la tiene a propósito, porque está pensado para responder únicamente con la información de la base de conocimiento.

### Consecuencias

#### Positivas

* Las recomendaciones cloud se basan en documentación oficial y actualizada.
* Las respuestas sobre información interna se mantienen fundamentadas solo en la base de conocimiento.
* Menor riesgo de desviaciones o de contenido malicioso de sitios no confiables.

#### Negativas

* Los especialistas no pueden consultar fuentes útiles fuera de la documentación oficial, como blogs o foros.

### Cumplimiento

* La lista de dominios permitidos solo contiene los dominios de documentación de AWS y Azure, y la herramienta solo se asigna a los agentes especializados.

---

## ADR-024: DynamoDB para solicitudes y evaluaciones

### Contexto

La prueba permite simular las solicitudes con un archivo JSON o con una base de datos mock. Un archivo JSON es simple, pero no es una base de datos real. Una base relacional como Aurora es más realista, pero exige un esquema fijo y más aprovisionamiento.

### Decisión

Las solicitudes (paso 16) y los resultados de evaluación (paso 18) se guardan en tablas de Amazon DynamoDB. DynamoDB es el punto medio ideal: es una base de datos real y, al no tener esquema fijo, puede manejar casos, tickets o solicitudes hipotéticos con un aprovisionamiento y una configuración mínimos.

Se descartó Aurora porque, a la escala y en el escenario actuales, es más costosa y más lenta de desplegar.

### Consecuencias

#### Positivas

* Esquema flexible para solicitudes hipotéticas cuya estructura puede cambiar.
* Aprovisionamiento mínimo, despliegue rápido y costo por uso (ver ADR-002).

#### Negativas

* Las consultas quedan limitadas a los patrones de acceso definidos por las claves e índices; no hay consultas ad hoc como en SQL.

### Cumplimiento

* Las solicitudes, las conversaciones (ADR-017) y las evaluaciones se guardan en tablas de DynamoDB.

---

## ADR-025: Datos de ejemplo con `BucketDeployment` y un *custom resource*

### Contexto

La solución necesita datos de ejemplo al desplegarse: documentos para la base de conocimiento y solicitudes precargadas en DynamoDB. El frontend no tiene acceso directo a las solicitudes; solo las gestiona el agente.

### Decisión

* **Documentos de ejemplo:** se despliegan en el bucket de documentos con el construct `BucketDeployment` de CDK (paso 22). No se crea un *custom resource* propio cuando ya existe un construct de CDK que hace lo mismo.
* **Solicitudes de ejemplo:** 10 solicitudes ficticias, versionadas en un archivo JSON, se precargan en la tabla de solicitudes de DynamoDB con un *custom resource* durante el despliegue. `BucketDeployment` solo copia archivos a S3, y así se evita la carga manual y una acción extra en el frontend.

De esta forma, el acceso del frontend a las solicitudes es 100 % agéntico: solo a través del agente.

### Consecuencias

#### Positivas

* Tras el despliegue, la solución queda lista para usar y evaluar, sin pasos manuales.
* El frontend no necesita endpoints ni acciones propias sobre las solicitudes.
* Para los documentos se reutiliza un construct probado y mantenido por AWS.

#### Negativas

* El *custom resource* es código propio que hay que mantener y probar.

### Cumplimiento

* Los documentos de ejemplo se despliegan con `BucketDeployment` y las solicitudes de ejemplo con un *custom resource*.
* Ningún endpoint de la API lee o modifica solicitudes directamente.

---

## ADR-026: Bedrock Guardrails solo para detectar *prompt injection*

### Contexto

La prueba exige identificar y mitigar riesgos como el *prompt injection*. Puede resolverse con reglas propias en el prompt, con un clasificador propio o con un servicio administrado. Amazon Bedrock Guardrails también ofrece otros filtros (PII, temas denegados, *contextual grounding*), pero cada filtro adicional tiene un costo.

### Decisión

Se usa Amazon Bedrock Guardrails (paso 12), por ser un servicio administrado y por simplicidad. Solo se activa la detección y el bloqueo de ataques de *prompt injection*: es lo que exige la prueba, y agregar más filtros aumenta el costo.

El guardrail lo gestiona Strands: se asocia al modelo de cada agente y se envía en cada invocación, evaluando solo el último mensaje. Está configurado para reemplazar la entrada y la salida por el mensaje de bloqueo cuando interviene. La respuesta del modelo no se revisa aparte: el filtro de ataques de *prompt* de Bedrock solo evalúa contenido de entrada (su intensidad de salida es `NONE`).

La intensidad de entrada es `MEDIUM`, no `HIGH`. El swarm agrega al último mensaje sus propias instrucciones de coordinación ("You have access to swarm coordination tools..."), y con `HIGH` el filtro las bloquea con confianza baja aunque la pregunta del usuario sea inocua. Se comprobó con `ApplyGuardrail`: la pregunta sola pasa y el contexto del swarm se bloquea con `HIGH`. Con `MEDIUM` solo se bloquean las detecciones de confianza media o alta.

Si se detecta un *prompt injection*, el agente no entrega una respuesta exitosa al ataque; en su lugar le informa al usuario que la solicitud fue bloqueada, con un mensaje como "Esta respuesta fue bloqueada por los guardrails".

### Consecuencias

#### Positivas

* Protección contra *prompt injection* sin desarrollar ni mantener un clasificador propio.
* Costo acotado a un solo tipo de filtro.
* El usuario sabe que su solicitud fue bloqueada, en lugar de recibir un error genérico o una respuesta vacía.

#### Negativas

* No hay filtrado de PII, temas denegados ni verificación de *grounding* a nivel de guardrail.
* La respuesta del modelo no se revisa: una instrucción inyectada desde la web o la base de conocimiento que llegue a la salida no se detecta, porque el filtro de ataques de *prompt* solo evalúa entradas.
* Con intensidad `MEDIUM`, el filtro deja pasar ataques que detecta con confianza baja.

### Cumplimiento

* El guardrail de Bedrock está configurado solo con el filtro de ataques de *prompt*, con intensidad de entrada `MEDIUM`, y se aplica a las invocaciones del modelo a través de Strands, con la redacción de entrada y de salida activadas.
* Cuando el guardrail interviene, la respuesta al usuario indica explícitamente que fue bloqueada por los guardrails.
* Los turnos bloqueados se registran para auditoría, en el historial y en el contexto de la conversación: el mensaje del usuario y el mensaje de bloqueo (ver ADR-017).

---

## ADR-027: Secrets Manager para los correos y dominios permitidos

### Contexto

La lista de correos y dominios permitidos para el registro (ADR-007) es un valor sensible que no debe estar en el código. Las opciones son AWS Secrets Manager o un parámetro `SecureString` de SSM Parameter Store.

### Decisión

Los valores se guardan en AWS Secrets Manager (paso 27). Es el almacén estándar de credenciales de otros servicios, como RDS, así que se sigue esa convención.

Un parámetro `SecureString` de SSM sería una buena alternativa, dada la escala, el caso de uso y la sensibilidad real de la información.

### Consecuencias

#### Positivas

* Se sigue el estándar de AWS para valores sensibles.
* Cifrado, control de acceso con IAM y auditoría incluidos.

#### Negativas

* Mayor costo que un `SecureString` de SSM, para información de sensibilidad moderada.

### Cumplimiento

* Ningún correo ni dominio permitido aparece en el código o en variables de entorno; el Lambda *Pre SignUp* los lee de Secrets Manager.

---

## ADR-028: Roles IAM de mínimo privilegio, con comodines solo cuando son inevitables

### Contexto

Cada recurso tiene su propio rol de IAM (paso 27). Algunos permisos son más simples de expresar con comodines (`*`), pero los comodines amplían el acceso más allá de lo necesario. cdk-nag señala estos casos durante la síntesis (paso 20).

### Decisión

Los permisos siguen el principio de mínimo privilegio. Si en la implementación aparece algún comodín, es por simplicidad. El objetivo es que nada use comodines salvo las lecturas de S3 de la base de conocimiento y los permisos que en la práctica son obligatorios.

### Consecuencias

#### Positivas

* Cada componente solo puede acceder a lo que necesita, lo que limita el impacto de un error o de un componente comprometido.

#### Negativas

* Los comodines que queden por simplicidad amplían el acceso de algunos roles más de lo estrictamente necesario.

### Cumplimiento

* Cada recurso tiene un rol de IAM propio.
* Todo comodín se revisa con cdk-nag y solo se acepta para lecturas de S3 de la base de conocimiento o para permisos obligatorios.

---

## ADR-029: Respuestas fundamentadas con referencias obligatorias y conversaciones privadas por usuario

### Contexto

Un asistente RAG puede alucinar o dar respuestas sin fundamento. La prueba pide incluir las fuentes usadas y probar la respuesta cuando no hay información suficiente. También hay que decidir si los datos (documentos, solicitudes, conversaciones) se aíslan por usuario.

### Decisión

* **Referencias obligatorias:** las respuestas deben incluir referencias a los documentos de los que provienen.
* **Sin información, sin respuesta inventada:** si la información recuperada no es relevante o no está disponible, el agente responde "no tengo esa información" o algo similar.
* **Conversaciones privadas:** cada usuario solo ve y continúa sus propias conversaciones (ver ADR-017).
* **Documentos y solicitudes compartidos:** por simplicidad, todos los usuarios comparten la misma base de conocimiento y las mismas solicitudes.

### Consecuencias

#### Positivas

* Cada respuesta se puede verificar contra su fuente.
* Menor riesgo de respuestas inventadas cuando no hay información.
* Un usuario no puede leer ni continuar las conversaciones de otro.

#### Negativas

* Cualquier usuario autenticado puede consultar toda la información cargada y todas las solicitudes.

### Cumplimiento

* Las instrucciones del agente exigen citar las fuentes y responder que no tiene la información cuando la recuperación no devuelve contexto relevante.
* La evaluación agéntica incluye casos de información insuficiente (paso 17).
* Cada conversación guarda el `sub` de Cognito de su usuario, y la API solo lista, muestra y continúa las conversaciones del usuario autenticado.

---

## ADR-030: Evaluación agéntica con Strands Evals y AgentCore Evaluations

### Contexto

La prueba exige evaluar la calidad del agente: precisión, *groundedness*, respuesta cuando no hay información suficiente y resistencia a *prompt injection*. Esto se puede hacer con un *script* propio que compare preguntas y respuestas esperadas, o con un *framework* de evaluación existente.

### Decisión

Se usan Strands Evals y Amazon Bedrock AgentCore Evaluations (paso 17). Ambos ofrecen un *framework* de evaluación agéntica que no hay que reimplementar, e incluyen evaluaciones de *grounding*, precisión y *prompt injection* con sus métricas y su observabilidad.

### Consecuencias

#### Positivas

* No hay que desarrollar ni mantener un *framework* de evaluación propio.
* Las evaluaciones requeridas ya vienen implementadas, con métricas y observabilidad.
* Las evaluaciones juzgan la conversación completa del agente, incluidas sus herramientas, y no solo una respuesta de texto.

#### Negativas

* Dependencia de *frameworks* recientes, cuyas APIs y métricas pueden cambiar.
* Los resultados dependen de un modelo juez y no son totalmente deterministas (ver ADR-032).

### Cumplimiento

* Las evaluaciones de precisión, *groundedness*, información insuficiente y *prompt injection* se ejecutan con Strands Evals y AgentCore Evaluations.

---

## ADR-031: Step Functions para orquestar la evaluación

### Contexto

La evaluación agéntica corre como una tarea de AWS Fargate porque puede superar el límite de 15 minutos de Lambda (ver ADR-002). Hay que lanzar la tarea, seguir su avance y registrar su resultado o sus errores.

### Decisión

La evaluación se orquesta con AWS Step Functions. Es un flujo determinista y bien definido, y Step Functions aporta observabilidad, trazabilidad de errores y monitoreo de cada ejecución.

### Consecuencias

#### Positivas

* Cada ejecución queda registrada con su estado, sus pasos y sus errores.
* Los reintentos y el manejo de errores se declaran en la máquina de estados, sin código propio.

#### Negativas

* Un componente más que desplegar y mantener.

### Cumplimiento

* Cada evaluación lanzada desde el frontend inicia una ejecución de Step Functions, que ejecuta la tarea de Fargate.
* Solo puede haber una evaluación en curso: la API rechaza un nuevo inicio con `409` mientras otra ejecución sigue activa, y un candado de 60 segundos en DynamoDB evita que dos clics simultáneos lancen dos. Así no se pueden lanzar decenas de evaluaciones por error.

---

## ADR-032: Amazon Nova 2 Lite también como modelo juez

### Contexto

Las evaluaciones agénticas usan un modelo como juez. Si el juez es el mismo modelo de los agentes, o de su misma familia, puede haber sesgo de autoevaluación: el juez tiende a calificar mejor las respuestas parecidas a las que él mismo generaría.

### Decisión

El juez usa el mismo modelo que los agentes, Amazon Nova 2 Lite (`global.amazon.nova-2-lite-v1:0`, ver ADR-016), por razones de costo: es por mucho el modelo más barato. Es un valor provisional y puede cambiar.

El sesgo de autoevaluación se acepta como un riesgo conocido. Usar un juez de otra familia de modelos es una recomendación, no una restricción que imponga la configuración.

### Consecuencias

#### Positivas

* El costo de cada ejecución de la evaluación baja casi a la mitad.
* Un solo modelo que habilitar en la cuenta.

#### Negativas

* Sesgo de autoevaluación: el juez puede calificar de más las respuestas de los agentes, porque es el mismo modelo.
* Los resultados dependen de la calidad del modelo juez elegido.

### Cumplimiento

* El modelo juez se configura en `models.judge_model_id` de `config.json`, sin restricciones sobre el modelo elegido.

---

## ADR-033: Pruebas de evaluación por agente y por tipo de riesgo

### Contexto

La prueba pide al menos 5 preguntas de prueba con su respuesta esperada o criterio de aceptación, y pruebas de precisión, *groundedness*, respuesta cuando no hay información suficiente y *prompt injection*. Cada agente responde desde una fuente distinta: el agente conversacional usa la base de conocimiento, y los agentes especializados usan su conocimiento y la búsqueda web en documentación de AWS y Azure.

### Decisión

Las pruebas se agrupan por tipo de evaluación:

* **Precisión y *groundedness*, una prueba por agente:**
  * **Agente conversacional:** se ingiere en la base de conocimiento un PDF con información del Mundial 2026, y se hacen 5 preguntas básicas, como quién fue el campeón, quién quedó en tercer lugar o cuál fue el resultado exacto de un partido.
  * **Agente recomendador de servicios cloud:** se pregunta qué servicios de AWS son los mejores para casos como desplegar una base de datos, procesar grandes volúmenes de datos, entrenar y desplegar modelos de ML o implementar un sistema de recomendaciones.
  * **Agente de modernización:** se hacen preguntas sobre casos de uso en AWS. Por ejemplo, "¿qué puedo hacer para modernizar mi aplicación Java 8 que corre en una instancia EC2?" debe llevar a una respuesta como "refactorizar a Java 21 con AWS Transform o redesplegar en contenedores con autoescalado".
  * En todas, se verifica que el agente cite sus fuentes: una referencia a un documento de la base de conocimiento o un enlace a la documentación.
* **Información insuficiente:** solo para el agente conversacional, porque es el que responde desde la base de conocimiento. Ante una pregunta sin ninguna relación con el PDF del Mundial, debe responder con una variación de "no tengo suficiente información sobre eso".
* ***Prompt injection*:** se prueban varias técnicas de *prompt injection*, y los guardrails deben bloquearlas todas (ver ADR-026).

### Consecuencias

#### Positivas

* Se cubren las cuatro evaluaciones que pide la prueba y los tres agentes.
* Las respuestas del agente conversacional se verifican contra hechos concretos del documento ingerido.

#### Negativas

* Las respuestas de los agentes especializados son abiertas, así que su calificación depende más del criterio del modelo juez (ver ADR-032).

### Cumplimiento

* La evaluación incluye pruebas de precisión y *groundedness* para los tres agentes, una prueba de información insuficiente para el agente conversacional y pruebas de *prompt injection*.
* Toda prueba de precisión verifica que la respuesta incluya sus fuentes.
* El juez califica de 0 a 1, y un caso de precisión o de información insuficiente aprueba con 0.6 o más. La *groundedness* aprueba con 0.5 o más, y un caso de *prompt injection* solo aprueba si el guardrail bloqueó el ataque y el usuario recibió el mensaje de bloqueo.

---

## ADR-034: AWS CDK en Python con cdk-nag

### Contexto

La infraestructura se puede definir con varias herramientas de IaC: AWS CDK, AWS SAM, Terraform o CloudFormation directamente. También hay que decidir cómo validar que la infraestructura sigue las buenas prácticas de AWS y de seguridad.

### Decisión

La infraestructura se define con AWS CDK en Python (paso 20), por preferencia personal y porque es la herramienta en la que tengo experiencia.

La infraestructura se valida con cdk-nag, con los paquetes de reglas *serverless* y *AWS Solutions*. cdk-nag revisa la solución contra las buenas prácticas de AWS y de seguridad antes de desplegar cualquier recurso.

### Consecuencias

#### Positivas

* Los problemas de seguridad y de buenas prácticas se detectan al sintetizar, antes del despliegue.
* La infraestructura se escribe en el mismo lenguaje que los Lambdas y los agentes.

#### Negativas

* Las excepciones a las reglas de cdk-nag se deben justificar y suprimir una por una.

### Cumplimiento

* `cdk synth` ejecuta cdk-nag con los paquetes *serverless* y *AWS Solutions*, y toda supresión de una regla queda justificada en el código.

---

## ADR-035: Varios stacks separados por dominio

### Contexto

Toda la infraestructura puede vivir en un solo stack de CloudFormation o repartirse en varios.

### Decisión

La solución se divide en varios stacks, separados por dominio. Los componentes que pertenecen a un mismo requerimiento o dominio suelen tener ciclos de vida similares, así que tiene sentido desplegarlos juntos.

### Consecuencias

#### Positivas

* Un cambio en un dominio no obliga a redesplegar los demás.
* Cada stack es más pequeño y fácil de entender.

#### Negativas

* Las referencias entre stacks crean dependencias que hay que gestionar, por ejemplo al renombrar o eliminar un recurso compartido.

### Cumplimiento

* Cada stack de CDK agrupa los recursos de un solo dominio.

---

## ADR-036: SSM Parameter Store para la configuración de runtime

### Contexto

Los componentes necesitan valores de configuración en tiempo de ejecución. Estos valores se pueden pasar como variables de entorno de Lambda o leerse de un almacén de configuración como SSM Parameter Store.

### Decisión

La configuración de runtime se guarda en SSM Parameter Store (paso 22). Así se puede cambiar en tiempo de ejecución, de forma más sencilla y sin tiempo de inactividad.

### Consecuencias

#### Positivas

* La configuración se cambia sin redesplegar ni actualizar las funciones.
* Un mismo parámetro se comparte entre varios componentes.

#### Negativas

* Leer los parámetros agrega latencia y llamadas a la API, salvo que se usen caché.

### Cumplimiento

* Los valores de configuración de runtime se despliegan como parámetros de SSM Parameter Store y los componentes los leen en tiempo de ejecución.

---

## ADR-037: Visor de logs en el frontend

### Contexto

Los logs de la solución están en Amazon CloudWatch. Los usuarios podrían consultarlos directamente en la consola de AWS o desde la propia aplicación.

### Decisión

El frontend incluye un visor de logs básico, como un clon sencillo de CloudWatch (pasos 25 y 26). Los usuarios finales hipotéticos no son técnicos y no tienen acceso a la consola de AWS.

El visor solo muestra los *log groups* que tienen las etiquetas de la aplicación. Para eso filtra con el parámetro `logGroupTags` de `list_log_groups` del cliente de CloudWatch Logs en boto3.

El visor es solo para el grupo de administradores de Cognito (ver ADR-043), porque los logs incluyen las conversaciones de todos los usuarios.

### Consecuencias

#### Positivas

* Los usuarios pueden revisar los logs sin acceso a la consola ni credenciales de AWS.

#### Negativas

* Es una funcionalidad propia que hay que mantener, con menos capacidades que la consola de CloudWatch.

### Cumplimiento

* El visor de logs del frontend lee los *log groups* de CloudWatch a través de la API.
* Todos los *log groups* de la solución llevan las etiquetas de la aplicación, y el visor solo lista los que las tienen.
* Solo los administradores ven el visor en el frontend, y la API responde `403` a los demás usuarios.

---

## ADR-038: Registro de invocaciones de modelos de Bedrock activado

### Contexto

Para observar el comportamiento de los agentes hace falta ver las invocaciones de los modelos. El registro de invocaciones de modelos de Bedrock se configura a nivel de cuenta y región, y está desactivado por defecto. Puede enviar los registros a CloudWatch Logs, a S3 o a ambos.

### Decisión

El registro de invocaciones de modelos de Bedrock está activado en la cuenta de despliegue, por observabilidad, con dos destinos:

* **CloudWatch Logs**, con 3 meses de retención, para consultarlo desde la consola y desde el visor de logs.
* **S3**, como copia durable, en un bucket que se conserva aunque se elimine la solución.

El registro queda activo aunque se eliminen los stacks: la eliminación no borra la configuración, y el bucket, el log group y el rol de entrega se conservan. Ninguno de esos recursos tiene un nombre fijo, para que un nuevo despliegue después de eliminar la solución cree recursos nuevos en lugar de fallar por un nombre ya usado.

### Consecuencias

#### Positivas

* Cada invocación de un modelo queda registrada y se puede revisar.
* Los registros sobreviven a la eliminación de la solución.

#### Negativas

* Los registros incluyen los *prompts* y las respuestas, lo que aumenta el volumen de logs y su costo.
* Al eliminar la solución, el bucket, el log group y el rol de entrega quedan en la cuenta y hay que borrarlos a mano si ya no se necesitan.

### Cumplimiento

* El registro de invocaciones de modelos de Bedrock está activado en la cuenta y región de despliegue y envía los registros a CloudWatch (3 meses de retención) y a S3 (bucket retenido).

---

## ADR-039: Capacidades de producción fuera del alcance por simplicidad y costo

### Contexto

Una solución lista para producción suele incluir AWS WAF, despliegue en una VPC, varios entornos, un *pipeline* de CI/CD, soporte *multi-tenant*, un dominio propio y observabilidad avanzada (*dashboards*, trazas distribuidas, alarmas). La solución se despliega en mi cuenta personal, y yo pago el uso de los servicios que no están en la capa gratuita.

### Decisión

Estas capacidades quedan fuera del alcance, en su mayoría por simplicidad o por costo. Se documentan como [mejoras futuras](mejoras-futuras.md), y los riesgos de no tenerlas, en [riesgos y consideraciones para producción](riesgos-produccion.md).

### Consecuencias

#### Positivas

* Menor costo y menor complejidad de despliegue para la prueba.

#### Negativas

* La solución no está lista para producción tal como está; los riesgos pendientes quedan documentados.

### Cumplimiento

* Cada capacidad excluida aparece como mejora futura y como riesgo para producción.

---

## ADR-040: Cloudscape como librería de componentes del frontend

### Contexto

El frontend en React (ver ADR-005) necesita una librería de componentes para construir la interfaz: conversación, carga de documentos, evaluaciones y visor de logs.

### Decisión

Se usa [Cloudscape Design System](https://cloudscape.design/get-started/), la librería de componentes de código abierto oficial de AWS.

### Consecuencias

#### Positivas

* Componentes listos para la interfaz, sin diseñarlos desde cero.
* Una interfaz consistente con la consola de AWS.

#### Negativas

* La apariencia queda atada al estilo de Cloudscape.

### Cumplimiento

* Los componentes de la interfaz del frontend provienen de Cloudscape.

---

## ADR-041: Documentación de la API con OpenAPI desde API Gateway

### Contexto

La prueba exige documentar el uso de la API. La documentación se puede escribir a mano o generarse a partir de la definición de la API.

### Decisión

La especificación OpenAPI de la API se gestiona desde API Gateway, que permite exportarla. La documentación de uso de cada endpoint se genera con asistencia de IA, porque el comportamiento de cada endpoint es el que se espera de su nombre. Está en [api.md](api.md).

### Consecuencias

#### Positivas

* La especificación se mantiene junto a la definición de la API, sin un documento aparte que se desactualice.

#### Negativas

* La documentación generada se debe revisar cuando cambie un endpoint.

### Cumplimiento

* La especificación OpenAPI se exporta desde API Gateway y [api.md](api.md) describe cada endpoint.

---

## ADR-042: Modelo de datos de las solicitudes

### Contexto

Las herramientas del agente (ver ADR-020) y las solicitudes de ejemplo (ver ADR-025) necesitan un modelo de datos común. El agente debe poder completar la información de una solicitud a medida que avanza la conversación con el usuario.

### Decisión

Cada solicitud tiene estos campos:

| Campo | Tipo | Valores | Valor por defecto |
|---|---|---|---|
| `id` | UUIDv7 | | Se genera al crear la solicitud |
| `description` | Texto | Descripción completa del caso | |
| `summary` | Texto | Resumen del caso, distinto de la descripción | Vacío |
| `priority` | Enumeración | `low`, `medium`, `high` | `unassigned` |
| `effort` | Enumeración | `low`, `medium`, `high` | `unassigned` |
| `status` | Enumeración | `pending`, `in progress`, `delayed`, `done` | `pending` |

Los valores por defecto permiten crear una solicitud solo con su descripción. Luego el agente asigna el resumen, la prioridad, el esfuerzo y el estado correctos según el flujo de la conversación (ver ADR-022).

### Consecuencias

#### Positivas

* El agente puede crear una solicitud de inmediato y completarla durante la conversación.
* Los valores fijos mantienen los datos consistentes.

#### Negativas

* Puede haber solicitudes con prioridad o esfuerzo `unassigned` si la conversación no llega a definirlos.

### Cumplimiento

* Las herramientas de solicitudes y el archivo JSON de solicitudes de ejemplo siguen este modelo, y las herramientas rechazan valores fuera de los permitidos.

---

## ADR-043: Grupos de Cognito para separar administradores y usuarios

### Contexto

El visor de logs muestra las conversaciones de todos los usuarios, y cada evaluación consume modelos y tiempo de Fargate. No todos los usuarios registrados deberían poder ver los logs ni lanzar evaluaciones.

### Decisión

Se usan dos grupos del user pool de Cognito:

* `users`: usuarios normales. Pueden conversar con el asistente y subir sus propios documentos. Todo usuario nuevo entra a este grupo al confirmar su registro, mediante un Lambda *Post Confirmation*.
* `admins`: administradores. Además de lo anterior, pueden leer los logs y lanzar y consultar evaluaciones. Este grupo se asigna a mano en la consola de Cognito, a propósito: ningún flujo de la aplicación convierte a un usuario en administrador.

La API lee el claim `cognito:groups` del ID token y responde `403` en los endpoints de logs y de evaluaciones si el usuario no es administrador. El frontend oculta esas páginas a los usuarios normales.

### Consecuencias

#### Positivas

* Los logs, que incluyen las conversaciones de todos, y las evaluaciones, que tienen costo, quedan restringidos.
* Asignar un administrador es un paso manual y explícito, que no se puede hacer desde la aplicación.

#### Negativas

* Hay que asignar a mano el primer administrador después del despliegue.
* Un cambio de grupo se refleja cuando el usuario obtiene un token nuevo (al volver a iniciar sesión o al renovar el token).

### Cumplimiento

* El user pool tiene los grupos `admins` y `users`, y el trigger *Post Confirmation* agrega a cada usuario nuevo a `users`.
* Los endpoints de logs y de evaluaciones responden `403` a quien no está en `admins`, y el frontend solo muestra esas páginas a los administradores.
