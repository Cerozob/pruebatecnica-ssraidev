import type { EvaluationStatus } from "../api/types";

const AGENT_LABELS: Record<string, string> = {
  conversational_agent: "Conversacional",
  modernization_agent: "Modernización",
  cloud_recommender_agent: "Recomendador cloud",
};

export function agentLabel(agent: string): string {
  return AGENT_LABELS[agent] ?? agent;
}

export function formatDate(iso?: string): string {
  if (!iso) return "-";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString("es-CO");
}

export function formatPercent(value: number | null | undefined): string {
  return value === null || value === undefined ? "-" : `${Math.round(value * 100)} %`;
}

export function statusType(status: EvaluationStatus): "pending" | "in-progress" | "success" | "error" {
  switch (status) {
    case "PENDING":
      return "pending";
    case "RUNNING":
      return "in-progress";
    case "COMPLETED":
      return "success";
    case "FAILED":
      return "error";
  }
}

export const STATUS_LABELS: Record<EvaluationStatus, string> = {
  PENDING: "Pendiente",
  RUNNING: "En ejecución",
  COMPLETED: "Completada",
  FAILED: "Fallida",
};

export const CATEGORY_LABELS: Record<string, string> = {
  accuracy: "Precisión y groundedness",
  insufficient_information: "Información insuficiente",
  prompt_injection: "Prompt injection",
};

/** Título corto para una conversación nueva, antes de que el backend devuelva el suyo. */
export function conversationTitle(text: string, maxLength = 80): string {
  const singleLine = text.replace(/\s+/g, " ").trim();
  return singleLine.length > maxLength ? `${singleLine.slice(0, maxLength - 1)}…` : singleLine;
}

export function isActiveEvaluation(status: EvaluationStatus): boolean {
  return status === "PENDING" || status === "RUNNING";
}

/** Título que el backend asigna a una conversación: el primer mensaje en una línea, hasta 80 caracteres. */
export function backendTitle(content: string): string {
  return content.split(/\s+/).filter(Boolean).join(" ").slice(0, 80);
}

// Margen para diferencias de reloj entre el navegador y el backend.
const CLOCK_SKEW_MS = 60_000;

/** La conversación que creó un primer mensaje cortado por timeout: mismo título y creada después de enviarlo. */
export function findNewConversation(
  conversations: { conversationId: string; title: string; createdAt?: string }[],
  content: string,
  sentAt: string,
): string | null {
  const title = backendTitle(content);
  const earliest = new Date(sentAt).getTime() - CLOCK_SKEW_MS;
  const match = conversations.find(
    (conversation) =>
      conversation.title === title && new Date(conversation.createdAt ?? 0).getTime() >= earliest,
  );
  return match?.conversationId ?? null;
}
