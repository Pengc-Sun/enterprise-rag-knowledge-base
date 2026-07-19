import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ApiError } from '../api/client';
import { createWorkspace, listWorkspaceTemplates } from '../api/workspaces';
import type { WorkspaceTemplate } from '../api/types';

function errorMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

function slugify(value: string) {
  const slug = value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
  return slug || 'workspace';
}

function templateCount(template: WorkspaceTemplate, schemaKey: 'directory_schema' | 'analysis_task_schema' | 'report_schema', itemKey: string) {
  const schema = template[schemaKey];
  const value = schema[itemKey];
  return Array.isArray(value) ? value.length : 0;
}

export function WorkspaceCreatePage() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState<WorkspaceTemplate[]>([]);
  const [templateId, setTemplateId] = useState<string>('');
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [description, setDescription] = useState('');
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [templateError, setTemplateError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);

  const selectedTemplate = useMemo(
    () => templates.find((template) => template.id === templateId) ?? null,
    [templateId, templates],
  );

  const loadTemplates = useCallback(async () => {
    setIsLoadingTemplates(true);
    setTemplateError(null);

    try {
      const response = await listWorkspaceTemplates();
      setTemplates(response);
    } catch (err) {
      setTemplateError(errorMessage(err, 'Failed to load workspace templates.'));
    } finally {
      setIsLoadingTemplates(false);
    }
  }, []);

  useEffect(() => {
    void loadTemplates();
  }, [loadTemplates]);

  function handleNameChange(value: string) {
    setName(value);
    setSlug((current) => (current ? current : slugify(value)));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);
    setIsCreating(true);

    try {
      await createWorkspace({
        name: name.trim(),
        slug: slugify(slug),
        description: description.trim() || null,
        template_id: templateId || null,
      });
      navigate('/workspaces');
    } catch (err) {
      setCreateError(errorMessage(err, 'Failed to create workspace.'));
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Workspaces</p>
          <h1>New workspace</h1>
        </div>
        <Link className="secondary-button nav-button" to="/workspaces">
          Workspace list
        </Link>
      </header>

      <form className="workspace-create-layout" onSubmit={handleSubmit}>
        <section className="create-panel" aria-labelledby="workspace-details-title">
          <div className="section-heading">
            <div>
              <h2 id="workspace-details-title">Workspace details</h2>
              <p>Name, URL slug, and project context.</p>
            </div>
          </div>

          <label className="field">
            <span>Name</span>
            <input
              maxLength={255}
              minLength={1}
              onChange={(event) => handleNameChange(event.target.value)}
              placeholder="Policy review"
              required
              type="text"
              value={name}
            />
          </label>

          <label className="field">
            <span>Slug</span>
            <input
              maxLength={100}
              minLength={1}
              onChange={(event) => setSlug(event.target.value)}
              pattern="^[a-z0-9]+(?:-[a-z0-9]+)*$"
              placeholder="policy-review"
              required
              type="text"
              value={slug}
            />
          </label>

          <label className="field">
            <span>Description</span>
            <textarea
              maxLength={5000}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Scope, source documents, reviewers, and expected report output"
              rows={5}
              value={description}
            />
          </label>
        </section>

        <section className="create-panel" aria-labelledby="template-title">
          <div className="section-heading">
            <div>
              <h2 id="template-title">Template</h2>
              <p>{selectedTemplate ? selectedTemplate.name : 'Manual setup'}</p>
            </div>
            <button className="secondary-button compact-button" onClick={() => void loadTemplates()} type="button">
              Refresh
            </button>
          </div>

          {templateError && (
            <p className="form-error" role="alert">
              {templateError}
            </p>
          )}

          <div className="template-list">
            <label className={templateId === '' ? 'template-option active' : 'template-option'}>
              <input
                checked={templateId === ''}
                name="template"
                onChange={() => setTemplateId('')}
                type="radio"
                value=""
              />
              <span>
                <strong>Blank workspace</strong>
                <small>No starter directories, tasks, or report outline.</small>
              </span>
            </label>

            {isLoadingTemplates ? (
              <p className="empty-state">Loading templates...</p>
            ) : (
              templates.map((template) => (
                <label
                  className={template.id === templateId ? 'template-option active' : 'template-option'}
                  key={template.id}
                >
                  <input
                    checked={template.id === templateId}
                    name="template"
                    onChange={() => setTemplateId(template.id)}
                    type="radio"
                    value={template.id}
                  />
                  <span>
                    <strong>{template.name}</strong>
                    <small>{template.description || template.category}</small>
                    <em>
                      {template.category} · {templateCount(template, 'directory_schema', 'directories')} directories ·{' '}
                      {templateCount(template, 'analysis_task_schema', 'tasks')} tasks ·{' '}
                      {templateCount(template, 'report_schema', 'sections')} report sections
                    </em>
                  </span>
                </label>
              ))
            )}
          </div>

          {createError && (
            <p className="form-error" role="alert">
              {createError}
            </p>
          )}

          <button className="primary-button" disabled={isCreating} type="submit">
            {isCreating ? 'Creating...' : 'Create workspace'}
          </button>
        </section>
      </form>
    </main>
  );
}
