# Discrepancias y supuestos

Solo quedan los puntos abiertos. Los que ya revisaste se resolvieron y quedaron documentados en los ADR, el README y `docs/api.md`. Cada entrada dice qué no estaba claro, qué se eligió y dónde vive en el código.

1. **Lista de dominios permitidos de la búsqueda web.** `domainFilter.include` requiere el conector `web-search` 1.2.0 o posterior, y CloudFormation no permite fijar la versión del conector; se asume que la versión por defecto lo admite. Lo vas a verificar en el despliegue. — `pruebatecnica/stacks/agents_stack.py` (`WebSearchTarget`)
2. **Primer mensaje que supera los 29 s de API Gateway.** Como el `sessionId` lo asigna AgentCore, la conversación solo se registra cuando el runtime responde. Si API Gateway corta antes, el Lambda termina igual y la registra; el frontend la encuentra en `GET /conversations` (mismo título y creada después del envío) y muestra la respuesta. — `backend/common/chat.py`, `frontend/src/pages/ChatPage.tsx`, `frontend/src/utils/format.ts`
3. **Formato del `conversationId` en la ruta.** AgentCore solo documenta que el `runtimeSessionId` tiene entre 33 y 256 caracteres, no su formato. La API acepta ese rango, sin barras ni espacios. — `backend/common/conversations.py` (`SESSION_ID_PATTERN`)
