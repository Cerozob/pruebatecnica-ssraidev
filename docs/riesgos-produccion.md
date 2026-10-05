# Riesgos y Consideraciones para Producción

Riesgos de llevar la solución a producción tal como está. Cada riesgo pendiente es la contraparte de una [mejora futura](mejoras-futuras.md), que sería su mitigación. Las mejoras de [nuevos canales](mejoras-futuras.md#nuevos-canales) amplían la solución y no responden a un riesgo.

## Riesgos mitigados en la solución

* ***Prompt injection*:** Bedrock Guardrails bloquea los ataques y el usuario recibe un mensaje de bloqueo ([ADR-026](decisiones_full.md#adr-026-bedrock-guardrails-solo-para-detectar-prompt-injection)).
* **Respuestas no fundamentadas:** las respuestas citan sus fuentes y el agente responde "no tengo esa información" cuando no hay contexto relevante ([ADR-029](decisiones_full.md#adr-029-respuestas-fundamentadas-con-referencias-obligatorias-y-conversaciones-privadas-por-usuario)). La evaluación agéntica lo verifica ([ADR-030](decisiones_full.md#adr-030-evaluación-agéntica-con-strands-evals-y-agentcore-evaluations)).
* **Acciones destructivas del agente:** no existe la operación de eliminar solicitudes ([ADR-021](decisiones_full.md#adr-021-sin-operación-de-eliminación-de-solicitudes)).
* **Registro de usuarios no autorizados:** solo se pueden registrar correos y dominios permitidos ([ADR-007](decisiones_full.md#adr-007-registro-restringido-con-un-lambda-pre-signup)).
* **Exposición de secretos:** los valores sensibles están en Secrets Manager ([ADR-027](decisiones_full.md#adr-027-secrets-manager-para-los-correos-y-dominios-permitidos)).

## Riesgos pendientes

### API

* **Costo a escala sostenida:** con carga alta y constante, Lambda puede ser más costoso que contenedores. Mitigación: [migrar a ECS Fargate con un ALB](mejoras-futuras.md#api).

### Ingesta documental

* **Cargas grandes interrumpidas:** sin carga multiparte, una carga fallida de un documento grande se debe repetir completa. Mitigación: [carga multiparte](mejoras-futuras.md#ingesta-documental).
* **Documentos no disponibles:** si una sincronización falla, no se reintenta y los documentos no quedan disponibles para el agente. Mitigación: [sincronización programada y cola de reintentos](mejoras-futuras.md#ingesta-documental).

### Conversación

* **Latencia percibida:** con respuestas síncronas, el usuario no ve nada hasta que la respuesta está completa. Mitigación: [respuestas en *streaming*](mejoras-futuras.md#conversación).

### Modelo

* **Respuestas de menor calidad:** Amazon Nova 2 Lite se eligió por costo y puede razonar, usar herramientas y coordinar el *swarm* peor que un modelo más grande. Mitigación: [un modelo de mayor calidad](mejoras-futuras.md#modelo).
* **Sesgo de autoevaluación:** el juez de la evaluación es el mismo modelo que los agentes, así que puede calificar de más sus respuestas. Mitigación: [un juez de otra familia de modelos](mejoras-futuras.md#modelo).

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
