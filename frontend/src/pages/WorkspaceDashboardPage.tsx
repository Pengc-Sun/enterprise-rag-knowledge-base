import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ApiError } from '../api/client';
import { getWorkspace, getWorkspaceDashboard } from '../api/workspaces';
import { WorkspaceNav } from '../components/WorkspaceNav';
import type { Workspace, WorkspaceDashboard, WorkspaceDashboardStatusMetric } from '../api/types';

function errorMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function statusRows(metric: WorkspaceDashboardStatusMetric) {
  return Object.entries(metric.by_status).filter(([, count]) => count > 0);
}

export function WorkspaceDashboardPage() {
  const { workspaceId = '' } = useParams();
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [dashboard, setDashboard] = useState<WorkspaceDashboard | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    if (!workspaceId) {
      setError('Workspace ID is missing.');
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const [workspaceResponse, dashboardResponse] = await Promise.all([
        getWorkspace(workspaceId),
        getWorkspaceDashboard(workspaceId),
      ]);
      setWorkspace(workspaceResponse);
      setDashboard(dashboardResponse);
    } catch (err) {
      setError(errorMessage(err, 'Failed to load workspace dashboard.'));
    } finally {
      setIsLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const pendingReviews = dashboard?.reviews.by_status.needs_review ?? 0;
  const approvedFindings = (dashboard?.reviews.by_status.approved ?? 0) + (dashboard?.reviews.by_status.edited ?? 0);
  const completedExports = dashboard?.exports.by_status.completed ?? 0;

  const cards = useMemo(
    () =>
      dashboard
        ? [
            { label: 'Documents', metric: dashboard.documents },
            { label: 'Analysis tasks', metric: dashboard.analysis_tasks },
            { label: 'Reviews', metric: dashboard.reviews },
            { label: 'Reports', metric: dashboard.reports },
            { label: 'Exports', metric: dashboard.exports },
          ]
        : [],
    [dashboard],
  );

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Workspace dashboard</p>
          <h1>{workspace?.name ?? 'Workspace'}</h1>
        </div>
        <div className="topbar-actions">
          <button className="secondary-button" onClick={() => void loadDashboard()} type="button">
            Refresh
          </button>
          <Link className="secondary-button nav-button" to="/workspaces">
            Workspace list
          </Link>
        </div>
      </header>

      {workspaceId && <WorkspaceNav workspaceId={workspaceId} />}

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      {isLoading ? (
        <section className="table-panel">
          <p className="empty-state">Loading workspace dashboard...</p>
        </section>
      ) : workspace && dashboard ? (
        <>
          <section className="status-band" aria-label="Workspace status">
            <div>
              <span className="metric-label">Status</span>
              <strong>{workspace.status}</strong>
            </div>
            <div>
              <span className="metric-label">Slug</span>
              <code>{workspace.slug}</code>
            </div>
            <div>
              <span className="metric-label">Updated</span>
              <strong>{formatDate(workspace.updated_at)}</strong>
            </div>
          </section>

          <section className="dashboard-summary-grid" aria-label="Workspace summary">
            <article className="summary-card">
              <span className="metric-label">Pending review</span>
              <strong>{pendingReviews}</strong>
            </article>
            <article className="summary-card">
              <span className="metric-label">Approved findings</span>
              <strong>{approvedFindings}</strong>
            </article>
            <article className="summary-card">
              <span className="metric-label">Completed exports</span>
              <strong>{completedExports}</strong>
            </article>
          </section>

          <section className="dashboard-card-grid" aria-label="Workspace metric cards">
            {cards.map((card) => (
              <article className="dashboard-card" key={card.label}>
                <div className="dashboard-card-header">
                  <h2>{card.label}</h2>
                  <strong>{card.metric.total}</strong>
                </div>
                <div className="status-list">
                  {statusRows(card.metric).length === 0 ? (
                    <p className="empty-state">No activity yet.</p>
                  ) : (
                    statusRows(card.metric).map(([status, count]) => (
                      <div className="status-list-row" key={status}>
                        <span>{status.replaceAll('_', ' ')}</span>
                        <strong>{count}</strong>
                      </div>
                    ))
                  )}
                </div>
              </article>
            ))}
          </section>
        </>
      ) : (
        <section className="empty-detail compact-empty">
          <h2>Workspace unavailable</h2>
          <p>The workspace could not be loaded or you do not have access.</p>
        </section>
      )}
    </main>
  );
}
