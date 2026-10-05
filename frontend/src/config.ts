/** Configuración de runtime que CDK publica como /config.json junto al frontend. */
export interface RuntimeConfig {
  region: string;
  apiUrl: string;
  userPoolId: string;
  userPoolClientId: string;
  cognitoDomain: string;
}

const REQUIRED_KEYS: (keyof RuntimeConfig)[] = ["region", "apiUrl", "userPoolId", "userPoolClientId", "cognitoDomain"];

export function parseConfig(raw: unknown): RuntimeConfig {
  if (typeof raw !== "object" || raw === null) {
    throw new Error("config.json no es un objeto JSON");
  }
  const record = raw as Record<string, unknown>;
  for (const key of REQUIRED_KEYS) {
    if (typeof record[key] !== "string" || record[key] === "") {
      throw new Error(`config.json: falta el valor '${key}'`);
    }
  }
  const config = record as unknown as RuntimeConfig;
  return { ...config, apiUrl: config.apiUrl.endsWith("/") ? config.apiUrl : `${config.apiUrl}/` };
}

export async function loadConfig(): Promise<RuntimeConfig> {
  const response = await fetch("/config.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`No se pudo cargar config.json (${response.status})`);
  }
  return parseConfig(await response.json());
}
