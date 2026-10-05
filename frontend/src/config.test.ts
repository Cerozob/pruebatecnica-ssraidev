import { describe, expect, it } from "vitest";
import { parseConfig } from "./config";

const valid = {
  region: "us-east-1",
  apiUrl: "https://abc.execute-api.us-east-1.amazonaws.com/api",
  userPoolId: "us-east-1_abc",
  userPoolClientId: "client",
  cognitoDomain: "demo.auth.us-east-1.amazoncognito.com",
};

describe("parseConfig", () => {
  it("normaliza la URL de la API con barra final", () => {
    expect(parseConfig(valid).apiUrl).toBe("https://abc.execute-api.us-east-1.amazonaws.com/api/");
  });

  it("rechaza una configuración incompleta", () => {
    expect(() => parseConfig({ ...valid, userPoolId: "" })).toThrow("userPoolId");
    expect(() => parseConfig(null)).toThrow();
  });
});
