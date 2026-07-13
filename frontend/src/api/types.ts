export type ApiResponse<T> = {
  success: boolean;
  message: string;
  data: T | null;
};

export type AccessToken = {
  access_token: string;
  token_type: string;
};

export type UserRead = {
  id: string;
  email: string;
  username: string;
  role: 'admin' | 'user';
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type LoginPayload = {
  email: string;
  password: string;
};

export type RegisterPayload = {
  email: string;
  username: string;
  password: string;
};


export type KnowledgeBaseVisibility = 'private' | 'public';

export type KnowledgeBase = {
  id: string;
  owner_id: string;
  name: string;
  description: string | null;
  visibility: KnowledgeBaseVisibility;
  created_at: string;
  updated_at: string;
};

export type KnowledgeBasePayload = {
  name: string;
  description?: string | null;
  visibility: KnowledgeBaseVisibility;
};

export type KnowledgeBaseUpdatePayload = Partial<KnowledgeBasePayload>;


export type DocumentStatus = 'uploaded' | 'parsing' | 'chunking' | 'embedding' | 'completed' | 'failed';

export type DocumentItem = {
  id: string;
  knowledge_base_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  file_hash: string;
  storage_path: string;
  status: DocumentStatus;
  error_message: string | null;
  chunk_count: number;
  created_by: string;
  created_at: string;
  updated_at: string;
};


export type Conversation = {
  id: string;
  user_id: string;
  knowledge_base_id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type MessageRole = 'user' | 'assistant' | 'system';

export type SourceCitation = {
  document_name: string;
  page_number: number;
  chunk_id: string;
  original_text: string;
  similarity_score: number;
};

export type Message = {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  sources: SourceCitation[];
  token_usage: Record<string, unknown> | null;
  latency_ms: number | null;
  created_at: string;
};

export type ConversationMetadata = {
  rewritten_question?: string;
  question_was_rewritten?: boolean;
  model?: string;
  provider?: string;
  context_message_count?: number;
  context_chunk_count?: number;
  context_chunk_ids?: string[];
};
