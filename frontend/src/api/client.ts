import type {
  Conversation,
  ConversationSummary,
  Evaluation,
  EvaluationSummary,
  LogGroup,
  SendMessageResponse,
  UploadUrlResponse,
} from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }

  /** API Gateway corta la integración a los 29 s, pero el backend sigue y guarda la respuesta. */
  get isTimeout(): boolean {
    return this.status === 504 || this.status === 0;
  }
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.message === "string") return body.message;
  } catch {
    // El cuerpo no es JSON.
  }
  return `Error ${response.status}`;
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly getToken: () => string | undefined;

  constructor(baseUrl: string, getToken: () => string | undefined) {
    this.baseUrl = baseUrl;
    this.getToken = getToken;
  }

  private async request(path: string, init: RequestInit = {}): Promise<Response> {
    const token = this.getToken();
    let response: Response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
        ...init,
        headers: {
          ...(init.body ? { "Content-Type": "application/json" } : {}),
          ...(token ? { Authorization: token } : {}),
          ...init.headers,
        },
      });
    } catch {
      // Un corte de red o de CORS en un 504 llega como TypeError sin estado.
      throw new ApiError(0, "No hubo respuesta del servidor.");
    }
    if (!response.ok) {
      throw new ApiError(response.status, await errorMessage(response));
    }
    return response;
  }

  private async json<T>(path: string, init?: RequestInit): Promise<T> {
    return (await this.request(path, init)).json() as Promise<T>;
  }

  listConversations(): Promise<{ conversations: ConversationSummary[] }> {
    return this.json("conversations");
  }

  getConversation(conversationId: string): Promise<Conversation> {
    return this.json(`conversations/${conversationId}`);
  }

  /** Primer mensaje: el backend crea la conversación y su sessionId de AgentCore. */
  createConversation(content: string): Promise<SendMessageResponse> {
    return this.json("conversations", { method: "POST", body: JSON.stringify({ content }) });
  }

  sendMessage(conversationId: string, content: string): Promise<SendMessageResponse> {
    return this.json(`conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    });
  }

  createUploadUrl(file: File): Promise<UploadUrlResponse> {
    return this.json("documents/upload-url", {
      method: "POST",
      body: JSON.stringify({
        fileName: file.name,
        contentType: file.type || "application/octet-stream",
        size: file.size,
      }),
    });
  }

  listLogGroups(): Promise<{ logGroups: LogGroup[] }> {
    return this.json("logs/groups");
  }

  /** El id es el nombre en base64url, que no se altera en la ruta de API Gateway. */
  async getLogEvents(logGroupId: string, hours: number, limit: number): Promise<string> {
    const params = new URLSearchParams({ hours: String(hours), limit: String(limit) });
    const response = await this.request(`logs/groups/${logGroupId}/events?${params}`);
    return response.text();
  }

  startEvaluation(): Promise<EvaluationSummary> {
    return this.json("evaluations", { method: "POST" });
  }

  listEvaluations(): Promise<{ evaluations: EvaluationSummary[] }> {
    return this.json("evaluations");
  }

  getEvaluation(evaluationId: string): Promise<Evaluation> {
    return this.json(`evaluations/${evaluationId}`);
  }
}

/** Sube el archivo directo a S3 con la URL prefirmada (ADR-009). */
export async function uploadToS3(upload: UploadUrlResponse, file: File): Promise<void> {
  const response = await fetch(upload.uploadUrl, {
    method: "PUT",
    headers: { "Content-Type": upload.contentType },
    body: file,
  });
  if (!response.ok) {
    throw new ApiError(response.status, `S3 rechazó la carga (${response.status})`);
  }
}
