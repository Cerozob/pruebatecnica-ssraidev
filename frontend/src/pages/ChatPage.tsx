import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import ContentLayout from "@cloudscape-design/components/content-layout";
import Flashbar, { type FlashbarProps } from "@cloudscape-design/components/flashbar";
import Grid from "@cloudscape-design/components/grid";
import Header from "@cloudscape-design/components/header";
import Link from "@cloudscape-design/components/link";
import PromptInput from "@cloudscape-design/components/prompt-input";
import SpaceBetween from "@cloudscape-design/components/space-between";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { ApiError } from "../api/client";
import { useApi } from "../api/context";
import type { ConversationSummary, Message } from "../api/types";
import { ChatMessage, ThinkingMessage } from "../components/ChatMessage";
import { findNewConversation, formatDate } from "../utils/format";

const MAX_LENGTH = 4000;
const POLL_INTERVAL_MS = 4000;
const POLL_TIMEOUT_MS = 5 * 60 * 1000;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export default function ChatPage() {
  const api = useApi();
  const navigate = useNavigate();
  const { conversationId: routeId } = useParams();

  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  // El id de la conversación es el sessionId de AgentCore; lo asigna el backend en el primer mensaje.
  const conversationId = routeId;
  const [messages, setMessages] = useState<Message[]>([]);
  const [prompt, setPrompt] = useState("");
  const [sending, setSending] = useState(false);
  const [flash, setFlash] = useState<FlashbarProps.MessageDefinition[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  const showError = useCallback((message: string) => {
    setFlash([{ type: "error", content: message, dismissible: true, onDismiss: () => setFlash([]), id: "error" }]);
  }, []);

  const refreshConversations = useCallback(async () => {
    try {
      setConversations((await api.listConversations()).conversations);
    } catch (error) {
      showError(`No se pudieron cargar las conversaciones: ${(error as Error).message}`);
    }
  }, [api, showError]);

  useEffect(() => {
    let cancelled = false;
    api
      .listConversations()
      .then(({ conversations: items }) => !cancelled && setConversations(items))
      .catch((error: Error) => !cancelled && showError(`No se pudieron cargar las conversaciones: ${error.message}`));
    return () => {
      cancelled = true;
    };
  }, [api, showError]);

  useEffect(() => {
    if (!routeId) return;
    let cancelled = false;
    api
      .getConversation(routeId)
      .then((conversation) => !cancelled && setMessages(conversation.messages))
      .catch((error: ApiError) => {
        if (!cancelled && error.status !== 404) showError(error.message);
      });
    return () => {
      cancelled = true;
    };
  }, [api, routeId, showError]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  const openConversation = (id?: string) => {
    setMessages([]);
    navigate(id ? `/chat/${id}` : "/chat");
  };

  /** Si API Gateway corta a los 29 s, el backend sigue y guarda la respuesta: se consulta hasta que aparece. */
  const waitForReply = async (id: string, previousCount: number): Promise<Message[] | null> => {
    const deadline = Date.now() + POLL_TIMEOUT_MS;
    while (Date.now() < deadline) {
      await sleep(POLL_INTERVAL_MS);
      try {
        const conversation = await api.getConversation(id);
        const last = conversation.messages[conversation.messages.length - 1];
        if (conversation.messages.length >= previousCount + 2 && last?.role === "assistant") {
          return conversation.messages;
        }
      } catch {
        // Se reintenta hasta el límite de tiempo.
      }
    }
    return null;
  };

  /** Si el primer mensaje se corta a los 29 s, la conversación ya existe: se busca en la lista del usuario. */
  const findCreatedConversation = async (content: string, sentAt: string): Promise<string | null> => {
    const deadline = Date.now() + POLL_TIMEOUT_MS;
    while (Date.now() < deadline) {
      await sleep(POLL_INTERVAL_MS);
      try {
        const { conversations: items } = await api.listConversations();
        const found = findNewConversation(items, content, sentAt);
        if (found) return found;
      } catch {
        // Se reintenta hasta el límite de tiempo.
      }
    }
    return null;
  };

  const send = async () => {
    const content = prompt.trim();
    if (!content || sending) return;
    if (content.length > MAX_LENGTH) {
      showError(`El mensaje no puede superar ${MAX_LENGTH} caracteres.`);
      return;
    }

    const isNew = !conversationId;
    const previousCount = messages.length;
    const startedAt = new Date().toISOString();
    const optimistic: Message = {
      messageId: `local-${Date.now()}`,
      role: "user",
      content,
      createdAt: startedAt,
    };
    setMessages((current) => [...current, optimistic]);
    setPrompt("");
    setSending(true);
    setFlash([]);

    let id = conversationId;
    try {
      const response = isNew ? await api.createConversation(content) : await api.sendMessage(id!, content);
      id = response.conversationId;
      setMessages((current) => [...current.slice(0, -1), response.userMessage, response.message]);
    } catch (error) {
      const apiError = error as ApiError;
      if (apiError.isTimeout) {
        id = id ?? (await findCreatedConversation(content, startedAt)) ?? undefined;
        const updated = id ? await waitForReply(id, previousCount) : null;
        if (updated) setMessages(updated);
        else showError("El asistente tardó demasiado en responder. Revisa la conversación más tarde.");
      } else {
        showError(apiError.message);
      }
    } finally {
      setSending(false);
      if (isNew && id) navigate(`/chat/${id}`, { replace: true });
      void refreshConversations();
    }
  };

  return (
    <ContentLayout header={<Header variant="h1">Conversación con el asistente</Header>}>
      <SpaceBetween size="m">
        <Flashbar items={flash} />
        <Grid gridDefinition={[{ colspan: { default: 12, m: 3 } }, { colspan: { default: 12, m: 9 } }]}>
          <Container
            header={
              <Header
                variant="h2"
                actions={
                  <Button iconName="add-plus" onClick={() => openConversation()} disabled={sending}>
                    Nueva
                  </Button>
                }
              >
                Conversaciones
              </Header>
            }
          >
            {conversations.length === 0 ? (
              <Box color="text-status-inactive">Aún no hay conversaciones.</Box>
            ) : (
              <SpaceBetween size="s">
                {conversations.map((conversation) => (
                  <SpaceBetween size="xxxs" key={conversation.conversationId}>
                    <Link
                      href={`/chat/${conversation.conversationId}`}
                      onFollow={(event) => {
                        event.preventDefault();
                        if (!sending) openConversation(conversation.conversationId);
                      }}
                      fontSize={conversation.conversationId === conversationId ? "heading-xs" : "body-m"}
                    >
                      {conversation.title || "Sin título"}
                    </Link>
                    <Box variant="small" color="text-body-secondary">
                      {formatDate(conversation.updatedAt)}
                    </Box>
                  </SpaceBetween>
                ))}
              </SpaceBetween>
            )}
          </Container>

          <Container
            footer={
              <PromptInput
                value={prompt}
                onChange={({ detail }) => setPrompt(detail.value)}
                onAction={() => void send()}
                placeholder="Pregunta sobre la documentación o gestiona una solicitud"
                actionButtonIconName="send"
                actionButtonAriaLabel="Enviar"
                disableActionButton={sending || prompt.trim() === ""}
                minRows={2}
                maxRows={8}
              />
            }
          >
            <div style={{ height: "60vh", overflowY: "auto" }}>
              <SpaceBetween size="m">
                {messages.length === 0 && !sending && (
                  <Box textAlign="center" color="text-status-inactive" padding="xxl">
                    Escribe un mensaje para empezar. Por ejemplo: "¿Quién fue el campeón del Mundial 2026?" o "Lista
                    las solicitudes pendientes".
                  </Box>
                )}
                {messages.map((message) => (
                  <ChatMessage key={message.messageId} message={message} />
                ))}
                {sending && <ThinkingMessage />}
                <div ref={endRef} />
              </SpaceBetween>
            </div>
          </Container>
        </Grid>
      </SpaceBetween>
    </ContentLayout>
  );
}
