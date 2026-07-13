import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { ApiError } from '../api/client';
import {
  createConversation,
  deleteConversation,
  listConversations,
  listMessages,
  streamConversationChat,
} from '../api/conversations';
import { getKnowledgeBase } from '../api/knowledgeBases';
import type { Conversation, ConversationMetadata, KnowledgeBase, Message, SourceCitation } from '../api/types';

type DraftMessage = Message & {
  isStreaming?: boolean;
  metadata?: ConversationMetadata;
};

function errorMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

function newDraftMessage(partial: Pick<DraftMessage, 'conversation_id' | 'role' | 'content'>): DraftMessage {
  return {
    id: `draft-${crypto.randomUUID()}`,
    conversation_id: partial.conversation_id,
    role: partial.role,
    content: partial.content,
    sources: [],
    token_usage: null,
    latency_ms: null,
    created_at: new Date().toISOString(),
  };
}

export function ChatPage() {
  const { knowledgeBaseId } = useParams();
  const abortRef = useRef<AbortController | null>(null);
  const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeBase | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<DraftMessage[]>([]);
  const [question, setQuestion] = useState('');
  const [pageError, setPageError] = useState<string | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [selectedSource, setSelectedSource] = useState<SourceCitation | null>(null);

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeConversationId) ?? null,
    [activeConversationId, conversations],
  );

  const loadConversations = useCallback(async () => {
    if (!knowledgeBaseId) {
      return;
    }

    setIsLoading(true);
    setPageError(null);

    try {
      const [knowledgeBaseResponse, conversationsResponse] = await Promise.all([
        getKnowledgeBase(knowledgeBaseId),
        listConversations(knowledgeBaseId),
      ]);
      setKnowledgeBase(knowledgeBaseResponse);
      setConversations(conversationsResponse);
      setActiveConversationId((current) => current ?? conversationsResponse[0]?.id ?? null);
    } catch (err) {
      setPageError(errorMessage(err, 'Failed to load conversations.'));
    } finally {
      setIsLoading(false);
    }
  }, [knowledgeBaseId]);

  useEffect(() => {
    void loadConversations();
  }, [loadConversations]);

  useEffect(() => {
    if (!knowledgeBaseId || !activeConversationId) {
      setMessages([]);
      return;
    }

    let cancelled = false;
    const kbId = knowledgeBaseId;
    const conversationId = activeConversationId;

    async function loadMessages() {
      setPageError(null);
      try {
        const response = await listMessages(kbId, conversationId);
        if (!cancelled) {
          setMessages(response);
        }
      } catch (err) {
        if (!cancelled) {
          setPageError(errorMessage(err, 'Failed to load messages.'));
        }
      }
    }

    void loadMessages();

    return () => {
      cancelled = true;
    };
  }, [activeConversationId, knowledgeBaseId]);

  if (!knowledgeBaseId) {
    return <Navigate to="/knowledge-bases" replace />;
  }

  async function handleNewConversation() {
    if (!knowledgeBaseId) {
      return;
    }

    setIsCreating(true);
    setPageError(null);

    try {
      const created = await createConversation(knowledgeBaseId, 'New conversation');
      setConversations((current) => [created, ...current]);
      setActiveConversationId(created.id);
      setMessages([]);
    } catch (err) {
      setPageError(errorMessage(err, 'Failed to create conversation.'));
    } finally {
      setIsCreating(false);
    }
  }

  async function handleDeleteConversation(conversation: Conversation) {
    if (!knowledgeBaseId) {
      return;
    }
    const confirmed = window.confirm(`Delete conversation "${conversation.title}"?`);
    if (!confirmed) {
      return;
    }

    try {
      await deleteConversation(knowledgeBaseId, conversation.id);
      setConversations((current) => current.filter((item) => item.id !== conversation.id));
      if (activeConversationId === conversation.id) {
        setActiveConversationId(null);
        setMessages([]);
      }
    } catch (err) {
      setPageError(errorMessage(err, 'Failed to delete conversation.'));
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!knowledgeBaseId || isStreaming) {
      return;
    }

    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) {
      return;
    }

    setStreamError(null);
    setQuestion('');

    let conversationId = activeConversationId;
    try {
      if (!conversationId) {
        const created = await createConversation(knowledgeBaseId, trimmedQuestion.slice(0, 80));
        setConversations((current) => [created, ...current]);
        setActiveConversationId(created.id);
        conversationId = created.id;
      }
    } catch (err) {
      setQuestion(trimmedQuestion);
      setStreamError(errorMessage(err, 'Failed to create conversation.'));
      return;
    }

    const userDraft = newDraftMessage({
      conversation_id: conversationId,
      role: 'user',
      content: trimmedQuestion,
    });
    const assistantDraft = newDraftMessage({
      conversation_id: conversationId,
      role: 'assistant',
      content: '',
    });
    assistantDraft.isStreaming = true;

    setMessages((current) => [...current, userDraft, assistantDraft]);
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamConversationChat(knowledgeBaseId, conversationId, trimmedQuestion, controller.signal, {
        onMetadata: (metadata) => {
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantDraft.id ? { ...message, metadata } : message,
            ),
          );
        },
        onToken: (token) => {
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantDraft.id
                ? { ...message, content: `${message.content}${token}` }
                : message,
            ),
          );
        },
        onDone: ({ sources, assistant_message_id }) => {
          setMessages((current) =>
            current.map((message) =>
              message.id === assistantDraft.id
                ? {
                    ...message,
                    id: assistant_message_id || message.id,
                    sources,
                    isStreaming: false,
                  }
                : message,
            ),
          );
        },
        onError: (message) => {
          setStreamError(message);
        },
      });
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        setStreamError('Generation stopped.');
      } else {
        setStreamError(errorMessage(err, 'Conversation stream failed.'));
      }
      setMessages((current) => current.filter((message) => message.id !== assistantDraft.id));
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
      await refreshActiveMessages(knowledgeBaseId, conversationId);
    }
  }

  async function refreshActiveMessages(kbId: string, conversationId: string) {
    try {
      const response = await listMessages(kbId, conversationId);
      setMessages(response);
    } catch {
      // Keep optimistic messages visible if history reload fails.
    }
  }

  function handleStopGeneration() {
    abortRef.current?.abort();
  }

  async function handleCopyAnswer(content: string) {
    try {
      await navigator.clipboard.writeText(content);
    } catch {
      setStreamError('Copy failed.');
    }
  }

  return (
    <main className="app-shell chat-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Chat</p>
          <h1>{knowledgeBase?.name ?? 'Knowledge base chat'}</h1>
        </div>
        <Link className="secondary-button nav-button" to={`/knowledge-bases/${knowledgeBaseId}`}>
          Knowledge base
        </Link>
      </header>

      {pageError && <p className="form-error" role="alert">{pageError}</p>}

      <section className="chat-layout" aria-label="Chat workspace">
        <aside className="conversation-sidebar" aria-label="Conversation list">
          <div className="section-heading">
            <div>
              <h2>Conversations</h2>
              <p>{conversations.length} saved</p>
            </div>
            <button className="secondary-button compact-button" disabled={isCreating} onClick={() => void handleNewConversation()} type="button">
              New
            </button>
          </div>

          <div className="conversation-list">
            {isLoading ? (
              <p className="empty-state">Loading conversations...</p>
            ) : conversations.length === 0 ? (
              <p className="empty-state">No conversations yet.</p>
            ) : (
              conversations.map((conversation) => (
                <button
                  className={conversation.id === activeConversationId ? 'conversation-item active' : 'conversation-item'}
                  key={conversation.id}
                  onClick={() => setActiveConversationId(conversation.id)}
                  type="button"
                >
                  <span>{conversation.title}</span>
                  <small>{new Date(conversation.updated_at).toLocaleString()}</small>
                </button>
              ))
            )}
          </div>

          {activeConversation && (
            <button
              className="danger-button compact-button"
              onClick={() => void handleDeleteConversation(activeConversation)}
              type="button"
            >
              Delete conversation
            </button>
          )}
        </aside>

        <section className="chat-panel" aria-label="Messages">
          <div className="message-list">
            {messages.length === 0 ? (
              <div className="empty-detail">
                <h2>Ask a question</h2>
                <p>Start a retrieval-backed conversation with this knowledge base.</p>
              </div>
            ) : (
              messages.map((message) => (
                <article className={`message-card ${message.role}`} key={message.id}>
                  <div className="message-header">
                    <strong>{message.role === 'user' ? 'You' : 'Assistant'}</strong>
                    {message.role === 'assistant' && message.content && (
                      <button className="secondary-button compact-button" onClick={() => void handleCopyAnswer(message.content)} type="button">
                        Copy
                      </button>
                    )}
                  </div>
                  <p>{message.content || (message.isStreaming ? 'Thinking...' : '')}</p>
                  {message.metadata?.context_chunk_count !== undefined && (
                    <small className="message-meta">
                      {message.metadata.context_chunk_count} chunks · {message.metadata.provider} / {message.metadata.model}
                    </small>
                  )}
                  {message.sources.length > 0 && (
                    <div className="source-grid" aria-label="Source citations">
                      {message.sources.map((source) => (
                        <button className="source-card" key={source.chunk_id} onClick={() => setSelectedSource(source)} type="button">
                          <strong>{source.document_name}</strong>
                          <span>Page {source.page_number} · score {source.similarity_score.toFixed(3)}</span>
                          <small>{source.original_text}</small>
                        </button>
                      ))}
                    </div>
                  )}
                </article>
              ))
            )}
          </div>

          {streamError && <p className="form-error" role="alert">{streamError}</p>}

          <form className="chat-input" onSubmit={handleSubmit}>
            <textarea
              maxLength={4000}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder={activeConversation ? 'Ask about uploaded documents' : 'Create a conversation by asking a question'}
              rows={3}
              value={question}
            />
            <div className="form-actions">
              <button className="primary-button inline-button" disabled={isStreaming} type="submit">
                {isStreaming ? 'Streaming...' : 'Send'}
              </button>
              {isStreaming && (
                <button className="danger-button" onClick={handleStopGeneration} type="button">
                  Stop
                </button>
              )}
            </div>
          </form>
        </section>
      </section>

      {selectedSource && (
        <div className="modal-backdrop" role="presentation" onClick={() => setSelectedSource(null)}>
          <section className="source-modal" aria-modal="true" role="dialog" onClick={(event) => event.stopPropagation()}>
            <div className="section-heading">
              <div>
                <h2>{selectedSource.document_name}</h2>
                <p>Page {selectedSource.page_number} · chunk {selectedSource.chunk_id}</p>
              </div>
              <button className="secondary-button compact-button" onClick={() => setSelectedSource(null)} type="button">
                Close
              </button>
            </div>
            <p>{selectedSource.original_text}</p>
          </section>
        </div>
      )}
    </main>
  );
}
