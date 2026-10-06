# Riesgos y Consideraciones para Producción

Esta sección contiene los riesgos al ir a producción, la mayoría son básicamente los *tradeoffs* de la sección anterior de [mejoras futuras](mejoras-futuras.md) a excepción de los canales de Amazon Connect. Además, se incluye un resumen de algunas consideraciones que se mitigaron porque incluso a un prototipo de esta escala vale la pena revisar y evitar.

## Riesgos mitigados en la solución

* ***Prompt injection*:** Bedrock Guardrails bloquea los ataques en el mensaje del usuario y en la respuesta del modelo, y el usuario recibe un mensaje de bloqueo ([ADR-026](decisiones_full.md#adr-026-bedrock-guardrails-solo-para-detectar-prompt-injection)).
* **Respuestas no fundamentadas:** las respuestas citan sus fuentes y el agente responde "no tengo esa información" cuando no hay contexto relevante ([ADR-029](decisiones_full.md#adr-029-respuestas-fundamentadas-con-referencias-obligatorias-y-conversaciones-privadas-por-usuario)). La evaluación agéntica lo verifica ([ADR-030](decisiones_full.md#adr-030-evaluación-agéntica-con-strands-evals-y-agentcore-evaluations)).
* **Acciones destructivas del agente:** no existe la operación de eliminar solicitudes ([ADR-021](decisiones_full.md#adr-021-sin-operación-de-eliminación-de-solicitudes)).
* **Registro de usuarios no autorizados:** solo se pueden registrar correos y dominios permitidos ([ADR-007](decisiones_full.md#adr-007-registro-restringido-con-un-lambda-pre-signup)).
* **Acceso indebido a logs y evaluaciones:** solo el grupo de administradores de Cognito, asignado a mano, puede leer los logs y lanzar evaluaciones ([ADR-043](decisiones_full.md#adr-043-grupos-de-cognito-para-separar-administradores-y-usuarios)).
* **Evaluaciones lanzadas en masa por error:** solo puede haber una evaluación en curso ([ADR-031](decisiones_full.md#adr-031-step-functions-para-orquestar-la-evaluación)).
* **Documentos perdidos durante una sincronización:** los cambios ocurridos durante una sincronización se reintentan hasta quedar incluidos ([ADR-010](decisiones_full.md#adr-010-sincronización-de-la-base-de-conocimiento-por-eventos)).
* **Exposición de secretos:** los valores sensibles están en Secrets Manager ([ADR-027](decisiones_full.md#adr-027-secrets-manager-para-los-correos-y-dominios-permitidos)).

## Riesgos pendientes

### API

* **Costo a escala sostenida:** con carga alta y constante, Lambda puede ser más costoso que contenedores. Mitigación: [migrar a ECS Fargate con un ALB](mejoras-futuras.md#api).

### Ingesta documental

* **Documentos de más de 50 MB:** la base de conocimiento no admite archivos de más de 50 MB, así que un documento más grande se debe dividir a mano antes de cargarlo. Mitigación: dividir automáticamente los documentos grandes antes de la ingesta.
* **Formatos no soportados:** los formatos que la base de conocimiento no procesa, como video o audio, requieren un procesamiento manual antes de cargarlos. Mitigación: Amazon Bedrock Data Automation para extraer su contenido.

### Conversación

* **Latencia percibida:** con respuestas síncronas, el usuario no ve nada hasta que la respuesta está completa. Mitigación: [respuestas en *streaming*](mejoras-futuras.md#conversación).
* **Límite de 29 s de API Gateway:** las API REST de API Gateway cortan la respuesta a los 29 s, un límite fijo. En los flujos en los que las acciones del agente o su razonamiento superan ese tiempo, el usuario no recibe la respuesta en la misma petición, aunque el turno se guarda. Mitigación: invocar AgentCore Runtime directamente desde el frontend con el SDK de AWS, lo que es necesario para esos flujos.

### Modelo

* **Respuestas de menor calidad:** Amazon Nova 2 Lite se eligió por costo y puede razonar, usar herramientas y coordinar el *swarm* peor que un modelo más grande. Mitigación: [un modelo de mayor calidad](mejoras-futuras.md#modelo).
* **Sesgo de autoevaluación:** el juez de la evaluación es el mismo modelo que los agentes, así que puede calificar de más sus respuestas. Mitigación: [un juez de otra familia de modelos](mejoras-futuras.md#modelo).
* **Prioridad y esfuerzo no reproducibles:** los decide el LLM y la misma solicitud puede recibir niveles distintos, sin una confianza asociada. Mitigación: [un modelo de decisión especializado](mejoras-futuras.md#modelo), por ejemplo uno que clasifique "el portal de pagos no carga para ningún cliente" como prioridad alta y esfuerzo medio, con una confianza asociada. No se usó un modelo como Strands Decider por razones de costo, pero sería un caso de uso perfecto para él.

### Seguridad

* **Permisos más amplios de lo necesario:** los comodines que queden en IAM amplían el acceso de algunos roles. Mitigación: [eliminar los comodines restantes](mejoras-futuras.md#seguridad).
* **Fuga de datos entre usuarios:** sin aislamiento por usuario ni soporte *multi-tenant*, cualquier usuario autenticado ve todos los documentos y solicitudes. Las conversaciones sí son privadas por usuario. Mitigación: [aislamiento de datos por usuario](mejoras-futuras.md#seguridad).
* **Tráfico malicioso:** sin AWS WAF, la única protección ante tráfico abusivo es la limitación de tasa de API Gateway. Mitigación: [AWS WAF](mejoras-futuras.md#seguridad).
* **Superficie de red pública:** sin VPC, los componentes se comunican por *endpoints* públicos de AWS. Mitigación: [despliegue en una VPC](mejoras-futuras.md#seguridad).

* **Exposición de PII en los documentos:** no se detecta información personal en los documentos cargados, que luego puede aparecer en las respuestas del agente. Mitigación: [Amazon Macie con alertas](mejoras-futuras.md#seguridad).
* **Vulnerabilidades en el código y sus dependencias:** no se analiza el código de los Lambdas, los contenedores ni los agentes. Mitigación: [análisis estático de vulnerabilidades](mejoras-futuras.md#seguridad).

### Gobernanza

* **Agentes sin inventario:** no hay un registro de los agentes, de sus herramientas ni de sus responsables, lo que dificulta la trazabilidad y la gobernanza. Mitigación: [registro de agentes](mejoras-futuras.md#gobernanza).
* **Datos sin clasificar:** los datos ingeridos no tienen etiquetas, metadatos ni controles de gobernanza, así que no se puede saber su origen, su sensibilidad ni quién puede usarlos. Mitigación: [etiquetas, metadatos y controles de gobernanza](mejoras-futuras.md#gobernanza).

### Despliegue

* **Errores manuales en el despliegue:** sin CI/CD, el despliegue depende de pasos manuales. Mitigación: [*pipeline* de CI/CD](mejoras-futuras.md#despliegue).
* **Cambios sin probar en producción:** con un solo entorno, no hay dónde probar los cambios antes de desplegarlos. Mitigación: [varios entornos](mejoras-futuras.md#despliegue).
* **URLs generadas por AWS:** sin dominio propio, el frontend y la API usan las URLs de CloudFront y API Gateway. Mitigación: [dominio propio](mejoras-futuras.md#despliegue).

### Observabilidad

* **Fallos detectados tarde:** sin métricas, alarmas ni *dashboards*, los problemas se descubren revisando los logs a mano. Mitigación: [*dashboards*, métricas y alarmas](mejoras-futuras.md#observabilidad).
* **Depuración difícil entre componentes:** sin X-Ray ni Application Signals, seguir una petición a través de API Gateway, Lambda, AgentCore y Bedrock es costoso. Mitigación: [trazabilidad completa y X-Ray](mejoras-futuras.md#observabilidad).
* **Procesos asíncronos opacos:** el usuario no ve en el frontend el estado de las sincronizaciones de la base de conocimiento ni de las evaluaciones. Mitigación: [monitoreo de procesos asíncronos en el frontend](mejoras-futuras.md#observabilidad).

## Otras consideraciones

* **Una sola ejecución de la evaluación:** los resultados de la evaluación incluidos en la entrega corresponden a una sola ejecución. El modelo no es determinista, así que otra ejecución puede dar resultados distintos.
* **Intensidad del guardrail:** el guardrail usa intensidad `LOW` porque con intensidades mayores bloqueaba el contexto propio del *swarm* y conversaciones válidas ([ADR-026](decisiones_full.md#adr-026-bedrock-guardrails-solo-para-detectar-prompt-injection)). Con esa intensidad, la evaluación de la entrega bloqueó 1 de 4 ataques de *prompt injection*.
* **Elementos fuera del diagrama:** AgentCore Memory y los grupos de Cognito no se dibujan a propósito; se describen en la arquitectura y en las decisiones técnicas.
