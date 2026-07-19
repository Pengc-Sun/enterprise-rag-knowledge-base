import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client';
import { listWorkspaces } from '../api/workspaces';
import { useAuth } from '../auth/AuthContext';
import type { Workspace } from '../api/types';

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function errorMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

export function WorkspaceListPage() {
  const navigate = useNavigate();
  const { signOut } = useAuth();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadWorkspaces = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await listWorkspaces();
      setWorkspaces(response);
    } catch (err) {
      setError(errorMessage(err, 'Failed to load workspaces.'));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadWorkspaces();
  }, [loadWorkspaces]);

  function handleSignOut() {
    signOut();
    navigate('/login', { replace: true });
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Workspaces</p>
          <h1>Project list</h1>
        </div>
        <div className="topbar-actions">
          <Link className="primary-button nav-button inline-button" to="/workspaces/new">
            New workspace
          </Link>
          <button className="secondary-button" onClick={handleSignOut} type="button">
            Sign out
          </button>
        </div>
      </header>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}

      <section className="table-panel" aria-labelledby="workspace-list-title">
        <div className="section-heading">
          <div>
            <h2 id="workspace-list-title">Workspace inventory</h2>
            <p>{workspaces.length} total</p>
          </div>
          <button className="secondary-button compact-button" onClick={() => void loadWorkspaces()} type="button">
            Refresh
          </button>
        </div>

        {isLoading ? (
          <p className="empty-state">Loading workspaces...</p>
        ) : workspaces.length === 0 ? (
          <div className="empty-detail compact-empty">
            <h2>No workspaces</h2>
            <p>Create a workspace to start using templates, documents, analysis, reviews, and reports.</p>
            <Link className="primary-button nav-button inline-button" to="/workspaces/new">
              New workspace
            </Link>
          </div>
        ) : (
          <div className="workspace-list">
            {workspaces.map((workspace) => (
              <article className="workspace-list-card" key={workspace.id}>
                <div className="workspace-card-main">
                  <div>
                    <h2>{workspace.name}</h2>
                    <p>{workspace.description || 'No description provided.'}</p>
                  </div>
                  <span className="visibility-badge">{workspace.status}</span>
                </div>
                <dl className="metadata-grid compact-metadata">
                  <div>
                    <dt>Slug</dt>
                    <dd>{workspace.slug}</dd>
                  </div>
                  <div>
                    <dt>Template</dt>
                    <dd>{workspace.template_id ? 'template' : 'none'}</dd>
                  </div>
                  <div>
                    <dt>Created</dt>
                    <dd>{formatDate(workspace.created_at)}</dd>
                  </div>
                  <div>
                    <dt>Updated</dt>
                    <dd>{formatDate(workspace.updated_at)}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
