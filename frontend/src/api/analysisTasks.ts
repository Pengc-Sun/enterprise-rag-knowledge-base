import { apiRequest } from './client';
import type {
  AnalysisResult,
  AnalysisResultStatus,
  AnalysisReviewQueueItem,
  AnalysisTask,
  ReviewDecision,
  ReviewDecisionPayload,
} from './types';

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

export type ReviewQueueFilters = {
  status?: AnalysisResultStatus;
  taskType?: string;
};

export function listReviewQueue(
  workspaceId: string,
  filters: ReviewQueueFilters = {},
): Promise<AnalysisReviewQueueItem[]> {
  const params = new URLSearchParams();
  if (filters.status) {
    params.set('status', filters.status);
  }
  if (filters.taskType) {
    params.set('task_type', filters.taskType);
  }
  const query = params.toString();
  return apiRequest<AnalysisReviewQueueItem[]>(
    `${analysisTasksPath(workspaceId)}/review-queue${query ? `?${query}` : ''}`,
  );
}

export function createReviewDecision(
  workspaceId: string,
  analysisTaskId: string,
  analysisResultId: string,
  payload: ReviewDecisionPayload,
): Promise<ReviewDecision> {
  return apiRequest<ReviewDecision>(
    `${analysisTasksPath(workspaceId)}/${analysisTaskId}/results/${analysisResultId}/review-decisions`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );
}
