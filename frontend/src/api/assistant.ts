import { http } from './client';
import type {
  AssistantChatRequest,
  AssistantChatResponse,
  AssistantCodeActionRequest,
  AssistantCodeActionResponse,
  AssistantConversation,
  AssistantContext,
  AssistantContextType,
  AssistantMode,
  AssistantMessage,
} from '../types';

const BASE = '/assistant';

function repoBase(owner: string, repository: string): string {
  return `${BASE}/${encodeURIComponent(owner)}/${encodeURIComponent(repository)}`;
}

/**
 * Send a message to the AI Developer Assistant.
 *
 * The assistant first tries to answer deterministically from loaded data.
 * If that fails, it falls back to Gemini with bounded context.
 */
export async function sendAssistantMessage(
  owner: string,
  repository: string,
  request: AssistantChatRequest,
): Promise<AssistantChatResponse> {
  const { data } = await http.post<AssistantChatResponse>(
    `${repoBase(owner, repository)}/chat`,
    request,
  );
  return data;
}

/**
 * Perform a code action (explain, refactor, generate tests, suggest fix).
 *
 * Returns the original code, generated code, explanation, and diff.
 */
export async function performCodeAction(
  owner: string,
  repository: string,
  request: AssistantCodeActionRequest,
): Promise<AssistantCodeActionResponse> {
  const { data } = await http.post<AssistantCodeActionResponse>(
    `${repoBase(owner, repository)}/code-action`,
    request,
  );
  return data;
}

/**
 * List conversations for a repository.
 */
export async function listConversations(
  owner: string,
  repository: string,
  params: { page?: number; per_page?: number } = {},
): Promise<{ items: AssistantConversation[]; total: number }> {
  const { data } = await http.get<{ items: AssistantConversation[]; total: number }>(
    `${repoBase(owner, repository)}/conversations`,
    { params },
  );
  return data;
}

/**
 * Get a conversation by ID.
 */
export async function getConversation(
  owner: string,
  repository: string,
  conversationId: string,
): Promise<AssistantConversation> {
  const { data } = await http.get<AssistantConversation>(
    `${repoBase(owner, repository)}/conversations/${encodeURIComponent(conversationId)}`,
  );
  return data;
}

// ---------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------

/** Messages in a conversation, in order. */
export function conversationMessages(conversation: AssistantConversation): AssistantMessage[] {
  return conversation.messages;
}

/** The last message in a conversation. */
export function lastMessage(conversation: AssistantConversation): AssistantMessage | null {
  return conversation.messages.length > 0
    ? conversation.messages[conversation.messages.length - 1]
    : null;
}

/** Messages that were answered locally (without LLM). */
export function cachedMessages(conversation: AssistantConversation): AssistantMessage[] {
  return conversation.messages.filter((message) => message.cached);
}

/** Messages that required the LLM. */
export function llmMessages(conversation: AssistantConversation): AssistantMessage[] {
  return conversation.messages.filter((message) => !message.cached);
}

/** The active context for a conversation. */
export function activeContext(conversation: AssistantConversation): AssistantContext | null {
  return conversation.context ?? null;
}

/** Context types that have been used in a conversation. */
export function usedContextTypes(conversation: AssistantConversation): AssistantContextType[] {
  const types = new Set<AssistantContextType>();
  for (const message of conversation.messages) {
    if (message.context_type) types.add(message.context_type);
  }
  return [...types];
}

/** Modes that have been used in a conversation. */
export function usedModes(conversation: AssistantConversation): AssistantMode[] {
  const modes = new Set<AssistantMode>();
  for (const message of conversation.messages) {
    if (message.mode) modes.add(message.mode);
  }
  return [...modes];
}

/** Warnings from all messages in a conversation. */
export function allWarnings(conversation: AssistantConversation): string[] {
  const warnings: string[] = [];
  for (const message of conversation.messages) {
    warnings.push(...(message.warnings ?? []));
  }
  return warnings;
}
