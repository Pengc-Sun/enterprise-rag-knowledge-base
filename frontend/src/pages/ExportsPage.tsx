import { FormEvent, useCallback, useEffect, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { ApiError } from '../api/client';
import { downloadExportJob, getExportJob } from '../api/reports';
import type { ReportExport } from '../api/types';
import { WorkspaceNav } from '../components/WorkspaceNav';

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function errorMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

function recentExportsKey(workspaceId: string) {
  return `enterprise-rag.recent-exports.${workspaceId}`;
}

function readRecentExportIds(workspaceId: string) {
  return JSON.parse(window.localStorage.getItem(recentExportsKey(workspaceId)) ?? '[]') as string[];
}

export function ExportsPage() {
  const { workspaceId } = useParams();
  const [exportId, setExportId] = useState('');
  const [exportJobs, setExportJobs] = useState<ReportExport[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [busyExportId, setBusyExportId] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);

  const loadRecentExports = useCallback(async () => {
    if (!workspaceId) {
      return;
    }

    setIsLoading(true);
    setPageError(null);

    try {
      const ids = readRecentExportIds(workspaceId);
      const jobs = await Promise.all(
        ids.map((id) =>
          getExportJob(workspaceId, id).catch(() => null),
        ),
      );
      setExportJobs(jobs.filter((job): job is ReportExport => job !== null));
    } catch (err) {
      setPageError(errorMessage(err, 'Failed to load recent exports.'));
    } finally {
      setIsLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void loadRecentExports();
  }, [loadRecentExports]);

  if (!workspaceId) {
    return <Navigate to="/workspaces" replace />;
  }

  async function handleLookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!workspaceId) {
      return;
    }
    const trimmed = exportId.trim();
    if (!trimmed) {
      return;
    }

    setBusyExportId(trimmed);
    setPageError(null);

    try {
      const job = await getExportJob(workspaceId, trimmed);
      setExportJobs((current) => [job, ...current.filter((item) => item.id !== job.id)]);
      setExportId('');
    } catch (err) {
      setPageError(errorMessage(err, 'Export job was not found.'));
    } finally {
      setBusyExportId(null);
    }
  }

  async function handleDownload(exportJob: ReportExport) {
    if (!workspaceId) {
      return;
    }

    setBusyExportId(exportJob.id);
    setPageError(null);

    try {
      await downloadExportJob(workspaceId, exportJob);
    } catch (err) {
      setPageError(errorMessage(err, 'Failed to download export file.'));
    } finally {
      setBusyExportId(null);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Workspace exports</p>
          <h1>Exports</h1>
        </div>
        <div className="topbar-actions">
          <button className="secondary-button nav-button" onClick={() => void loadRecentExports()} type="button">
            Refresh
          </button>
          <Link className="secondary-button nav-button" to={`/workspaces/${workspaceId}/reports`}>
            Reports
          </Link>
        </div>
      </header>

      <WorkspaceNav workspaceId={workspaceId} />

      <section className="status-band" aria-label="Export summary">
        <div>
          <span className="metric-label">Visible exports</span>
          <strong>{exportJobs.length}</strong>
        </div>
        <div>
          <span className="metric-label">Completed</span>
          <strong>{exportJobs.filter((job) => job.status === 'completed').length}</strong>
        </div>
        <div>
          <span className="metric-label">Formats</span>
          <strong>{new Set(exportJobs.map((job) => job.format)).size}</strong>
        </div>
      </section>

      {pageError && <p className="form-error" role="alert">{pageError}</p>}

      <section className="report-panel" aria-labelledby="lookup-export-title">
        <div className="section-heading">
          <div>
            <h2 id="lookup-export-title">Lookup export</h2>
            <p>Use an export ID from a report export response to reopen or download it.</p>
          </div>
        </div>
        <form className="upload-form" onSubmit={handleLookup}>
          <label className="field">
            <span>Export ID</span>
            <input
              onChange={(event) => setExportId(event.target.value)}
              placeholder="8df873e9-7f97-4ea5-b60c-5a8e29c92025"
              type="text"
              value={exportId}
            />
          </label>
          <button className="primary-button inline-button" disabled={busyExportId === exportId.trim()} type="submit">
            Lookup
          </button>
        </form>
      </section>

      <section className="table-panel" aria-label="Export jobs">
        <div className="section-heading">
          <div>
            <h2>Recent exports</h2>
            <p>{isLoading ? 'Loading exports...' : `${exportJobs.length} export jobs visible in this browser`}</p>
          </div>
        </div>

        {isLoading ? (
          <p className="empty-state">Loading recent exports...</p>
        ) : exportJobs.length === 0 ? (
          <p className="empty-state">No recent exports in this browser yet. Create one from the Reports page.</p>
        ) : (
          <div className="export-list">
            {exportJobs.map((exportJob) => (
              <article className="export-card" key={exportJob.id}>
                <div>
                  <strong>{String(exportJob.export_metadata.filename ?? exportJob.id)}</strong>
                  <small>{exportJob.id}</small>
                </div>
                <span className={`status-pill status-${exportJob.status}`}>{exportJob.status}</span>
                <span>{exportJob.format.toUpperCase()}</span>
                <span>{formatDate(exportJob.created_at)}</span>
                <button
                  className="primary-button inline-button"
                  disabled={busyExportId === exportJob.id || exportJob.status !== 'completed'}
                  onClick={() => void handleDownload(exportJob)}
                  type="button"
                >
                  {busyExportId === exportJob.id ? 'Downloading...' : 'Download'}
                </button>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
