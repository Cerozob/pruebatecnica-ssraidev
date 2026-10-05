"""Revisión de *prompt injection* en la respuesta del modelo con ApplyGuardrail (ADR-026)."""

GUARDRAIL_INTERVENED = "GUARDRAIL_INTERVENED"


def contains_prompt_attack(client, guardrail_id: str, guardrail_version: str, text: str) -> bool:
    """Indica si el filtro de ataques de prompt detecta una inyección en `text`.

    Bedrock solo aplica ese filtro a contenido de entrada, así que la respuesta se envía con `source="INPUT"`.
    """
    if not text.strip():
        return False
    response = client.apply_guardrail(
        guardrailIdentifier=guardrail_id,
        guardrailVersion=guardrail_version,
        source="INPUT",
        content=[{"text": {"text": text}}],
    )
    return response.get("action") == GUARDRAIL_INTERVENED
