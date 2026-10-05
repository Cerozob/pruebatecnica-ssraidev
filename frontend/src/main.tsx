import "@cloudscape-design/global-styles/index.css";
import { WebStorageStateStore } from "oidc-client-ts";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AuthProvider } from "react-oidc-context";
import { BrowserRouter } from "react-router";
import App from "./App";
import { ApiProvider } from "./api/context";
import { loadConfig } from "./config";

const root = createRoot(document.getElementById("root")!);

loadConfig()
  .then((config) => {
    // ADR-006: inicio de sesión con el managed login de Cognito (código de autorización con PKCE).
    const oidcConfig = {
      authority: `https://cognito-idp.${config.region}.amazonaws.com/${config.userPoolId}`,
      client_id: config.userPoolClientId,
      redirect_uri: `${window.location.origin}/`,
      response_type: "code",
      scope: "openid email profile",
      userStore: new WebStorageStateStore({ store: window.sessionStorage }),
      onSigninCallback: () => window.history.replaceState({}, document.title, window.location.pathname),
    };

    root.render(
      <StrictMode>
        <AuthProvider {...oidcConfig}>
          <ApiProvider baseUrl={config.apiUrl}>
            <BrowserRouter>
              <App config={config} />
            </BrowserRouter>
          </ApiProvider>
        </AuthProvider>
      </StrictMode>,
    );
  })
  .catch((error: Error) => {
    root.render(<p style={{ fontFamily: "sans-serif", padding: 24 }}>No se pudo iniciar la aplicación: {error.message}</p>);
  });
