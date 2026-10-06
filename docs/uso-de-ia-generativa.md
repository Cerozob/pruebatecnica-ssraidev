# Documento de reporte de uso de IA Generativa

* Autor: **Camilo Rozo**
* Disclaimer: en este documento en particular, la redacción es 100% humana

## 1. Herramientas de IA Generativa Utilizadas

* Claude ai
* Claude Code
* Claude Cowork
* Kiro

## 2. Qué tareas apoyo con AI

Prácticamente todo excepto por la planeación y el diseño en sí de la solución. El código fue asistido por claude code y Kiro, y el testing, troubleshooting y demás tareas de implementación fueron asistidas o realizadas por subagentes de IA.

Asimismo, la redacción formal y compilación de documentación fue asistida por IA Generativa.

## 3. Qué validaciones realizo sobre el código generado

Generación de pruebas, pruebas end to end manuales en AWS. Checks contra mejores prácticas de AWS. La revisión manual fue agilizada por medio de reportes. Yo diseñé todo lo más específico posible, por lo que el agente de IA es capaz de comparar la implementación contra la arquitectura Y el constraint impuesto, y en caso de desviarse, anotarlo en un backlog que yo puedo monitorear constantemente.

## 4. Qué riesgos identificó

El overengineering: el código generado siempre tiende a la sobreingeniería y sobrepensamiento de edge cases, timeouts, resiliencia y demás. Muchas de las decisiones de arquitectura tienen como razón principal el "por simplicidad", y a pesar de esto, se compone igualmente un asistente realmente complejo en comparación con lo mínimo viable para aprobar la prueba.

La desviación: Es natural que el Agente asuma cosas en situaciones ambiguas, ahora, no siempre se detiene a preguntar, por lo que en caso de desviarse, es necesario frenar o trackear las desviaciones para asegurarse de que el producto final SÍ cumpla con el objetivo planteado en la etapa de diseño. Esto es más notorio al vibecodear, es decir, al implementar sin el previo proceso de diseño.

Sobredocumentación: No tiene sentido documentar temas en el código que no están, para eso son las decisiones de diseño. Frecuentemente, al corregir un Agente de IA, el resultado es código corregido PERO con un agregado de un comentario de "ya no se hace XYZ, sino ABC", donde el XYZ es el problema anterior y ABC la corrección. Esto agranda el código un montón. Adicionalmente, la documentación autogenerada es muy buena porque es detallada, pero sí se corre el riesgo de inflar demasiado el repositorio con archivos markdown que nadie va a leer. Kiro es un especial culpable de esto, cada corrección, feature o arreglito termina en documentos markdown, y fácilmente se pueden llegar a 20 o 30 markdowns con texto y texto que capaz y no se necesita más.

## 5. Cómo evitó depender ciegamente de la herramienta

* Primero, encargándome del diseño completo, de esa forma evito el bias del agente de IA por su implementación de preferencia (ej: si le hago una pregunta y toma un repositorio de contexto que podría desviar mi propio proceso de pensamiento).
* Responder con prompts: el agente me pregunta cosas y sugiere opciones recomendando UNA. Prefiero siempre responder en mis palabras de forma que las respuestas autogeneradas no generen un sesgo.
* Segundo, evitando el modo AUTO. En claude code por ejemplo hay un modo full autónomo que no me pregunta nada, es muy veloz y trabaja solo, pero yo como desarrollador quedo a ciegas. Entonces hay que evitar dejar los agentes sin supervisión y evitar autoejecutar comandos sensibles
* Cuestionar todo: en las decisiones de arquitectura se nota esta parte, el documento y la redacción es del LLM, pero el proceso es que el LLM me cuestione mis decisiones según documentación de mejores prácticas, de ese modo permito verificar que YO estoy alineado con las mejores prácticas, en especial si es un proyecto en el que mi experticia se vea limitada

* Preguntas retóricas: Una técnica que me funciona bien es que le pregunto al agente o le propongo acciones, features o cuestionamientos que yo ya sé de antemano la respuesta, de esa forma verifico que el agente y el desarrollo actual sigue estando alineado. Incluso a través de agentes, sesiones y entornos de ejecución.
