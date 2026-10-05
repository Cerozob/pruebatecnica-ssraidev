# Documentación de la API

La API es una API REST de Amazon API Gateway (ver [ADR-008](decisiones_full.md#adr-008-api-rest-de-api-gateway-en-lugar-de-http-api)). Cada endpoint es un Lambda de Powertools (ver [ADR-003](decisiones_full.md#adr-003-api-con-lambdas-de-powertools-detrás-de-api-gateway)). La especificación OpenAPI completa se exporta desde API Gateway (ver [ADR-041](decisiones_full.md#adr-041-documentación-de-la-api-con-openapi-desde-api-gateway)).

## Autenticación

Todos los endpoints exigen el ID token de Amazon Cognito en el encabezado `Authorization`. El *authorizer* de Cognito rechaza las peticiones sin un token válido con `401`.

## Endpoints

### Conversación

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/conversations` | Envía el primer mensaje de una conversación nueva y devuelve la respuesta del asistente, con las fuentes usadas, y el `conversationId`. Cuerpo: `{"content": "..."}` (1 a 4000 caracteres). |
| `POST` | `/conversations/{conversationId}/messages` | Envía un mensaje a una conversación existente del usuario y devuelve la respuesta del asistente, con las fuentes usadas. Cuerpo: `{"content": "..."}`. |
| `GET` | `/conversations` | Lista las conversaciones del usuario, la más reciente primero. |
| `GET` | `/conversations/{conversationId}` | Devuelve el historial de mensajes de una conversación del usuario. |

El `conversationId` es el `runtimeSessionId` de Amazon Bedrock AgentCore Runtime. El primer mensaje se envía al runtime sin sesión: AgentCore crea una y devuelve su id, que la API devuelve como `conversationId`. Los mensajes siguientes usan ese id, y el runtime conserva el contexto de la conversación; la API solo reenvía cada mensaje y registra el turno para el historial. Cada usuario solo ve y continúa sus propias conversaciones.

La respuesta es síncrona (ver [ADR-018](decisiones_full.md#adr-018-respuestas-síncronas)). Si tarda más de 29 segundos, API Gateway responde `504`, pero el backend termina el turno y lo guarda: el cliente puede consultar `GET /conversations/{conversationId}` (o, en el primer mensaje, `GET /conversations`) hasta que aparezca la respuesta.

### Documentos

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/documents/upload-url` | Devuelve una URL prefirmada para subir un documento directamente al bucket de S3. La carga dispara la sincronización de la base de conocimiento. |
| `POST` | `/knowledge-base/sync` | Lanza una sincronización manual de la base de conocimiento. Si ya hay una en curso, no lanza otra. |

### Logs

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/logs/groups` | Lista los *log groups* de CloudWatch que tienen las etiquetas de la aplicación, cada uno con `name` e `id`. |
| `GET` | `/logs/groups/{logGroupId}/events` | Devuelve los eventos de un *log group* como texto plano, los más recientes al final. Parámetros opcionales: `hours` (1 a 168, por defecto 24) y `limit` (1 a 1000, por defecto 200). |

El `logGroupId` es el nombre del *log group* en base64url, porque los nombres tienen barras y las REST APIs decodifican los parámetros de la ruta antes de pasarlos al backend.

### Evaluaciones

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/evaluations` | Inicia una evaluación agéntica. |
| `GET` | `/evaluations` | Lista las evaluaciones anteriores y su estado. |
| `GET` | `/evaluations/{evaluationId}` | Devuelve el progreso y los resultados de una evaluación. |

Las solicitudes no tienen endpoints: solo se gestionan a través del agente (ver [ADR-025](decisiones_full.md#adr-025-datos-de-ejemplo-con-bucketdeployment-y-un-custom-resource)).

## Errores

| Código | Cuándo |
|---|---|
| `400` | La petición no cumple el esquema esperado. |
| `401` | Falta el token o no es válido. |
| `404` | El recurso no existe o no pertenece al usuario. |
| `429` | Se superó el límite de tasa de API Gateway. |
| `500` | Error interno. |
| `502` | El asistente no pudo responder. |
| `504` | La respuesta tardó más de 29 segundos; ver la nota de conversación. |
