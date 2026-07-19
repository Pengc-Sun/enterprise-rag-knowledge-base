import { apiRequest } from './client';
import type { KnowledgeBase, KnowledgeBasePayload, KnowledgeBaseUpdatePayload } from './types';

const knowledgeBasesPath = (workspaceId?: string) =>
  workspaceId ? `/workspaces/${workspaceId}/knowledge-bases` : '/knowledge-bases';

const knowledgeBasePath = (knowledgeBaseId: string, workspaceId?: string) =>
  `${knowledgeBasesPath(workspaceId)}/${knowledgeBaseId}`;

export function listKnowledgeBases(workspaceId?: string): Promise<KnowledgeBase[]> {
  return apiRequest<KnowledgeBase[]>(knowledgeBasesPath(workspaceId));
}

export function createKnowledgeBase(
  payload: KnowledgeBasePayload,
  workspaceId?: string,
): Promise<KnowledgeBase> {
  return apiRequest<KnowledgeBase>(knowledgeBasesPath(workspaceId), {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getKnowledgeBase(knowledgeBaseId: string, workspaceId?: string): Promise<KnowledgeBase> {
  return apiRequest<KnowledgeBase>(knowledgeBasePath(knowledgeBaseId, workspaceId));
}

export function updateKnowledgeBase(
  knowledgeBaseId: string,
  payload: KnowledgeBaseUpdatePayload,
  workspaceId?: string,
): Promise<KnowledgeBase> {
  return apiRequest<KnowledgeBase>(knowledgeBasePath(knowledgeBaseId, workspaceId), {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function deleteKnowledgeBase(knowledgeBaseId: string, workspaceId?: string): Promise<void> {
  return apiRequest<void>(knowledgeBasePath(knowledgeBaseId, workspaceId), {
    method: 'DELETE',
  });
}
