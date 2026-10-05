import AppLayout from "@cloudscape-design/components/app-layout";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import Header from "@cloudscape-design/components/header";
import SideNavigation from "@cloudscape-design/components/side-navigation";
import SpaceBetween from "@cloudscape-design/components/space-between";
import Spinner from "@cloudscape-design/components/spinner";
import TopNavigation from "@cloudscape-design/components/top-navigation";
import { useAuth } from "react-oidc-context";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router";
import type { RuntimeConfig } from "./config";
import ChatPage from "./pages/ChatPage";
import DocumentsPage from "./pages/DocumentsPage";
import EvaluationDetailPage from "./pages/EvaluationDetailPage";
import EvaluationsPage from "./pages/EvaluationsPage";
import LogsPage from "./pages/LogsPage";

const NAV_ITEMS = [
  { type: "link" as const, text: "Conversación", href: "/chat" },
  { type: "link" as const, text: "Documentos", href: "/documentos" },
  { type: "link" as const, text: "Evaluaciones", href: "/evaluaciones" },
  { type: "link" as const, text: "Logs", href: "/logs" },
];

function SignIn({ onSignIn, error }: { onSignIn: () => void; error?: string }) {
  return (
    <Box margin="xxxl" textAlign="center">
      <Container header={<Header variant="h1">Asistente RAG Agéntico</Header>}>
        <SpaceBetween size="m">
          <Box>Consulta la documentación interna y gestiona tus solicitudes con el asistente.</Box>
          {error && <Box color="text-status-error">{error}</Box>}
          <Button variant="primary" onClick={onSignIn}>
            Iniciar sesión
          </Button>
        </SpaceBetween>
      </Container>
    </Box>
  );
}

export default function App({ config }: { config: RuntimeConfig }) {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  if (auth.isLoading) {
    return (
      <Box margin="xxxl" textAlign="center">
        <Spinner size="large" />
      </Box>
    );
  }
  if (!auth.isAuthenticated) {
    return <SignIn onSignIn={() => void auth.signinRedirect()} error={auth.error?.message} />;
  }

  const signOut = async () => {
    await auth.removeUser();
    // Cognito cierra su propia sesión en el endpoint /logout del managed login.
    const logoutUri = encodeURIComponent(`${window.location.origin}/`);
    window.location.href = `https://${config.cognitoDomain}/logout?client_id=${config.userPoolClientId}&logout_uri=${logoutUri}`;
  };

  return (
    <>
      <div id="top-nav">
        <TopNavigation
          identity={{ href: "/", title: "Asistente RAG Agéntico" }}
          utilities={[
            {
              type: "menu-dropdown",
              text: auth.user?.profile.email ?? "Usuario",
              iconName: "user-profile",
              items: [{ id: "signout", text: "Cerrar sesión" }],
              onItemClick: ({ detail }) => {
                if (detail.id === "signout") void signOut();
              },
            },
          ]}
        />
      </div>
      <AppLayout
        headerSelector="#top-nav"
        toolsHide
        navigation={
          <SideNavigation
            activeHref={`/${location.pathname.split("/")[1]}`}
            header={{ href: "/chat", text: "Menú" }}
            items={NAV_ITEMS}
            onFollow={(event) => {
              event.preventDefault();
              navigate(event.detail.href);
            }}
          />
        }
        content={
          <Routes>
            <Route path="/" element={<Navigate to="/chat" replace />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/chat/:conversationId" element={<ChatPage />} />
            <Route path="/documentos" element={<DocumentsPage />} />
            <Route path="/evaluaciones" element={<EvaluationsPage />} />
            <Route path="/evaluaciones/:evaluationId" element={<EvaluationDetailPage />} />
            <Route path="/logs" element={<LogsPage />} />
            <Route path="*" element={<Navigate to="/chat" replace />} />
          </Routes>
        }
      />
    </>
  );
}
