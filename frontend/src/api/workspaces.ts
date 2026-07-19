import { apiRequest } from './client';
import type { Workspace, WorkspaceDashboard, WorkspacePayload, WorkspaceTemplate } from './types';

export function listWorkspaces(): Promise<Workspace[]> {
  return apiRequest<Workspace[]>('/workspaces');
}

export function getWorkspace(workspaceId: string): Promise<Workspace> {
  return apiRequest<Workspace>(`/workspaces/${workspaceId}`);
}

export function createWorkspace(payload: WorkspacePayload): Promise<Workspace> {
  return apiRequest<Workspace>('/workspaces', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function getWorkspaceDashboard(workspaceId: string): Promise<WorkspaceDashboard> {
  return apiRequest<WorkspaceDashboard>(`/workspaces/${workspaceId}/dashboard`);
}

export function listWorkspaceTemplates(): Promise<WorkspaceTemplate[]> {
  return apiRequest<WorkspaceTemplate[]>('/workspace-templates');
}
