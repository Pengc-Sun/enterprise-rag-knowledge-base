import { NavLink } from 'react-router-dom';

type WorkspaceNavProps = {
  workspaceId: string;
};

const navItems = [
  { label: 'Dashboard', path: '' },
  { label: 'Knowledge bases', path: 'knowledge-bases' },
  { label: 'Documents', path: 'documents' },
  { label: 'Analysis', path: 'analysis-tasks' },
  { label: 'Review', path: 'review' },
  { label: 'Reports', path: 'reports' },
  { label: 'Exports', path: 'exports' },
  { label: 'Members', path: 'members' },
];

export function WorkspaceNav({ workspaceId }: WorkspaceNavProps) {
  return (
    <nav className="workspace-nav" aria-label="Workspace navigation">
      {navItems.map((item) => (
        <NavLink
          className={({ isActive }) => (isActive ? 'workspace-nav-link active' : 'workspace-nav-link')}
          end={item.path === ''}
          key={item.label}
          to={`/workspaces/${workspaceId}${item.path ? `/${item.path}` : ''}`}
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
