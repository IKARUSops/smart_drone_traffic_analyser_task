"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  DashboardTaskDetailResponse,
  DashboardTaskSummaryResponse,
} from "@/types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function formatDate(value: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

export default function DashboardPage() {
  const [tasks, setTasks] = useState<DashboardTaskSummaryResponse[]>([]);
  const [selectedTask, setSelectedTask] = useState<DashboardTaskDetailResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [detailsLoading, setDetailsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  const taskCount = tasks.length;
  const completedCount = useMemo(() => tasks.filter((item) => item.status === "completed").length, [tasks]);

  const refreshTasks = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/dashboard/tasks`, { cache: "no-store" });
      if (!response.ok) {
        throw new Error("Unable to load dashboard tasks");
      }
      const payload: DashboardTaskSummaryResponse[] = await response.json();
      setTasks(payload);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "Unable to load dashboard tasks");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refreshTasks();
  }, []);

  const openTaskDetails = async (taskId: string) => {
    setDetailsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/dashboard/tasks/${taskId}`);
      if (!response.ok) {
        throw new Error("Unable to load task details");
      }
      const payload: DashboardTaskDetailResponse = await response.json();
      setSelectedTask(payload);
    } catch (detailError) {
      setError(detailError instanceof Error ? detailError.message : "Unable to load task details");
    } finally {
      setDetailsLoading(false);
    }
  };

  const deleteTask = async (taskId: string) => {
    const ok = window.confirm("Delete this task and all stored artifacts?");
    if (!ok) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/dashboard/tasks/${taskId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error("Unable to delete task");
      }
      setTasks((current) => current.filter((item) => item.task_id !== taskId));
      if (selectedTask?.task_id === taskId) {
        setSelectedTask(null);
      }
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Unable to delete task");
    }
  };

  return (
    <div className="page-stack">
      <section className="workspace-banner">
        <div>
          <p className="eyebrow">Dashboard</p>
          <h1>SQLite-backed task history with direct playback, reports, and delete controls.</h1>
          <p className="hero-text">
            Browse completed and in-progress tasks, open details in a popup, and download video or report artifacts without leaving the dashboard.
          </p>
        </div>

        <div className="workspace-links">
          <Link className="button-primary" href="/inference">
            Open inference flow
          </Link>
          <button className="button-secondary" type="button" onClick={() => void refreshTasks()}>
            Refresh
          </button>
        </div>
      </section>

      <section className="feature-grid dashboard-grid">
        <article className="feature-card">
          <p className="card-label">Stored tasks</p>
          <h3>{taskCount}</h3>
          <p>Total persisted rows in SQLite storage.</p>
        </article>
        <article className="feature-card">
          <p className="card-label">Completed</p>
          <h3>{completedCount}</h3>
          <p>Tasks that finished and can be opened directly.</p>
        </article>
        <article className="feature-card">
          <p className="card-label">Storage mode</p>
          <h3>Compressed</h3>
          <p>Task results are stored as compressed blobs for efficiency.</p>
        </article>
      </section>

      <section className="panel dashboard-table-wrap">
        <h2>Task History</h2>
        {error && <p className="error-text">{error}</p>}
        {loading ? (
          <p className="hero-text">Loading tasks...</p>
        ) : tasks.length === 0 ? (
          <p className="hero-text">No persisted tasks yet. Run inference to populate the dashboard.</p>
        ) : (
          <div className="dashboard-table-scroll">
            <table className="dashboard-table">
              <thead>
                <tr>
                  <th>Task ID</th>
                  <th>Status</th>
                  <th>Updated</th>
                  <th>Total vehicles</th>
                  <th>Processing time</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.task_id}>
                    <td>{task.task_id}</td>
                    <td>{task.status}</td>
                    <td>{formatDate(task.updated_at)}</td>
                    <td>{task.total_unique_vehicles}</td>
                    <td>{task.processing_time_seconds.toFixed(2)}s</td>
                    <td className="dashboard-actions-cell">
                      <button className="secondary" type="button" onClick={() => void openTaskDetails(task.task_id)}>
                        View
                      </button>
                      <button className="secondary" type="button" onClick={() => void deleteTask(task.task_id)}>
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {selectedTask && (
        <div className="modal-backdrop" onClick={() => setSelectedTask(null)}>
          <section className="modal-card" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <div>
                <p className="card-label">Task detail</p>
                <h2>{selectedTask.task_id}</h2>
              </div>
              <button className="secondary" type="button" onClick={() => setSelectedTask(null)}>
                Close
              </button>
            </div>

            {detailsLoading ? (
              <p className="hero-text">Loading details...</p>
            ) : (
              <>
                <div className="stat-grid">
                  <article>
                    <h3>Status</h3>
                    <p>{selectedTask.status}</p>
                  </article>
                  <article>
                    <h3>Updated</h3>
                    <p>{formatDate(selectedTask.updated_at)}</p>
                  </article>
                  <article>
                    <h3>Scene mode</h3>
                    <p>{selectedTask.scene_mode ?? "-"}</p>
                  </article>
                  <article>
                    <h3>Orientation</h3>
                    <p>{selectedTask.region_orientation ?? "-"}</p>
                  </article>
                </div>

                <div className="downloads dashboard-modal-downloads">
                  <a className="primary" href={`${API_BASE_URL}${selectedTask.video_stream_url}`} target="_blank" rel="noreferrer">
                    View video
                  </a>
                  <a className="secondary" href={`${API_BASE_URL}${selectedTask.video_download_url}`} target="_blank" rel="noreferrer">
                    Download video
                  </a>
                  <a className="secondary" href={`${API_BASE_URL}${selectedTask.report_csv_url}`} target="_blank" rel="noreferrer">
                    CSV report
                  </a>
                  <a className="secondary" href={`${API_BASE_URL}${selectedTask.report_xlsx_url}`} target="_blank" rel="noreferrer">
                    XLSX report
                  </a>
                </div>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}