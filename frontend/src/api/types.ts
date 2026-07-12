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
