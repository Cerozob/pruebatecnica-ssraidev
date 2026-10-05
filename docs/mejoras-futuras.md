# Mejoras Futuras

Mejoras identificadas durante el diseño que no se implementaron, en su mayoría por simplicidad o por costo. Cada una enlaza a la decisión de arquitectura que la origina. Salvo las de [nuevos canales](#nuevos-canales), cada mejora responde a un riesgo descrito en [riesgos y consideraciones para producción](riesgos-produccion.md).

## API

* **Migrar la API a ECS Fargate con un ALB** cuando la carga sea sostenida y de mayor escala. A esa escala es más rentable que Lambda, y los handlers actuales se pueden reutilizar sin reimplementarse ([ADR-003](decisiones_full.md#adr-003-api-con-lambdas-de-powertools-detrás-de-api-gateway)).

## Ingesta documental

* **Carga multiparte** para documentos muy grandes y para reanudar cargas interrumpidas ([ADR-009](decisiones_full.md#adr-009-carga-de-documentos-directa-a-s3-con-urls-prefirmadas)).
* **Sincronización programada** de la base de conocimiento, junto a la sincronización por eventos ([ADR-010](decisiones_full.md#adr-010-sincronización-de-la-base-de-conocimiento-por-eventos)).
* **Reintento de las sincronizaciones que terminan con error**; los cambios ocurridos durante una sincronización ya se reintentan ([ADR-010](decisiones_full.md#adr-010-sincronización-de-la-base-de-conocimiento-por-eventos)).

## Conversación

* **Respuestas en *streaming*** para mejorar la latencia percibida ([ADR-018](decisiones_full.md#adr-018-respuestas-síncronas)).

## Modelo

* **Un modelo de mayor calidad** para los agentes, como Claude Sonnet, si los resultados de la evaluación o el presupuesto lo justifican ([ADR-016](decisiones_full.md#adr-016-amazon-nova-2-lite-como-modelo-de-lenguaje)).
* **Un modelo juez de otra familia** distinta a la de los agentes, para eliminar el sesgo de autoevaluación ([ADR-032](decisiones_full.md#adr-032-amazon-nova-2-lite-también-como-modelo-juez)).
* **Un modelo de decisión especializado para la prioridad y el esfuerzo**, como Strands Decider en un endpoint de SageMaker con GPU o en Fargate, si el volumen de solicitudes lo justifica y se mide su precisión con solicitudes reales en español ([ADR-022](decisiones_full.md#adr-022-prioridad-y-esfuerzo-los-decide-el-llm-con-niveles-fijos)).

## Seguridad

* **Eliminar los permisos con wildcards restantes** de los roles IAM, salvo las lecturas de S3 de la base de conocimiento y los permisos obligatorios ([ADR-028](decisiones_full.md#adr-028-roles-iam-de-mínimo-privilegio-con-comodines-solo-cuando-son-inevitables)).
* **Aislamiento de datos por usuario** y soporte *multi-tenant* para documentos y solicitudes; las conversaciones ya son privadas por usuario ([ADR-029](decisiones_full.md#adr-029-respuestas-fundamentadas-con-referencias-obligatorias-y-conversaciones-privadas-por-usuario), [ADR-039](decisiones_full.md#adr-039-capacidades-de-producción-fuera-del-alcance-por-simplicidad-y-costo)).
* **AWS WAF** frente a CloudFront y API Gateway ([ADR-039](decisiones_full.md#adr-039-capacidades-de-producción-fuera-del-alcance-por-simplicidad-y-costo)).
* **Despliegue en una VPC** para los componentes que lo admitan, con *endpoints* privados hacia los servicios de AWS ([ADR-039](decisiones_full.md#adr-039-capacidades-de-producción-fuera-del-alcance-por-simplicidad-y-costo)).

* **Amazon Macie** para identificar PII en los documentos cargados a S3, con acciones de remediación como alertas por Amazon SNS ([ADR-039](decisiones_full.md#adr-039-capacidades-de-producción-fuera-del-alcance-por-simplicidad-y-costo)).
* **Análisis estático de vulnerabilidades** del código de los Lambdas, los contenedores y los agentes, por ejemplo con Amazon Inspector ([ADR-039](decisiones_full.md#adr-039-capacidades-de-producción-fuera-del-alcance-por-simplicidad-y-costo)).

## Gobernanza

* **Registro de agentes:** un registro de agentes propio, o una entrada en el registro corporativo existente si lo hay, para trazabilidad y gobernanza ([ADR-039](decisiones_full.md#adr-039-capacidades-de-producción-fuera-del-alcance-por-simplicidad-y-costo)).
* **Etiquetas, metadatos y controles de gobernanza** para los datos ingeridos, en todos los componentes ([ADR-039](decisiones_full.md#adr-039-capacidades-de-producción-fuera-del-alcance-por-simplicidad-y-costo)).

## Despliegue

* ***Pipeline* de CI/CD** que ejecute cdk-nag, el análisis de vulnerabilidades, las pruebas y el despliegue ([ADR-039](decisiones_full.md#adr-039-capacidades-de-producción-fuera-del-alcance-por-simplicidad-y-costo)).
* **Varios entornos** (por ejemplo, desarrollo, pruebas y producción) ([ADR-039](decisiones_full.md#adr-039-capacidades-de-producción-fuera-del-alcance-por-simplicidad-y-costo)).
* **Dominio propio** para el frontend y la API ([ADR-039](decisiones_full.md#adr-039-capacidades-de-producción-fuera-del-alcance-por-simplicidad-y-costo)).

## Observabilidad

* ***Dashboards* dedicados de CloudWatch** para la solución ([ADR-039](decisiones_full.md#adr-039-capacidades-de-producción-fuera-del-alcance-por-simplicidad-y-costo)).
* **CloudWatch Application Signals** para monitorear la salud de los servicios ([ADR-039](decisiones_full.md#adr-039-capacidades-de-producción-fuera-del-alcance-por-simplicidad-y-costo)).
* **Trazabilidad completa de logs y AWS X-Ray** para seguir una petición a través de todos los componentes ([ADR-039](decisiones_full.md#adr-039-capacidades-de-producción-fuera-del-alcance-por-simplicidad-y-costo)).
* **Métricas y alarmas en CloudWatch** ([ADR-039](decisiones_full.md#adr-039-capacidades-de-producción-fuera-del-alcance-por-simplicidad-y-costo)).
* **Monitoreo en el frontend de los procesos asíncronos**, como las sincronizaciones de la base de conocimiento y las ejecuciones de evaluación ([ADR-039](decisiones_full.md#adr-039-capacidades-de-producción-fuera-del-alcance-por-simplicidad-y-costo)).

## Nuevos canales

* **Integración con Amazon Connect** mediante los agentes de IA de Connect, reutilizando este sistema agéntico y sus herramientas. Así se agrega soporte por voz, aunque el caso de uso y el modelo no lo contemplaran inicialmente, y mejores canales de comunicación para los usuarios finales, como una línea telefónica, correo electrónico y WhatsApp.
