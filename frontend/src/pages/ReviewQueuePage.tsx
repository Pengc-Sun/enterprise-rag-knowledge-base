import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { createReviewDecision, listReviewQueue } from '../api/analysisTasks';
import { ApiError } from '../api/client';
import type {
  AnalysisResultStatus,
  AnalysisReviewQueueItem,
  JsonObject,
  ReviewDecisionType,
} from '../api/types';
import { WorkspaceNav } from '../components/WorkspaceNav';

type ReviewFilter = AnalysisResultStatus | 'open';

const reviewFilterOptions: Array<{ label: string; value: ReviewFilter }> = [
  { label: 'Open', value: 'open' },
  { label: 'AI generated', value: 'ai_generated' },
  { label: 'Needs review', value: 'needs_review' },
  { label: 'Approved', value: 'approved' },
  { label: 'Edited', value: 'edited' },
  { label: 'Rejected', value: 'rejected' },
];

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function errorMessage(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

function formatJson(value: JsonObject | JsonObject[]) {
  return JSON.stringify(value, null, 2);
}

function summarizeQueueItem(item: AnalysisReviewQueueItem) {
  const summary = item.analysis_result.result.summary;
  if (typeof summary === 'string' && summary.trim()) {
    return summary;
  }
  return item.analysis_task.description || 'Structured AI result awaiting reviewer decision.';
}

function parseEditedResult(value: string): JsonObject {
  const parsed = JSON.parse(value) as unknown;
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('Edited result must be a JSON object.');
  }
  return parsed as JsonObject;
}

export function ReviewQueuePage() {
  const { workspaceId } = useParams();
  const [queueItems, setQueueItems] = useState<AnalysisReviewQueueItem[]>([]);
  const [selectedResultId, setSelectedResultId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<ReviewFilter>('open');
  const [comment, setComment] = useState('');
  const [editJson, setEditJson] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [decisionInFlight, setDecisionInFlight] = useState<ReviewDecisionType | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);

  const selectedItem = useMemo(
    () => queueItems.find((item) => item.analysis_result.id === selectedResultId) ?? null,
    [queueItems, selectedResultId],
  );
  const openCount = queueItems.filter(
    (item) => item.analysis_result.status === 'ai_generated' || item.analysis_result.status === 'needs_review',
  ).length;

  const loadQueue = useCallback(async () => {
    if (!workspaceId) {
      return;
    }

    setIsLoading(true);
    setPageError(null);

    try {
      const response = await listReviewQueue(
        workspaceId,
        statusFilter === 'open' ? {} : { status: statusFilter },
      );
      setQueueItems(response);
      setSelectedResultId((current) =>
        response.some((item) => item.analysis_result.id === current)
          ? current
          : response[0]?.analysis_result.id ?? null,
      );
    } catch (err) {
      setPageError(errorMessage(err, 'Failed to load review queue.'));
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter, workspaceId]);

  useEffect(() => {
    void loadQueue();
  }, [loadQueue]);

  useEffect(() => {
    if (!selectedItem) {
      setComment('');
      setEditJson('');
      return;
    }

    setComment('');
    setDecisionError(null);
    setEditJson(formatJson(selectedItem.analysis_result.result));
  }, [selectedItem]);

  if (!workspaceId) {
    return <Navigate to="/workspaces" replace />;
  }

  async function submitDecision(decision: ReviewDecisionType, editedResult?: JsonObject) {
    if (!workspaceId || !selectedItem || decisionInFlight) {
      return;
    }

    setDecisionInFlight(decision);
    setDecisionError(null);

    try {
      await createReviewDecision(
        workspaceId,
        selectedItem.analysis_task.id,
        selectedItem.analysis_result.id,
        {
          decision,
          comment: comment.trim() || null,
          edited_result: editedResult ?? null,
        },
      );
      await loadQueue();
    } catch (err) {
      setDecisionError(errorMessage(err, 'Failed to submit review decision.'));
    } finally {
      setDecisionInFlight(null);
    }
  }

  async function handleEditSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    try {
      await submitDecision('edit', parseEditedResult(editJson));
    } catch (err) {
      setDecisionError(err instanceof Error ? err.message : 'Edited result must be valid JSON.');
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Workspace review</p>
          <h1>Review queue</h1>
        </div>
        <div className="topbar-actions">
          <button className="secondary-button nav-button" onClick={() => void loadQueue()} type="button">
            Refresh
          </button>
          <Link className="secondary-button nav-button" to={`/workspaces/${workspaceId}`}>
            Dashboard
          </Link>
        </div>
      </header>

      <WorkspaceNav workspaceId={workspaceId} />

      <section className="status-band" aria-label="Review queue summary">
        <div>
          <span className="metric-label">Visible results</span>
          <strong>{queueItems.length}</strong>
        </div>
        <div>
          <span className="metric-label">Open</span>
          <strong>{openCount}</strong>
        </div>
        <div>
          <span className="metric-label">Filter</span>
          <select
            aria-label="Review status filter"
            className="compact-select"
            onChange={(event) => setStatusFilter(event.target.value as ReviewFilter)}
            value={statusFilter}
          >
            {reviewFilterOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </section>

      {pageError && <p className="form-error" role="alert">{pageError}</p>}
      {decisionError && <p className="form-error" role="alert">{decisionError}</p>}

      <section className="review-layout" aria-label="Review queue workspace">
        <aside className="review-sidebar" aria-label="Review queue list">
          <div className="section-heading">
            <div>
              <h2>Results</h2>
              <p>{isLoading ? 'Loading queue...' : `${queueItems.length} result${queueItems.length === 1 ? '' : 's'}`}</p>
            </div>
          </div>

          <div className="review-list">
            {isLoading ? (
              <p className="empty-state">Loading review queue...</p>
            ) : queueItems.length === 0 ? (
              <p className="empty-state">No analysis results match this review filter.</p>
            ) : (
              queueItems.map((item) => (
                <button
                  className={item.analysis_result.id === selectedResultId ? 'review-item active' : 'review-item'}
                  key={item.analysis_result.id}
                  onClick={() => setSelectedResultId(item.analysis_result.id)}
                  type="button"
                >
                  <span>
                    <strong>{item.analysis_task.name}</strong>
                    <small>{summarizeQueueItem(item)}</small>
                  </span>
                  <span className={`status-pill status-${item.analysis_result.status}`}>
                    {item.analysis_result.status}
                  </span>
                </button>
              ))
            )}
          </div>
        </aside>

        <section className="review-detail" aria-label="Review decision detail">
          {selectedItem ? (
            <>
              <div className="detail-header">
                <div>
                  <h2>{selectedItem.analysis_task.name}</h2>
                  <p>{selectedItem.analysis_task.description || 'No task description provided.'}</p>
                </div>
                <span className={`status-pill status-${selectedItem.analysis_result.status}`}>
                  {selectedItem.analysis_result.status}
                </span>
              </div>

              <dl className="metadata-grid compact-metadata">
                <div>
                  <dt>Task type</dt>
                  <dd>{selectedItem.analysis_task.task_type}</dd>
                </div>
                <div>
                  <dt>Provider</dt>
                  <dd>{selectedItem.analysis_result.provider ?? 'local'}</dd>
                </div>
                <div>
                  <dt>Confidence</dt>
                  <dd>
                    {selectedItem.analysis_result.confidence === null
                      ? 'n/a'
                      : selectedItem.analysis_result.confidence.toFixed(2)}
                  </dd>
                </div>
                <div>
                  <dt>Generated</dt>
                  <dd>{formatDate(selectedItem.analysis_result.created_at)}</dd>
                </div>
              </dl>

              <section className="review-output-grid" aria-label="AI result and citations">
                <div>
                  <h2>AI result</h2>
                  <pre>{formatJson(selectedItem.analysis_result.result)}</pre>
                </div>
                <div>
                  <h2>Citations</h2>
                  {selectedItem.analysis_result.citations.length === 0 ? (
                    <p className="empty-state">No citations returned.</p>
                  ) : (
                    <pre>{formatJson(selectedItem.analysis_result.citations)}</pre>
                  )}
                </div>
              </section>

              <section className="review-actions-panel" aria-label="Review actions">
                <label className="field">
                  <span>Comment</span>
                  <textarea
                    maxLength={5000}
                    onChange={(event) => setComment(event.target.value)}
                    placeholder="Optional reviewer note"
                    rows={3}
                    value={comment}
                  />
                </label>

                <div className="form-actions">
                  <button
                    className="primary-button inline-button"
                    disabled={decisionInFlight !== null}
                    onClick={() => void submitDecision('approve')}
                    type="button"
                  >
                    {decisionInFlight === 'approve' ? 'Approving...' : 'Approve'}
                  </button>
                  <button
                    className="danger-button"
                    disabled={decisionInFlight !== null}
                    onClick={() => void submitDecision('reject')}
                    type="button"
                  >
                    {decisionInFlight === 'reject' ? 'Rejecting...' : 'Reject'}
                  </button>
                </div>

                <form className="review-edit-form" onSubmit={handleEditSubmit}>
                  <label className="field">
                    <span>Edited result JSON</span>
                    <textarea
                      onChange={(event) => setEditJson(event.target.value)}
                      rows={12}
                      spellCheck={false}
                      value={editJson}
                    />
                  </label>
                  <button className="secondary-button inline-button" disabled={decisionInFlight !== null} type="submit">
                    {decisionInFlight === 'edit' ? 'Saving edit...' : 'Save edit'}
                  </button>
                </form>
              </section>
            </>
          ) : (
            <div className="empty-detail">
              <h2>Select a result</h2>
              <p>Choose an AI-generated result to approve, edit, or reject.</p>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
