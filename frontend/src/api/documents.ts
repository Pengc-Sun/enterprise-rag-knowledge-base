import { apiRequest } from './client';
import type { DocumentItem } from './types';

const documentsPath = (knowledgeBaseId: string, workspaceId?: string) =>
  workspaceId
    ? `/workspaces/${workspaceId}/knowledge-bases/${knowledgeBaseId}/documents`
    : `/knowledge-bases/${knowledgeBaseId}/documents`;

export function listDocuments(knowledgeBaseId: string, workspaceId?: string): Promise<DocumentItem[]> {
  return apiRequest<DocumentItem[]>(documentsPath(knowledgeBaseId, workspaceId));
}

export function uploadDocument(
  knowledgeBaseId: string,
  file: File,
  workspaceId?: string,
): Promise<DocumentItem> {
  const body = new FormData();
  body.append('file', file);

  return apiRequest<DocumentItem>(documentsPath(knowledgeBaseId, workspaceId), {
    method: 'POST',
    body,
  });
}

export function reprocessDocument(
  knowledgeBaseId: string,
  documentId: string,
  workspaceId?: string,
): Promise<DocumentItem> {
  return apiRequest<DocumentItem>(`${documentsPath(knowledgeBaseId, workspaceId)}/${documentId}/reprocess`, {
    method: 'POST',
  });
}

export function deleteDocument(
  knowledgeBaseId: string,
  documentId: string,
  workspaceId?: string,
): Promise<void> {
  return apiRequest<void>(`${documentsPath(knowledgeBaseId, workspaceId)}/${documentId}`, {
    method: 'DELETE',
  });
}
