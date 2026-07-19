import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import {
  getAnalysisTask,
  listAnalysisResults,
  listAnalysisTasks,
  runAnalysisTask,
} from '../api/analysisTasks';
import { ApiError } from '../api/client';
import type { AnalysisResult, AnalysisTask, JsonObject } from '../api/types';
import { WorkspaceNav } from '../components/WorkspaceNav';

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

function summarizeResult(result: AnalysisResult | null) {
  if (!result) {
    return 'No runs yet';
  }
  const summary = result.result.summary;
  if (typeof summary === 'string' && summary.trim()) {
    return summary;
  }
  return `${Object.keys(result.result).length} output field${Object.keys(result.result).length === 1 ? '' : 's'}`;
}

export function AnalysisTasksPage() {
  const { workspaceId } = useParams();
  const [tasks, setTasks] = useState<AnalysisTask[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [selectedTask, setSelectedTask] = useState<AnalysisTask | null>(null);
  const [results, setResults] = useState<AnalysisResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const [runningTaskId, setRunningTaskId] = useState<string | null>(null);
  const [pageError, setPageError] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const latestResult = results[0] ?? null;
  const statusCounts = useMemo(
    () =>
      tasks.reduce<Record<string, number>>((counts, task) => {
        counts[task.status] = (counts[task.status] ?? 0) + 1;
        return counts;
      }, {}),
    [tasks],
  );

  const loadTasks = useCallback(async () => {
    if (!workspaceId) {
      return;
    }

    setIsLoading(true);
    setPageError(null);

    try {
      const response = await listAnalysisTasks(workspaceId);
      setTasks(response);
      setSelectedTaskId((current) => current ?? response[0]?.id ?? null);
    } catch (err) {
      setPageError(errorMessage(err, 'Failed to load analysis tasks.'));
    } finally {
      setIsLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  useEffect(() => {
    if (!workspaceId || !selectedTaskId) {
      setSelectedTask(null);
      setResults([]);
      return;
    }

    let cancelled = false;
    const wsId = workspaceId;
    const taskId = selectedTaskId;

    async function loadSelectedTask() {
      setIsLoadingResults(true);
      setPageError(null);
      try {
        const [taskResponse, resultsResponse] = await Promise.all([
          getAnalysisTask(wsId, taskId),
          listAnalysisResults(wsId, taskId),
        ]);
        if (!cancelled) {
          setSelectedTask(taskResponse);
          setResults(resultsResponse);
        }
      } catch (err) {
        if (!cancelled) {
          setSelectedTask(null);
          setResults([]);
          setPageError(errorMessage(err, 'Failed to load analysis task details.'));
        }
      } finally {
        if (!cancelled) {
          setIsLoadingResults(false);
        }
      }
    }

    void loadSelectedTask();

    return () => {
      cancelled = true;
    };
  }, [selectedTaskId, workspaceId]);

  if (!workspaceId) {
    return <Navigate to="/workspaces" replace />;
  }

  async function handleRunTask(task: AnalysisTask) {
    if (!workspaceId || runningTaskId) {
      return;
    }

    setRunningTaskId(task.id);
    setRunError(null);
    setTasks((current) => current.map((item) => (item.id === task.id ? { ...item, status: 'running' } : item)));
    if (selectedTask?.id === task.id) {
      setSelectedTask({ ...selectedTask, status: 'running' });
    }

    try {
      const result = await runAnalysisTask(workspaceId, task.id);
      const refreshedTask = await getAnalysisTask(workspaceId, task.id);
      setTasks((current) => current.map((item) => (item.id === refreshedTask.id ? refreshedTask : item)));
      if (selectedTaskId === task.id) {
        setSelectedTask(refreshedTask);
        setResults((current) => [result, ...current.filter((item) => item.id !== result.id)]);
      }
    } catch (err) {
      setRunError(errorMessage(err, 'Failed to run analysis task.'));
      await loadTasks();
    } finally {
      setRunningTaskId(null);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Workspace analysis</p>
          <h1>Analysis tasks</h1>
        </div>
        <div className="topbar-actions">
          <button className="secondary-button nav-button" onClick={() => void loadTasks()} type="button">
            Refresh
          </button>
          <Link className="secondary-button nav-button" to={`/workspaces/${workspaceId}`}>
            Dashboard
          </Link>
        </div>
      </header>

      <WorkspaceNav workspaceId={workspaceId} />

      <section className="status-band" aria-label="Analysis task status summary">
        <div>
          <span className="metric-label">Tasks</span>
          <strong>{tasks.length}</strong>
        </div>
        <div>
          <span className="metric-label">Completed</span>
          <strong>{statusCounts.completed ?? 0}</strong>
        </div>
        <div>
          <span className="metric-label">Pending review</span>
          <strong>{results.filter((result) => result.status === 'ai_generated' || result.status === 'needs_review').length}</strong>
        </div>
      </section>

      {pageError && <p className="form-error" role="alert">{pageError}</p>}
      {runError && <p className="form-error" role="alert">{runError}</p>}

      <section className="analysis-layout" aria-label="Analysis task runner">
        <aside className="analysis-sidebar" aria-label="Analysis task list">
          <div className="section-heading">
            <div>
              <h2>Tasks</h2>
              <p>{isLoading ? 'Loading tasks...' : `${tasks.length} available`}</p>
            </div>
          </div>

          <div className="analysis-task-list">
            {isLoading ? (
              <p className="empty-state">Loading analysis tasks...</p>
            ) : tasks.length === 0 ? (
              <p className="empty-state">No analysis tasks were created for this workspace template.</p>
            ) : (
              tasks.map((task) => (
                <button
                  className={task.id === selectedTaskId ? 'analysis-task-item active' : 'analysis-task-item'}
                  key={task.id}
                  onClick={() => setSelectedTaskId(task.id)}
                  type="button"
                >
                  <span>
                    <strong>{task.name}</strong>
                    <small>{task.task_type}</small>
                  </span>
                  <span className={`status-pill status-${task.status}`}>{task.status}</span>
                </button>
              ))
            )}
          </div>
        </aside>

        <section className="analysis-detail" aria-label="Analysis task details">
          {selectedTask ? (
            <>
              <div className="detail-header">
                <div>
                  <h2>{selectedTask.name}</h2>
                  <p>{selectedTask.description || 'No description provided.'}</p>
                </div>
                <span className={`status-pill status-${selectedTask.status}`}>{selectedTask.status}</span>
              </div>

              <dl className="metadata-grid compact-metadata">
                <div>
                  <dt>Type</dt>
                  <dd>{selectedTask.task_type}</dd>
                </div>
                <div>
                  <dt>Template key</dt>
                  <dd>{selectedTask.template_task_key ?? 'custom'}</dd>
                </div>
                <div>
                  <dt>Updated</dt>
                  <dd>{formatDate(selectedTask.updated_at)}</dd>
                </div>
                <div>
                  <dt>Results</dt>
                  <dd>{results.length}</dd>
                </div>
              </dl>

              <div className="form-actions">
                <button
                  className="primary-button inline-button"
                  disabled={runningTaskId === selectedTask.id}
                  onClick={() => void handleRunTask(selectedTask)}
                  type="button"
                >
                  {runningTaskId === selectedTask.id ? 'Running...' : 'Run analysis'}
                </button>
                <button
                  className="secondary-button nav-button"
                  onClick={() => void loadTasks()}
                  type="button"
                >
                  Refresh status
                </button>
              </div>

              <section className="analysis-result-panel" aria-label="Latest analysis result">
                <div className="section-heading">
                  <div>
                    <h2>Latest result</h2>
                    <p>{isLoadingResults ? 'Loading result...' : summarizeResult(latestResult)}</p>
                  </div>
                  {latestResult && <span className={`status-pill status-${latestResult.status}`}>{latestResult.status}</span>}
                </div>

                {latestResult ? (
                  <div className="analysis-result-grid">
                    <div>
                      <h2>Output</h2>
                      <pre>{formatJson(latestResult.result)}</pre>
                    </div>
                    <div>
                      <h2>Run metadata</h2>
                      <dl className="metadata-grid">
                        <div>
                          <dt>Provider</dt>
                          <dd>{latestResult.provider ?? 'local'}</dd>
                        </div>
                        <div>
                          <dt>Model</dt>
                          <dd>{latestResult.model ?? 'workspace-scoped-retrieval'}</dd>
                        </div>
                        <div>
                          <dt>Confidence</dt>
                          <dd>{latestResult.confidence === null ? 'n/a' : latestResult.confidence.toFixed(2)}</dd>
                        </div>
                        <div>
                          <dt>Created</dt>
                          <dd>{formatDate(latestResult.created_at)}</dd>
                        </div>
                      </dl>

                      <h2>Citations</h2>
                      {latestResult.citations.length === 0 ? (
                        <p className="empty-state">No citations returned.</p>
                      ) : (
                        <pre>{formatJson(latestResult.citations)}</pre>
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="empty-state">Run this task to generate a structured AI result for review.</p>
                )}
              </section>

              <section className="analysis-schema-grid" aria-label="Task configuration">
                <div>
                  <h2>Input scope</h2>
                  <pre>{formatJson(selectedTask.input_scope)}</pre>
                </div>
                <div>
                  <h2>Output schema</h2>
                  <pre>{formatJson(selectedTask.output_schema)}</pre>
                </div>
              </section>
            </>
          ) : (
            <div className="empty-detail">
              <h2>Select an analysis task</h2>
              <p>Choose a task to inspect its schema, run it, and review generated results.</p>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
