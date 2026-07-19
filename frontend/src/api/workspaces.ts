import { apiRequest } from './client';
import type { Workspace, WorkspacePayload, WorkspaceTemplate } from './types';

export function listWorkspaces(): Promise<Workspace[]> {
  return apiRequest<Workspace[]>('/workspaces');
}

export function createWorkspace(payload: WorkspacePayload): Promise<Workspace> {
  return apiRequest<Workspace>('/workspaces', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function listWorkspaceTemplates(): Promise<WorkspaceTemplate[]> {
  return apiRequest<WorkspaceTemplate[]>('/workspace-templates');
}
