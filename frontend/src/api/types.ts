export type Role = "user" | "assistant";

export interface Source {
  type: "document" | "web";
  title: string;
  uri: string;
  excerpt?: string;
}

export interface Message {
  messageId: string;
  role: Role;
  content: string;
  createdAt: string;
  sources?: Source[];
  agents?: string[];
  blocked?: boolean;
  error?: boolean;
}

export interface ConversationSummary {
  conversationId: string;
  title: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface Conversation extends ConversationSummary {
  messages: Message[];
}

export interface SendMessageResponse {
  conversationId: string;
  userMessage: Message;
  message: Message;
}

export interface UploadUrlResponse {
  uploadUrl: string;
  key: string;
  expiresIn: number;
  contentType: string;
}

export interface LogGroup {
  name: string;
  id: string;
}

export type EvaluationStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";

export interface EvaluationSummaryMetrics {
  total: number;
  passed: number;
  accuracy: number | null;
  accuracyScore: number | null;
  groundedness: number | null;
  insufficientInformation: number | null;
  promptInjectionBlocked: number | null;
}

export interface EvaluationSummary {
  evaluationId: string;
  status: EvaluationStatus;
  createdAt: string;
  startedAt?: string;
  finishedAt?: string;
  progress?: { completed: number; total: number };
  summary?: EvaluationSummaryMetrics;
  error?: string;
}

export interface EvaluationResult {
  caseId: string;
  category: "accuracy" | "insufficient_information" | "prompt_injection";
  expectedAgent: string;
  agents: string[];
  technique?: string | null;
  question: string;
  expected: string;
  answer: string;
  score: number;
  reason: string;
  groundedness?: { score: number; reason: string } | null;
  sources: Source[];
  blocked: boolean;
  passed: boolean;
}

export interface Evaluation extends EvaluationSummary {
  results: EvaluationResult[];
}
