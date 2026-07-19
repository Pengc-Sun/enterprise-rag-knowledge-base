import { FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { ApiError } from '../api/client';
import { deleteDocument, listDocuments, reprocessDocument, uploadDocument } from '../api/documents';
import { getKnowledgeBase } from '../api/knowledgeBases';
import type { DocumentItem, KnowledgeBase } from '../api/types';
import { WorkspaceNav } from '../components/WorkspaceNav';

function formatBytes(bytes: number) {
  if (bytes === 0) {
    return '0 B';
  }

  const units = ['B', 'KB', 'MB', 'GB'];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** index;
  return `${value.toFixed(value >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function errorMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

export function DocumentsPage() {
  const { workspaceId, knowledgeBaseId } = useParams();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeBase | null>(null);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [busyDocumentId, setBusyDocumentId] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const knowledgeBasesPath = workspaceId ? `/workspaces/${workspaceId}/knowledge-bases` : '/knowledge-bases';
  const knowledgeBasePath = knowledgeBaseId ? `${knowledgeBasesPath}/${knowledgeBaseId}` : knowledgeBasesPath;

  const loadDocuments = useCallback(async () => {
    if (!knowledgeBaseId) {
      return;
    }

    setIsLoading(true);
    setPageError(null);

    try {
      const [knowledgeBaseResponse, documentsResponse] = await Promise.all([
        getKnowledgeBase(knowledgeBaseId, workspaceId),
        listDocuments(knowledgeBaseId, workspaceId),
      ]);
      setKnowledgeBase(knowledgeBaseResponse);
      setDocuments(documentsResponse);
    } catch (err) {
      setPageError(errorMessage(err, 'Failed to load documents.'));
    } finally {
      setIsLoading(false);
    }
  }, [knowledgeBaseId, workspaceId]);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  if (!knowledgeBaseId) {
    return <Navigate to={knowledgeBasesPath} replace />;
  }

  async function handleUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!knowledgeBaseId) {
      return;
    }
    if (!selectedFile) {
      setUploadError('Select a document file before uploading.');
      return;
    }

    setIsUploading(true);
    setUploadError(null);

    try {
      const uploaded = await uploadDocument(knowledgeBaseId, selectedFile, workspaceId);
      setDocuments((current) => [uploaded, ...current]);
      setSelectedFile(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err) {
      setUploadError(errorMessage(err, 'Failed to upload document.'));
    } finally {
      setIsUploading(false);
    }
  }

  async function handleReprocess(document: DocumentItem) {
    if (!knowledgeBaseId) {
      return;
    }

    setBusyDocumentId(document.id);
    setPageError(null);

    try {
      const processed = await reprocessDocument(knowledgeBaseId, document.id, workspaceId);
      setDocuments((current) => current.map((item) => (item.id === processed.id ? processed : item)));
    } catch (err) {
      setPageError(errorMessage(err, 'Failed to reprocess document.'));
    } finally {
      setBusyDocumentId(null);
    }
  }

  async function handleDelete(document: DocumentItem) {
    if (!knowledgeBaseId) {
      return;
    }

    const confirmed = window.confirm(`Delete document "${document.filename}"?`);
    if (!confirmed) {
      return;
    }

    setBusyDocumentId(document.id);
    setPageError(null);

    try {
      await deleteDocument(knowledgeBaseId, document.id, workspaceId);
      setDocuments((current) => current.filter((item) => item.id !== document.id));
    } catch (err) {
      setPageError(errorMessage(err, 'Failed to delete document.'));
    } finally {
      setBusyDocumentId(null);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Documents</p>
          <h1>{knowledgeBase?.name ?? 'Document management'}</h1>
        </div>
        <Link className="secondary-button nav-button" to={knowledgeBasePath}>
          Knowledge base
        </Link>
      </header>

      {workspaceId && <WorkspaceNav workspaceId={workspaceId} />}

      {pageError && <p className="form-error" role="alert">{pageError}</p>}

      <section className="create-panel" aria-labelledby="upload-document-title">
        <div className="section-heading">
          <div>
            <h2 id="upload-document-title">Upload document</h2>
            <p>Accepted formats: PDF, TXT, Markdown, and DOCX.</p>
          </div>
        </div>

        <form className="upload-form" onSubmit={handleUpload}>
          <label className="file-drop">
            <span>{selectedFile ? selectedFile.name : 'Choose a document file'}</span>
            <small>{selectedFile ? formatBytes(selectedFile.size) : 'Maximum size follows backend settings'}</small>
            <input
              accept=".pdf,.txt,.md,.markdown,.docx"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              ref={fileInputRef}
              type="file"
            />
          </label>
          <button className="primary-button inline-button" disabled={isUploading} type="submit">
            {isUploading ? 'Uploading...' : 'Upload'}
          </button>
          {uploadError && <p className="form-error wide-field" role="alert">{uploadError}</p>}
        </form>
      </section>

      <section className="table-panel" aria-label="Document list">
        <div className="section-heading">
          <div>
            <h2>Documents</h2>
            <p>{documents.length} files in this knowledge base</p>
          </div>
          <button className="secondary-button compact-button" onClick={() => void loadDocuments()} type="button">
            Refresh
          </button>
        </div>

        {isLoading ? (
          <p className="empty-state">Loading documents...</p>
        ) : documents.length === 0 ? (
          <p className="empty-state">No documents uploaded yet.</p>
        ) : (
          <div className="document-table" role="table" aria-label="Documents">
            <div className="document-row table-head" role="row">
              <span role="columnheader">Filename</span>
              <span role="columnheader">Size</span>
              <span role="columnheader">Status</span>
              <span role="columnheader">Chunks</span>
              <span role="columnheader">Uploaded</span>
              <span role="columnheader">Actions</span>
            </div>
            {documents.map((document) => (
              <div className="document-row" role="row" key={document.id}>
                <div className="filename-cell" role="cell">
                  <strong>{document.filename}</strong>
                  {document.error_message && <small>{document.error_message}</small>}
                </div>
                <span role="cell">{formatBytes(document.file_size)}</span>
                <span role="cell" className={`status-pill status-${document.status}`}>
                  {document.status}
                </span>
                <span role="cell">{document.chunk_count}</span>
                <span role="cell">{formatDate(document.created_at)}</span>
                <div className="row-actions" role="cell">
                  <button
                    className="secondary-button compact-button"
                    disabled={busyDocumentId === document.id}
                    onClick={() => void handleReprocess(document)}
                    type="button"
                  >
                    {busyDocumentId === document.id ? 'Working...' : 'Reprocess'}
                  </button>
                  <button
                    className="danger-button compact-button"
                    disabled={busyDocumentId === document.id}
                    onClick={() => void handleDelete(document)}
                    type="button"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
