import { Navigate, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from './components/ProtectedRoute';
import { ChatPage } from './pages/ChatPage';
import { DocumentsPage } from './pages/DocumentsPage';
import { KnowledgeBasesPage } from './pages/KnowledgeBasesPage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { WorkspaceCreatePage } from './pages/WorkspaceCreatePage';
import { WorkspaceListPage } from './pages/WorkspaceListPage';

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
