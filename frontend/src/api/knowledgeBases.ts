import { apiRequest } from './client';
import type { KnowledgeBase, KnowledgeBasePayload, KnowledgeBaseUpdatePayload } from './types';

export function listKnowledgeBases(): Promise<KnowledgeBase[]> {
  return apiRequest<KnowledgeBase[]>('/knowledge-bases');
}

export function createKnowledgeBase(payload: KnowledgeBasePayload): Promise<KnowledgeBase> {
  return apiRequest<KnowledgeBase>('/knowledge-bases', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getKnowledgeBase(knowledgeBaseId: string): Promise<KnowledgeBase> {
  return apiRequest<KnowledgeBase>(`/knowledge-bases/${knowledgeBaseId}`);
}

export function updateKnowledgeBase(
  knowledgeBaseId: string,
  payload: KnowledgeBaseUpdatePayload,
): Promise<KnowledgeBase> {
  return apiRequest<KnowledgeBase>(`/knowledge-bases/${knowledgeBaseId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deleteKnowledgeBase(knowledgeBaseId: string): Promise<void> {
  return apiRequest<void>(`/knowledge-bases/${knowledgeBaseId}`, {
    method: 'DELETE',
  });
}
