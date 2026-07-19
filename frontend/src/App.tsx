import { Navigate, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AnalysisTasksPage } from './pages/AnalysisTasksPage';
import { ChatPage } from './pages/ChatPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { KnowledgeBasesPage } from './pages/KnowledgeBasesPage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { WorkspaceCreatePage } from './pages/WorkspaceCreatePage';
import { WorkspaceDashboardPage } from './pages/WorkspaceDashboardPage';
import { WorkspaceListPage } from './pages/WorkspaceListPage';
import { WorkspacePlaceholderPage } from './pages/WorkspacePlaceholderPage';

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <WorkspaceListPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/workspaces"
        element={
          <ProtectedRoute>
            <WorkspaceListPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/workspaces/new"
        element={
          <ProtectedRoute>
            <WorkspaceCreatePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/workspaces/:workspaceId"
        element={
          <ProtectedRoute>
            <WorkspaceDashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/workspaces/:workspaceId/knowledge-bases"
        element={
          <ProtectedRoute>
            <KnowledgeBasesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/workspaces/:workspaceId/knowledge-bases/:knowledgeBaseId"
        element={
          <ProtectedRoute>
            <KnowledgeBasesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/workspaces/:workspaceId/knowledge-bases/:knowledgeBaseId/documents"
        element={
          <ProtectedRoute>
            <DocumentsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/workspaces/:workspaceId/knowledge-bases/:knowledgeBaseId/chat"
        element={
          <ProtectedRoute>
            <ChatPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/workspaces/:workspaceId/analysis-tasks"
        element={
          <ProtectedRoute>
            <AnalysisTasksPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/workspaces/:workspaceId/:section"
        element={
          <ProtectedRoute>
            <WorkspacePlaceholderPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/knowledge-bases"
        element={
          <ProtectedRoute>
            <KnowledgeBasesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/knowledge-bases/:knowledgeBaseId/chat"
        element={
          <ProtectedRoute>
            <ChatPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/knowledge-bases/:knowledgeBaseId/documents"
        element={
          <ProtectedRoute>
            <DocumentsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/knowledge-bases/:knowledgeBaseId"
        element={
          <ProtectedRoute>
            <KnowledgeBasesPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
