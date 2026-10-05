import { describe, expect, it } from "vitest";
import {
  agentLabel,
  backendTitle,
  conversationTitle,
  findNewConversation,
  formatPercent,
  isActiveEvaluation,
  statusType,
} from "./format";

describe("format", () => {
  it("traduce los nombres de los agentes y deja los desconocidos igual", () => {
    expect(agentLabel("cloud_recommender_agent")).toBe("Recomendador cloud");
    expect(agentLabel("otro")).toBe("otro");
  });

  it("formatea proporciones como porcentaje y muestra guion si no hay valor", () => {
    expect(formatPercent(0.8333)).toBe("83 %");
    expect(formatPercent(null)).toBe("-");
    expect(formatPercent(undefined)).toBe("-");
  });

  it("acorta el título de una conversación nueva a una sola línea", () => {
    expect(conversationTitle("  hola\n  mundo ")).toBe("hola mundo");
    expect(conversationTitle("a".repeat(100), 10)).toBe(`${"a".repeat(9)}…`);
  });

  it("solo considera activas las evaluaciones pendientes o en ejecución", () => {
    expect(isActiveEvaluation("PENDING")).toBe(true);
    expect(isActiveEvaluation("RUNNING")).toBe(true);
    expect(isActiveEvaluation("COMPLETED")).toBe(false);
    expect(statusType("FAILED")).toBe("error");
  });
});

describe("findNewConversation", () => {
  const sentAt = "2026-10-05T10:00:00.000Z";

  it("encuentra la conversación creada por el primer mensaje", () => {
    const items = [
      { conversationId: "vieja", title: "Hola  mundo", createdAt: "2026-10-04T10:00:00.000Z" },
      { conversationId: "nueva", title: "Hola mundo", createdAt: "2026-10-05T10:00:05.000Z" },
    ];
    expect(findNewConversation(items, "  Hola\n mundo ", sentAt)).toBe("nueva");
  });

  it("no confunde una conversación anterior con el mismo título", () => {
    const items = [{ conversationId: "vieja", title: "Hola", createdAt: "2026-10-04T10:00:00.000Z" }];
    expect(findNewConversation(items, "Hola", sentAt)).toBeNull();
  });

  it("usa el mismo recorte de título que el backend", () => {
    expect(backendTitle("a ".repeat(100))).toHaveLength(80);
  });
});
