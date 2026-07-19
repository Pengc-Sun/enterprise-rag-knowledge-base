import { Link, useParams } from 'react-router-dom';
import { WorkspaceNav } from '../components/WorkspaceNav';

const sectionLabels: Record<string, string> = {
  'knowledge-bases': 'Knowledge bases',
  documents: 'Documents',
  'analysis-tasks': 'Analysis tasks',
  review: 'Review queue',
  reports: 'Reports',
  exports: 'Exports',
  members: 'Members',
};

export function WorkspacePlaceholderPage() {
  const { workspaceId = '', section = '' } = useParams();
  const label = sectionLabels[section] ?? 'Workspace section';

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Workspace</p>
          <h1>{label}</h1>
        </div>
        <Link className="secondary-button nav-button" to={`/workspaces/${workspaceId}`}>
          Dashboard
        </Link>
      </header>

      {workspaceId && <WorkspaceNav workspaceId={workspaceId} />}

      <section className="empty-detail compact-empty">
        <h2>{label}</h2>
        <p>This workspace section is reserved for the next frontend migration step.</p>
      </section>
    </main>
  );
}
