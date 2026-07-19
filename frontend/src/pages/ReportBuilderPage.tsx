import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { listReviewQueue } from '../api/analysisTasks';
import { ApiError } from '../api/client';
import {
  createReport,
  createReportExport,
  createReportSection,
  downloadExportJob,
  generateReportSection,
  getReportPreview,
  listReportSections,
  listReports,
  updateReport,
  updateReportSection,
} from '../api/reports';
import type {
  AnalysisReviewQueueItem,
  ExportFormat,
  Report,
  ReportExport,
  ReportPreview,
  ReportSection,
} from '../api/types';
import { WorkspaceNav } from '../components/WorkspaceNav';

const exportFormats: ExportFormat[] = ['markdown', 'docx', 'pdf'];

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function errorMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

function parseCsv(value: string) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function recentExportsKey(workspaceId: string) {
  return `enterprise-rag.recent-exports.${workspaceId}`;
}

function rememberExport(workspaceId: string, exportJob: ReportExport) {
  const key = recentExportsKey(workspaceId);
  const current = JSON.parse(window.localStorage.getItem(key) ?? '[]') as string[];
  const next = [exportJob.id, ...current.filter((id) => id !== exportJob.id)].slice(0, 20);
  window.localStorage.setItem(key, JSON.stringify(next));
}

export function ReportBuilderPage() {
  const { workspaceId } = useParams();
  const [reports, setReports] = useState<Report[]>([]);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [sections, setSections] = useState<ReportSection[]>([]);
  const [preview, setPreview] = useState<ReportPreview | null>(null);
  const [approvedItems, setApprovedItems] = useState<AnalysisReviewQueueItem[]>([]);
  const [selectedResultIds, setSelectedResultIds] = useState<string[]>([]);
  const [createTitle, setCreateTitle] = useState('');
  const [editTitle, setEditTitle] = useState('');
  const [sectionTitle, setSectionTitle] = useState('');
  const [sectionBody, setSectionBody] = useState('');
  const [sectionSources, setSectionSources] = useState('');
  const [generatedTitle, setGeneratedTitle] = useState('');
  const [lastExport, setLastExport] = useState<ReportExport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingReport, setIsLoadingReport] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const selectedReport = useMemo(
    () => reports.find((report) => report.id === selectedReportId) ?? null,
    [reports, selectedReportId],
  );

  const loadReports = useCallback(async () => {
    if (!workspaceId) {
      return;
    }

    setIsLoading(true);
    setPageError(null);

    try {
      const response = await listReports(workspaceId);
      setReports(response);
      setSelectedReportId((current) => current ?? response[0]?.id ?? null);
    } catch (err) {
      setPageError(errorMessage(err, 'Failed to load reports.'));
    } finally {
      setIsLoading(false);
    }
  }, [workspaceId]);

  const loadApprovedResults = useCallback(async () => {
    if (!workspaceId) {
      return;
    }

    const [approved, edited] = await Promise.all([
      listReviewQueue(workspaceId, { status: 'approved' }),
      listReviewQueue(workspaceId, { status: 'edited' }),
    ]);
    setApprovedItems([...approved, ...edited]);
  }, [workspaceId]);

  const loadSelectedReport = useCallback(async () => {
    if (!workspaceId || !selectedReportId) {
      setSections([]);
      setPreview(null);
      return;
    }

    setIsLoadingReport(true);
    setPageError(null);

    try {
      const [sectionResponse, previewResponse] = await Promise.all([
        listReportSections(workspaceId, selectedReportId),
        getReportPreview(workspaceId, selectedReportId),
      ]);
      setSections(sectionResponse);
      setPreview(previewResponse);
    } catch (err) {
      setPageError(errorMessage(err, 'Failed to load report details.'));
    } finally {
      setIsLoadingReport(false);
    }
  }, [selectedReportId, workspaceId]);

  useEffect(() => {
    void loadReports();
  }, [loadReports]);

  useEffect(() => {
    void loadApprovedResults().catch((err) => {
      setPageError(errorMessage(err, 'Failed to load approved analysis results.'));
    });
  }, [loadApprovedResults]);

  useEffect(() => {
    setEditTitle(selectedReport?.title ?? '');
  }, [selectedReport]);

  useEffect(() => {
    void loadSelectedReport();
  }, [loadSelectedReport]);

  if (!workspaceId) {
    return <Navigate to="/workspaces" replace />;
  }

  async function handleCreateReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspaceId) {
      return;
    }

    setBusyAction('create-report');
    setFormError(null);

    try {
      const report = await createReport(workspaceId, { title: createTitle.trim() });
      setReports((current) => [report, ...current]);
      setSelectedReportId(report.id);
      setCreateTitle('');
    } catch (err) {
      setFormError(errorMessage(err, 'Failed to create report.'));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleUpdateTitle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspaceId || !selectedReport) {
      return;
    }

    setBusyAction('update-title');
    setFormError(null);

    try {
      const updated = await updateReport(workspaceId, selectedReport.id, { title: editTitle.trim() });
      setReports((current) => current.map((report) => (report.id === updated.id ? updated : report)));
      await loadSelectedReport();
    } catch (err) {
      setFormError(errorMessage(err, 'Failed to update report title.'));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleCreateSection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspaceId || !selectedReport) {
      return;
    }

    setBusyAction('create-section');
    setFormError(null);

    try {
      await createReportSection(workspaceId, selectedReport.id, {
        title: sectionTitle.trim(),
        body_markdown: sectionBody,
        source_result_ids: parseCsv(sectionSources),
        sort_order: (sections.length + 1) * 10,
      });
      setSectionTitle('');
      setSectionBody('');
      setSectionSources('');
      await loadSelectedReport();
    } catch (err) {
      setFormError(errorMessage(err, 'Failed to create report section.'));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleUpdateSection(section: ReportSection) {
    if (!workspaceId || !selectedReport) {
      return;
    }

    setBusyAction(section.id);
    setFormError(null);

    try {
      await updateReportSection(workspaceId, selectedReport.id, section.id, {
        title: section.title,
        body_markdown: section.body_markdown,
        source_result_ids: section.source_result_ids,
        sort_order: section.sort_order,
      });
      await loadSelectedReport();
    } catch (err) {
      setFormError(errorMessage(err, 'Failed to update report section.'));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleGenerateSection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspaceId || !selectedReport) {
      return;
    }
    if (selectedResultIds.length === 0) {
      setFormError('Select at least one approved or edited analysis result.');
      return;
    }

    setBusyAction('generate-section');
    setFormError(null);

    try {
      await generateReportSection(workspaceId, selectedReport.id, {
        analysis_result_ids: selectedResultIds,
        title: generatedTitle.trim() || null,
        sort_order: (sections.length + 1) * 10,
      });
      setGeneratedTitle('');
      setSelectedResultIds([]);
      await loadSelectedReport();
    } catch (err) {
      setFormError(errorMessage(err, 'Failed to generate report section.'));
    } finally {
      setBusyAction(null);
    }
  }

  async function handleExport(format: ExportFormat) {
    if (!workspaceId || !selectedReport) {
      return;
    }

    setBusyAction(`export-${format}`);
    setFormError(null);

    try {
      const exportJob = await createReportExport(workspaceId, selectedReport.id, format);
      setLastExport(exportJob);
      rememberExport(workspaceId, exportJob);
    } catch (err) {
      setFormError(errorMessage(err, 'Failed to export report.'));
    } finally {
      setBusyAction(null);
    }
  }

  function toggleSelectedResult(resultId: string) {
    setSelectedResultIds((current) =>
      current.includes(resultId) ? current.filter((id) => id !== resultId) : [...current, resultId],
    );
  }

  return (
    <main className="app-shell report-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Workspace reports</p>
          <h1>Report builder</h1>
        </div>
        <div className="topbar-actions">
          <button className="secondary-button nav-button" onClick={() => void loadReports()} type="button">
            Refresh
          </button>
          <Link className="secondary-button nav-button" to={`/workspaces/${workspaceId}/exports`}>
            Exports
          </Link>
        </div>
      </header>

      <WorkspaceNav workspaceId={workspaceId} />

      {pageError && <p className="form-error" role="alert">{pageError}</p>}
      {formError && <p className="form-error" role="alert">{formError}</p>}

      <section className="report-layout" aria-label="Report builder workspace">
        <aside className="report-sidebar" aria-label="Report list">
          <form className="resource-form" onSubmit={handleCreateReport}>
            <label className="field">
              <span>New report title</span>
              <input
                maxLength={255}
                minLength={1}
                onChange={(event) => setCreateTitle(event.target.value)}
                placeholder="Policy Review Report"
                required
                type="text"
                value={createTitle}
              />
            </label>
            <button className="primary-button inline-button" disabled={busyAction === 'create-report'} type="submit">
              {busyAction === 'create-report' ? 'Creating...' : 'Create report'}
            </button>
          </form>

          <div className="report-list">
            {isLoading ? (
              <p className="empty-state">Loading reports...</p>
            ) : reports.length === 0 ? (
              <p className="empty-state">No reports yet.</p>
            ) : (
              reports.map((report) => (
                <button
                  className={report.id === selectedReportId ? 'report-item active' : 'report-item'}
                  key={report.id}
                  onClick={() => setSelectedReportId(report.id)}
                  type="button"
                >
                  <strong>{report.title}</strong>
                  <span className={`status-pill status-${report.status}`}>{report.status}</span>
                  <small>{formatDate(report.updated_at)}</small>
                </button>
              ))
            )}
          </div>
        </aside>

        <section className="report-detail" aria-label="Report detail">
          {selectedReport ? (
            <>
              <div className="detail-header">
                <div>
                  <h2>{selectedReport.title}</h2>
                  <p>{sections.length} sections · {preview?.section_count ?? 0} preview sections</p>
                </div>
                <span className={`status-pill status-${selectedReport.status}`}>{selectedReport.status}</span>
              </div>

              <form className="resource-form two-column-form" onSubmit={handleUpdateTitle}>
                <label className="field">
                  <span>Report title</span>
                  <input
                    maxLength={255}
                    minLength={1}
                    onChange={(event) => setEditTitle(event.target.value)}
                    required
                    type="text"
                    value={editTitle}
                  />
                </label>
                <button className="secondary-button inline-button" disabled={busyAction === 'update-title'} type="submit">
                  {busyAction === 'update-title' ? 'Saving...' : 'Save title'}
                </button>
              </form>

              <section className="report-action-grid" aria-label="Report actions">
                <form className="report-panel" onSubmit={handleCreateSection}>
                  <div className="section-heading">
                    <div>
                      <h2>Manual section</h2>
                      <p>Add reviewer-written Markdown content.</p>
                    </div>
                  </div>
                  <label className="field">
                    <span>Title</span>
                    <input
                      maxLength={255}
                      minLength={1}
                      onChange={(event) => setSectionTitle(event.target.value)}
                      required
                      type="text"
                      value={sectionTitle}
                    />
                  </label>
                  <label className="field">
                    <span>Body Markdown</span>
                    <textarea onChange={(event) => setSectionBody(event.target.value)} rows={7} value={sectionBody} />
                  </label>
                  <label className="field">
                    <span>Source result IDs</span>
                    <input
                      onChange={(event) => setSectionSources(event.target.value)}
                      placeholder="comma-separated approved result IDs"
                      type="text"
                      value={sectionSources}
                    />
                  </label>
                  <button className="primary-button inline-button" disabled={busyAction === 'create-section'} type="submit">
                    {busyAction === 'create-section' ? 'Adding...' : 'Add section'}
                  </button>
                </form>

                <form className="report-panel" onSubmit={handleGenerateSection}>
                  <div className="section-heading">
                    <div>
                      <h2>Generate from approved results</h2>
                      <p>{approvedItems.length} approved or edited results available.</p>
                    </div>
                  </div>
                  <label className="field">
                    <span>Generated section title</span>
                    <input
                      maxLength={255}
                      onChange={(event) => setGeneratedTitle(event.target.value)}
                      placeholder="Optional"
                      type="text"
                      value={generatedTitle}
                    />
                  </label>
                  <div className="approved-result-list">
                    {approvedItems.length === 0 ? (
                      <p className="empty-state">Approve or edit analysis results before generating report content.</p>
                    ) : (
                      approvedItems.map((item) => (
                        <label className="approved-result-option" key={item.analysis_result.id}>
                          <input
                            checked={selectedResultIds.includes(item.analysis_result.id)}
                            onChange={() => toggleSelectedResult(item.analysis_result.id)}
                            type="checkbox"
                          />
                          <span>
                            <strong>{item.analysis_task.name}</strong>
                            <small>{item.analysis_result.id}</small>
                          </span>
                        </label>
                      ))
                    )}
                  </div>
                  <button
                    className="primary-button inline-button"
                    disabled={busyAction === 'generate-section' || approvedItems.length === 0}
                    type="submit"
                  >
                    {busyAction === 'generate-section' ? 'Generating...' : 'Generate section'}
                  </button>
                </form>
              </section>

              <section className="report-panel" aria-label="Report sections">
                <div className="section-heading">
                  <div>
                    <h2>Sections</h2>
                    <p>{isLoadingReport ? 'Loading sections...' : `${sections.length} current sections`}</p>
                  </div>
                </div>
                {sections.length === 0 ? (
                  <p className="empty-state">No report sections yet.</p>
                ) : (
                  <div className="section-editor-list">
                    {sections.map((section, index) => (
                      <article className="section-editor" key={section.id}>
                        <label className="field">
                          <span>Section title</span>
                          <input
                            maxLength={255}
                            minLength={1}
                            onChange={(event) =>
                              setSections((current) =>
                                current.map((item) =>
                                  item.id === section.id ? { ...item, title: event.target.value } : item,
                                ),
                              )
                            }
                            required
                            type="text"
                            value={section.title}
                          />
                        </label>
                        <label className="field">
                          <span>Body Markdown</span>
                          <textarea
                            onChange={(event) =>
                              setSections((current) =>
                                current.map((item) =>
                                  item.id === section.id ? { ...item, body_markdown: event.target.value } : item,
                                ),
                              )
                            }
                            rows={8}
                            value={section.body_markdown}
                          />
                        </label>
                        <div className="form-actions">
                          <span className="status-pill status-draft">#{index + 1}</span>
                          <button
                            className="secondary-button inline-button"
                            disabled={busyAction === section.id}
                            onClick={() => void handleUpdateSection(section)}
                            type="button"
                          >
                            {busyAction === section.id ? 'Saving...' : 'Save section'}
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                )}
              </section>

              <section className="report-action-grid" aria-label="Preview and exports">
                <div className="report-panel">
                  <div className="section-heading">
                    <div>
                      <h2>Preview</h2>
                      <p>{preview ? `${preview.section_count} sections rendered` : 'No preview available'}</p>
                    </div>
                  </div>
                  <pre className="markdown-preview">{preview?.markdown || 'Preview will appear after sections are added.'}</pre>
                </div>

                <div className="report-panel">
                  <div className="section-heading">
                    <div>
                      <h2>Export</h2>
                      <p>Exports only succeed when referenced results are approved or edited.</p>
                    </div>
                  </div>
                  <div className="form-actions">
                    {exportFormats.map((format) => (
                      <button
                        className="secondary-button inline-button"
                        disabled={busyAction === `export-${format}`}
                        key={format}
                        onClick={() => void handleExport(format)}
                        type="button"
                      >
                        {busyAction === `export-${format}` ? 'Exporting...' : `Export ${format.toUpperCase()}`}
                      </button>
                    ))}
                  </div>
                  {lastExport && (
                    <div className="export-card">
                      <strong>{String(lastExport.export_metadata.filename ?? lastExport.id)}</strong>
                      <span className={`status-pill status-${lastExport.status}`}>{lastExport.status}</span>
                      <button
                        className="primary-button inline-button"
                        onClick={() => void downloadExportJob(workspaceId, lastExport)}
                        type="button"
                      >
                        Download
                      </button>
                    </div>
                  )}
                </div>
              </section>
            </>
          ) : (
            <div className="empty-detail">
              <h2>Select a report</h2>
              <p>Create or choose a report to edit sections, preview Markdown, and export files.</p>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
