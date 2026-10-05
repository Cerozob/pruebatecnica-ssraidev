import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "./client";

afterEach(() => vi.unstubAllGlobals());

describe("ApiClient", () => {
  it("envía el token de Cognito y usa el id del log group en la ruta", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("linea", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new ApiClient("https://api.example.com/api/", () => "token-123");

    await expect(client.getLogEvents("L2F3cy9sYW1iZGEvZm4", 24, 100)).resolves.toBe("linea");

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://api.example.com/api/logs/groups/L2F3cy9sYW1iZGEvZm4/events?hours=24&limit=100");
    expect(init.headers.Authorization).toBe("token-123");
  });

  it("marca como timeout un 504 de API Gateway y conserva el mensaje del backend", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ message: "Endpoint request timed out" }), { status: 504 })),
    );
    const client = new ApiClient("https://api.example.com/api/", () => undefined);

    const error = await client.sendMessage("id", "hola").catch((caught: ApiError) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).isTimeout).toBe(true);
    expect((error as ApiError).message).toBe("Endpoint request timed out");
  });

  it("trata un fallo de red como timeout para seguir esperando la respuesta", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const client = new ApiClient("https://api.example.com/api/", () => undefined);

    const error = (await client.listConversations().catch((caught) => caught)) as ApiError;
    expect(error.isTimeout).toBe(true);
  });
});
