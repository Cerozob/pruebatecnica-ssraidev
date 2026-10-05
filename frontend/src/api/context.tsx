import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useAuth } from "react-oidc-context";
import { ApiClient } from "./client";

const ApiContext = createContext<ApiClient | null>(null);

export function ApiProvider({ baseUrl, children }: { baseUrl: string; children: ReactNode }) {
  const auth = useAuth();
  const idToken = auth.user?.id_token;
  // El authorizer de Cognito de API Gateway valida el ID token del user pool.
  const client = useMemo(() => new ApiClient(baseUrl, () => idToken), [baseUrl, idToken]);
  return <ApiContext.Provider value={client}>{children}</ApiContext.Provider>;
}

export function useApi(): ApiClient {
  const client = useContext(ApiContext);
  if (!client) throw new Error("useApi debe usarse dentro de ApiProvider");
  return client;
}
