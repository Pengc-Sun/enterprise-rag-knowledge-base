import { apiRequest } from './client';
import type { AnalysisResult, AnalysisTask } from './types';

const analysisTasksPath = (workspaceId: string) => `/workspaces/${workspaceId}/analysis-tasks`;

export function listAnalysisTasks(workspaceId: string): Promise<AnalysisTask[]> {
  return apiRequest<AnalysisTask[]>(analysisTasksPath(workspaceId));
}

export function getAnalysisTask(workspaceId: string, analysisTaskId: string): Promise<AnalysisTask> {
  return apiRequest<AnalysisTask>(`${analysisTasksPath(workspaceId)}/${analysisTaskId}`);
}

export function runAnalysisTask(workspaceId: string, analysisTaskId: string): Promise<AnalysisResult> {
  return apiRequest<AnalysisResult>(`${analysisTasksPath(workspaceId)}/${analysisTaskId}/run`, {
    method: 'POST',
  });
}

export function listAnalysisResults(
  workspaceId: string,
  analysisTaskId: string,
): Promise<AnalysisResult[]> {
  return apiRequest<AnalysisResult[]>(`${analysisTasksPath(workspaceId)}/${analysisTaskId}/results`);
}
