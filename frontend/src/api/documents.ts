import { apiRequest } from './client';
import type { DocumentItem } from './types';

const documentsPath = (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/documents`;

export function listDocuments(knowledgeBaseId: string): Promise<DocumentItem[]> {
  return apiRequest<DocumentItem[]>(documentsPath(knowledgeBaseId));
}

export function uploadDocument(knowledgeBaseId: string, file: File): Promise<DocumentItem> {
  const body = new FormData();
  body.append('file', file);

  return apiRequest<DocumentItem>(documentsPath(knowledgeBaseId), {
    method: 'POST',
    body,
  });
}

export function reprocessDocument(
  knowledgeBaseId: string,
  documentId: string,
): Promise<DocumentItem> {
  return apiRequest<DocumentItem>(`${documentsPath(knowledgeBaseId)}/${documentId}/reprocess`, {
    method: 'POST',
  });
}

export function deleteDocument(knowledgeBaseId: string, documentId: string): Promise<void> {
  return apiRequest<void>(`${documentsPath(knowledgeBaseId)}/${documentId}`, {
    method: 'DELETE',
  });
}
