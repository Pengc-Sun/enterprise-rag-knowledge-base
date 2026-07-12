import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

const workspaceItems = [
  {
    title: 'Knowledge bases',
    description: 'Organize private corpora before document ingestion and retrieval tests.',
    status: 'Ready for API wiring',
  },
  {
    title: 'Documents',
    description: 'Upload, parse, and track files after the authenticated file flow is connected.',
    status: 'Backend available',
  },
  {
    title: 'Chat',
    description: 'Run retrieval-backed conversations once the vector search workflow is exposed.',
    status: 'Planned',
  },
];

export function DashboardPage() {
  const navigate = useNavigate();
  const { signOut, token } = useAuth();
  const tokenPreview = token ? `${token.slice(0, 12)}...${token.slice(-8)}` : 'No token';

  function handleSignOut() {
    signOut();
    navigate('/login', { replace: true });
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Enterprise RAG</p>
          <h1>Workspace</h1>
        </div>
        <button className="secondary-button" onClick={handleSignOut} type="button">
          Sign out
        </button>
      </header>

      <section className="status-band" aria-label="Authentication status">
        <div>
          <span className="metric-label">Session</span>
          <strong>Authenticated</strong>
        </div>
        <div>
          <span className="metric-label">Token</span>
          <code>{tokenPreview}</code>
        </div>
        <div>
          <span className="metric-label">API base</span>
          <code>{import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'}</code>
        </div>
      </section>

      <section className="workspace-grid" aria-label="Workspace modules">
        {workspaceItems.map((item) => (
          <article className="module-card" key={item.title}>
            <div>
              <h2>{item.title}</h2>
              <p>{item.description}</p>
            </div>
            <span>{item.status}</span>
          </article>
        ))}
      </section>
    </main>
  );
}
