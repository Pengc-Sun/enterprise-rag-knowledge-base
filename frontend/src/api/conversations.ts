import { API_BASE_URL, ApiError, apiRequest, getStoredToken } from './client';
import type { Conversation, ConversationMetadata, Message, SourceCitation } from './types';

const conversationsPath = (knowledgeBaseId: string, workspaceId?: string) =>
  workspaceId
    ? `/workspaces/${workspaceId}/knowledge-bases/${knowledgeBaseId}/conversations`
    : `/knowledge-bases/${knowledgeBaseId}/conversations`;

export type StreamChatHandlers = {
  onStart?: () => void;
  onMetadata?: (metadata: ConversationMetadata) => void;
  onToken?: (token: string) => void;
  onDone?: (payload: { sources: SourceCitation[]; user_message_id: string; assistant_message_id: string }) => void;
  onError?: (message: string) => void;
};

type ParsedSseEvent = {
  event: string;
  data: Record<string, unknown>;
};

export function listConversations(knowledgeBaseId: string, workspaceId?: string): Promise<Conversation[]> {
  return apiRequest<Conversation[]>(conversationsPath(knowledgeBaseId, workspaceId));
}

export function createConversation(
  knowledgeBaseId: string,
  title = 'New conversation',
  workspaceId?: string,
): Promise<Conversation> {
  return apiRequest<Conversation>(conversationsPath(knowledgeBaseId, workspaceId), {
    method: 'POST',
    body: JSON.stringify({ title }),
  });
}

export function deleteConversation(
  knowledgeBaseId: string,
  conversationId: string,
  workspaceId?: string,
): Promise<void> {
  return apiRequest<void>(`${conversationsPath(knowledgeBaseId, workspaceId)}/${conversationId}`, {
    method: 'DELETE',
  });
}

export function listMessages(
  knowledgeBaseId: string,
  conversationId: string,
  workspaceId?: string,
): Promise<Message[]> {
  return apiRequest<Message[]>(`${conversationsPath(knowledgeBaseId, workspaceId)}/${conversationId}/messages`);
}

export async function streamConversationChat(
  knowledgeBaseId: string,
  conversationId: string,
  question: string,
  signal: AbortSignal,
  handlers: StreamChatHandlers,
  workspaceId?: string,
): Promise<void> {
  const headers = new Headers({
    Accept: 'text/event-stream',
    'Content-Type': 'application/json',
  });
  const token = getStoredToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(
    `${API_BASE_URL}${conversationsPath(knowledgeBaseId, workspaceId)}/${conversationId}/chat/stream`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({ question }),
      signal,
    },
  );

  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => null);
    throw new ApiError(body?.message ?? 'Conversation stream failed', response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';

    for (const eventBlock of events) {
      const parsed = parseSseEvent(eventBlock);
      if (parsed) {
        const streamError = dispatchStreamEvent(parsed, handlers);
        if (streamError) {
          throw new ApiError(streamError, 400);
        }
      }
    }
  }

  if (buffer.trim()) {
    const parsed = parseSseEvent(buffer);
    if (parsed) {
      const streamError = dispatchStreamEvent(parsed, handlers);
      if (streamError) {
        throw new ApiError(streamError, 400);
      }
    }
  }
}

function parseSseEvent(block: string): ParsedSseEvent | null {
  const lines = block.split('\n');
  const eventLine = lines.find((line) => line.startsWith('event:'));
  const dataLine = lines.find((line) => line.startsWith('data:'));
  if (!eventLine || !dataLine) {
    return null;
  }

  try {
    return {
      event: eventLine.replace('event:', '').trim(),
      data: JSON.parse(dataLine.replace('data:', '').trim()) as Record<string, unknown>,
    };
  } catch {
    return null;
  }
}

function dispatchStreamEvent(parsed: ParsedSseEvent, handlers: StreamChatHandlers): string | null {
  if (parsed.event === 'start') {
    handlers.onStart?.();
    return null;
  }
  if (parsed.event === 'metadata') {
    handlers.onMetadata?.(parsed.data as ConversationMetadata);
    return null;
  }
  if (parsed.event === 'token') {
    handlers.onToken?.(String(parsed.data.token ?? ''));
    return null;
  }
  if (parsed.event === 'done') {
    handlers.onDone?.({
      sources: (parsed.data.sources ?? []) as SourceCitation[],
      user_message_id: String(parsed.data.user_message_id ?? ''),
      assistant_message_id: String(parsed.data.assistant_message_id ?? ''),
    });
    return null;
  }
  if (parsed.event === 'error') {
    const message = String(parsed.data.message ?? 'Conversation stream failed');
    handlers.onError?.(message);
    return message;
  }
  return null;
}
