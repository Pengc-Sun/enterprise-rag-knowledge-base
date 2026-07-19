import { API_BASE_URL, ApiError, apiRequest, getStoredToken } from './client';
import type {
  ExportFormat,
  Report,
  ReportExport,
  ReportPayload,
  ReportPreview,
  ReportSection,
  ReportSectionGeneratePayload,
  ReportSectionPayload,
  ReportSectionUpdatePayload,
} from './types';

const reportsPath = (workspaceId: string) => `/workspaces/${workspaceId}/reports`;
const reportPath = (workspaceId: string, reportId: string) => `${reportsPath(workspaceId)}/${reportId}`;
const exportsPath = (workspaceId: string) => `/workspaces/${workspaceId}/exports`;

export function listReports(workspaceId: string): Promise<Report[]> {
  return apiRequest<Report[]>(reportsPath(workspaceId));
}

export function createReport(workspaceId: string, payload: ReportPayload): Promise<Report> {
  return apiRequest<Report>(reportsPath(workspaceId), {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateReport(
  workspaceId: string,
  reportId: string,
  payload: Partial<ReportPayload>,
): Promise<Report> {
  return apiRequest<Report>(reportPath(workspaceId, reportId), {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function getReportPreview(workspaceId: string, reportId: string): Promise<ReportPreview> {
  return apiRequest<ReportPreview>(`${reportPath(workspaceId, reportId)}/preview`);
}

export function listReportSections(workspaceId: string, reportId: string): Promise<ReportSection[]> {
  return apiRequest<ReportSection[]>(`${reportPath(workspaceId, reportId)}/sections`);
}

export function createReportSection(
  workspaceId: string,
  reportId: string,
  payload: ReportSectionPayload,
): Promise<ReportSection> {
  return apiRequest<ReportSection>(`${reportPath(workspaceId, reportId)}/sections`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function updateReportSection(
  workspaceId: string,
  reportId: string,
  sectionId: string,
  payload: ReportSectionUpdatePayload,
): Promise<ReportSection> {
  return apiRequest<ReportSection>(`${reportPath(workspaceId, reportId)}/sections/${sectionId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function generateReportSection(
  workspaceId: string,
  reportId: string,
  payload: ReportSectionGeneratePayload,
): Promise<ReportSection> {
  return apiRequest<ReportSection>(`${reportPath(workspaceId, reportId)}/sections/generate`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function createReportExport(
  workspaceId: string,
  reportId: string,
  format: ExportFormat,
): Promise<ReportExport> {
  return apiRequest<ReportExport>(`${reportPath(workspaceId, reportId)}/exports`, {
    method: 'POST',
    body: JSON.stringify({ format }),
  });
}

export function getExportJob(workspaceId: string, exportId: string): Promise<ReportExport> {
  return apiRequest<ReportExport>(`${exportsPath(workspaceId)}/${exportId}`);
}

export async function downloadExportJob(workspaceId: string, exportJob: ReportExport): Promise<void> {
  const token = getStoredToken();
  const headers = new Headers();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${exportsPath(workspaceId)}/${exportJob.id}/download`, {
    headers,
  });
  if (!response.ok) {
    throw new ApiError('Export download failed', response.status);
  }

  const blob = await response.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = String(exportJob.export_metadata.filename ?? `report-export.${exportJob.format}`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
