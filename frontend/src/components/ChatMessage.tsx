import Avatar from "@cloudscape-design/chat-components/avatar";
import ChatBubble from "@cloudscape-design/chat-components/chat-bubble";
import Badge from "@cloudscape-design/components/badge";
import Box from "@cloudscape-design/components/box";
import ExpandableSection from "@cloudscape-design/components/expandable-section";
import Link from "@cloudscape-design/components/link";
import SpaceBetween from "@cloudscape-design/components/space-between";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import type { Message, Source } from "../api/types";
import { agentLabel } from "../utils/format";

function SourceItem({ source }: { source: Source }) {
  if (source.type === "web") {
    return (
      <Link href={source.uri} external>
        {source.title}
      </Link>
    );
  }
  return (
    <SpaceBetween size="xxxs">
      <Box fontWeight="bold">{source.title}</Box>
      {source.excerpt && (
        <Box variant="small" color="text-body-secondary">
          {source.excerpt}
        </Box>
      )}
    </SpaceBetween>
  );
}

export function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const sources = message.sources ?? [];
  return (
    <ChatBubble
      type={isUser ? "outgoing" : "incoming"}
      ariaLabel={isUser ? "Tu mensaje" : "Respuesta del asistente"}
      avatar={
        isUser ? (
          <Avatar ariaLabel="Tú" iconName="user-profile" />
        ) : (
          <Avatar ariaLabel="Asistente" color="gen-ai" iconName="gen-ai" />
        )
      }
    >
      <SpaceBetween size="xs">
        {message.blocked && <StatusIndicator type="warning">Bloqueado por los guardrails</StatusIndicator>}
        {message.error && <StatusIndicator type="error">Error del asistente</StatusIndicator>}
        <div style={{ whiteSpace: "pre-wrap" }}>{message.content}</div>
        {!isUser && (message.agents?.length ?? 0) > 0 && (
          <SpaceBetween size="xxs" direction="horizontal">
            {message.agents!.map((agent, index) => (
              <Badge key={`${agent}-${index}`} color="grey">
                {agentLabel(agent)}
              </Badge>
            ))}
          </SpaceBetween>
        )}
        {sources.length > 0 && (
          <ExpandableSection headerText={`Fuentes (${sources.length})`} variant="footer">
            <SpaceBetween size="s">
              {sources.map((source) => (
                <SourceItem key={source.uri} source={source} />
              ))}
            </SpaceBetween>
          </ExpandableSection>
        )}
      </SpaceBetween>
    </ChatBubble>
  );
}

export function ThinkingMessage() {
  return (
    <ChatBubble
      type="incoming"
      ariaLabel="El asistente está respondiendo"
      showLoadingBar
      avatar={<Avatar ariaLabel="Asistente" color="gen-ai" iconName="gen-ai" loading />}
    >
      <Box color="text-status-inactive">Consultando a los agentes…</Box>
    </ChatBubble>
  );
}
