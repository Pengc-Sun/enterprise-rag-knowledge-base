import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ApiError } from '../api/client';
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  getKnowledgeBase,
  listKnowledgeBases,
  updateKnowledgeBase,
} from '../api/knowledgeBases';
import type { KnowledgeBase, KnowledgeBaseVisibility } from '../api/types';

const visibilityOptions: KnowledgeBaseVisibility[] = ['private', 'public'];

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function errorMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

export function KnowledgeBasesPage() {
  const navigate = useNavigate();
  const { knowledgeBaseId } = useParams();
  const [items, setItems] = useState<KnowledgeBase[]>([]);
  const [selected, setSelected] = useState<KnowledgeBase | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [listError, setListError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [createName, setCreateName] = useState('');
  const [createDescription, setCreateDescription] = useState('');
  const [createVisibility, setCreateVisibility] = useState<KnowledgeBaseVisibility>('private');
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editVisibility, setEditVisibility] = useState<KnowledgeBaseVisibility>('private');

  const selectedFromList = useMemo(
    () => items.find((item) => item.id === knowledgeBaseId) ?? null,
    [items, knowledgeBaseId],
  );

  const loadKnowledgeBases = useCallback(async () => {
    setIsLoading(true);
    setListError(null);

    try {
      const response = await listKnowledgeBases();
      setItems(response);
    } catch (err) {
      setListError(errorMessage(err, 'Failed to load knowledge bases.'));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadKnowledgeBases();
  }, [loadKnowledgeBases]);

  useEffect(() => {
    let cancelled = false;

    async function syncSelected() {
      if (!knowledgeBaseId) {
        setSelected(null);
        return;
      }

      if (selectedFromList) {
        setSelected(selectedFromList);
        return;
      }

      try {
        const response = await getKnowledgeBase(knowledgeBaseId);
        if (!cancelled) {
          setSelected(response);
        }
      } catch (err) {
        if (!cancelled) {
          setSelected(null);
          setListError(errorMessage(err, 'Knowledge base was not found.'));
        }
      }
    }

    void syncSelected();

    return () => {
      cancelled = true;
    };
  }, [knowledgeBaseId, selectedFromList]);

  useEffect(() => {
    if (!selected) {
      setEditName('');
      setEditDescription('');
      setEditVisibility('private');
      return;
    }

    setEditName(selected.name);
    setEditDescription(selected.description ?? '');
    setEditVisibility(selected.visibility);
  }, [selected]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);
    setIsSaving(true);

    try {
      const created = await createKnowledgeBase({
        name: createName.trim(),
        description: createDescription.trim() || null,
        visibility: createVisibility,
      });
      setItems((current) => [created, ...current]);
      setCreateName('');
      setCreateDescription('');
      setCreateVisibility('private');
      navigate(`/knowledge-bases/${created.id}`);
    } catch (err) {
      setCreateError(errorMessage(err, 'Failed to create knowledge base.'));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) {
      return;
    }

    setDetailError(null);
    setIsSaving(true);

    try {
      const updated = await updateKnowledgeBase(selected.id, {
        name: editName.trim(),
        description: editDescription.trim() || null,
        visibility: editVisibility,
      });
      setSelected(updated);
      setItems((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (err) {
      setDetailError(errorMessage(err, 'Failed to update knowledge base.'));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete() {
    if (!selected) {
      return;
    }

    const confirmed = window.confirm(`Delete knowledge base "${selected.name}"?`);
    if (!confirmed) {
      return;
    }

    setDetailError(null);
    setIsDeleting(true);

    try {
      await deleteKnowledgeBase(selected.id);
      setItems((current) => current.filter((item) => item.id !== selected.id));
      setSelected(null);
      navigate('/knowledge-bases', { replace: true });
    } catch (err) {
      setDetailError(errorMessage(err, 'Failed to delete knowledge base.'));
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Knowledge bases</p>
          <h1>Corpus management</h1>
        </div>
        <Link className="secondary-button nav-button" to="/">
          Workspace
        </Link>
      </header>

      {listError && <p className="form-error" role="alert">{listError}</p>}

      <section className="kb-layout" aria-label="Knowledge base management">
        <aside className="kb-sidebar" aria-label="Knowledge base list">
          <div className="section-heading">
            <div>
              <h2>Knowledge base list</h2>
              <p>{items.length} total</p>
            </div>
            <button className="secondary-button compact-button" onClick={() => void loadKnowledgeBases()} type="button">
              Refresh
            </button>
          </div>

          <div className="kb-list">
            {isLoading ? (
              <p className="empty-state">Loading knowledge bases...</p>
            ) : items.length === 0 ? (
              <p className="empty-state">No knowledge bases yet. Create one to start organizing documents.</p>
            ) : (
              items.map((item) => (
                <Link
                  className={item.id === selected?.id ? 'kb-list-item active' : 'kb-list-item'}
                  key={item.id}
                  to={`/knowledge-bases/${item.id}`}
                >
                  <strong>{item.name}</strong>
                  <span>{item.description || 'No description'}</span>
                  <small>{item.visibility}</small>
                </Link>
              ))
            )}
          </div>
        </aside>

        <section className="kb-detail" aria-label="Knowledge base details">
          {selected ? (
            <>
              <div className="detail-header">
                <div>
                  <h2>{selected.name}</h2>
                  <p>{selected.description || 'No description provided.'}</p>
                </div>
                <span className="visibility-badge">{selected.visibility}</span>
              </div>

              <dl className="metadata-grid">
                <div>
                  <dt>ID</dt>
                  <dd><code>{selected.id}</code></dd>
                </div>
                <div>
                  <dt>Owner</dt>
                  <dd><code>{selected.owner_id}</code></dd>
                </div>
                <div>
                  <dt>Created</dt>
                  <dd>{formatDate(selected.created_at)}</dd>
                </div>
                <div>
                  <dt>Updated</dt>
                  <dd>{formatDate(selected.updated_at)}</dd>
                </div>
              </dl>

              <form className="resource-form" onSubmit={handleUpdate}>
                <label className="field">
                  <span>Name</span>
                  <input
                    maxLength={255}
                    minLength={1}
                    onChange={(event) => setEditName(event.target.value)}
                    required
                    type="text"
                    value={editName}
                  />
                </label>

                <label className="field">
                  <span>Description</span>
                  <textarea
                    maxLength={5000}
                    onChange={(event) => setEditDescription(event.target.value)}
                    rows={5}
                    value={editDescription}
                  />
                </label>

                <label className="field">
                  <span>Visibility</span>
                  <select
                    onChange={(event) => setEditVisibility(event.target.value as KnowledgeBaseVisibility)}
                    value={editVisibility}
                  >
                    {visibilityOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>

                {detailError && <p className="form-error" role="alert">{detailError}</p>}

                <div className="form-actions">
                  <button className="primary-button inline-button" disabled={isSaving} type="submit">
                    {isSaving ? 'Saving...' : 'Save changes'}
                  </button>
                  <Link className="secondary-button nav-button" to={`/knowledge-bases/${selected.id}/documents`}>
                    Manage documents
                  </Link>
                  <Link className="secondary-button nav-button" to={`/knowledge-bases/${selected.id}/chat`}>
                    Open chat
                  </Link>
                  <button
                    className="danger-button"
                    disabled={isDeleting}
                    onClick={handleDelete}
                    type="button"
                  >
                    {isDeleting ? 'Deleting...' : 'Delete'}
                  </button>
                </div>
              </form>
            </>
          ) : (
            <div className="empty-detail">
              <h2>Select a knowledge base</h2>
              <p>Choose an item from the list to inspect metadata, update settings, or delete it.</p>
            </div>
          )}
        </section>
      </section>

      <section className="create-panel" aria-labelledby="create-kb-title">
        <div className="section-heading">
          <div>
            <h2 id="create-kb-title">Create knowledge base</h2>
            <p>New knowledge bases are available only to the authenticated owner by default.</p>
          </div>
        </div>

        <form className="resource-form two-column-form" onSubmit={handleCreate}>
          <label className="field">
            <span>Name</span>
            <input
              maxLength={255}
              minLength={1}
              onChange={(event) => setCreateName(event.target.value)}
              placeholder="Engineering handbook"
              required
              type="text"
              value={createName}
            />
          </label>

          <label className="field">
            <span>Visibility</span>
            <select
              onChange={(event) => setCreateVisibility(event.target.value as KnowledgeBaseVisibility)}
              value={createVisibility}
            >
              {visibilityOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <label className="field wide-field">
            <span>Description</span>
            <textarea
              maxLength={5000}
              onChange={(event) => setCreateDescription(event.target.value)}
              placeholder="Scope, owners, and intended retrieval use cases"
              rows={4}
              value={createDescription}
            />
          </label>

          {createError && <p className="form-error wide-field" role="alert">{createError}</p>}

          <button className="primary-button inline-button" disabled={isSaving} type="submit">
            {isSaving ? 'Creating...' : 'Create knowledge base'}
          </button>
        </form>
      </section>
    </main>
  );
}
