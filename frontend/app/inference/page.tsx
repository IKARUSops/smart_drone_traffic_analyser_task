"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";

import Link from "next/link";

import LinePicker from "@/components/LinePicker";
import MediaPlayer from "@/components/MediaPlayer";
import { RegionSelectionRequest, ResultResponse, StatusResponse, UploadResponse } from "@/types/api";

type Step = "upload" | "line" | "processing" | "result" | "cancelled" | "error";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const STEP_LABELS: Record<Step, string> = {
  upload: "Step 1 of 4 - Upload",
  line: "Step 2 of 4 - Define region",
  processing: "Step 3 of 4 - Processing",
  result: "Step 4 of 4 - Results",
  cancelled: "Flow cancelled",
  error: "Flow interrupted",
};

export default function InferencePage() {
  const [step, setStep] = useState<Step>("upload");
  const [taskId, setTaskId] = useState<string>("");
  const [taskToken, setTaskToken] = useState<string>("");
  const [frameUrl, setFrameUrl] = useState<string>("");
  const [videoSrc, setVideoSrc] = useState<string>("");
  const [videoDownloadUrl, setVideoDownloadUrl] = useState<string>("");
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [result, setResult] = useState<ResultResponse | null>(null);
  const [error, setError] = useState<string>("");
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [isCancelling, setIsCancelling] = useState<boolean>(false);
  const [cancelNotice, setCancelNotice] = useState<string>("");
  const [reportFormat, setReportFormat] = useState<"csv" | "xlsx">("csv");

  const canUpload = useMemo(() => !isUploading && step === "upload", [isUploading, step]);

  useEffect(() => {
    return () => {
      if (frameUrl) {
        URL.revokeObjectURL(frameUrl);
      }
    };
  }, [frameUrl]);

  const uploadVideo = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !canUpload) {
      return;
    }

    setIsUploading(true);
    setError("");

    try {
      const formData = new FormData();
      formData.append("video", file);

      const response = await fetch(`${API_BASE_URL}/api/v1/tasks/upload`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error("Upload failed");
      }

      const payload: UploadResponse = await response.json();
      setTaskId(payload.task_id);
      setTaskToken(payload.access_token);

      const frameResponse = await fetch(`${API_BASE_URL}${payload.frame_url}`, {
        headers: { "X-Task-Token": payload.access_token },
      });
      if (!frameResponse.ok) {
        throw new Error("Unable to load frame preview");
      }
      const frameBlob = await frameResponse.blob();
      setFrameUrl(URL.createObjectURL(frameBlob));
      setStep("line");
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Upload failed");
      setStep("error");
    } finally {
      setIsUploading(false);
    }
  };

  const submitLine = async (payload: RegionSelectionRequest) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v2/tasks/${taskId}/region`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Task-Token": taskToken,
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error("Failed to submit region");
      }

      setStep("processing");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to submit region");
      setStep("error");
    }
  };

  const requestCancellation = async () => {
    if (!taskId || !taskToken || isCancelling) {
      return;
    }

    setIsCancelling(true);
    setCancelNotice("");

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/tasks/${taskId}/cancel`, {
        method: "POST",
        headers: { "X-Task-Token": taskToken },
      });
      if (!response.ok) {
        throw new Error("Failed to request cancellation");
      }

      setCancelNotice("Cancellation requested. Waiting for the worker to stop.");
    } catch (cancelError) {
      setError(cancelError instanceof Error ? cancelError.message : "Failed to request cancellation");
      setStep("error");
    } finally {
      setIsCancelling(false);
    }
  };

  useEffect(() => {
    if (step !== "processing" || !taskId || !taskToken) {
      return;
    }

    const interval = window.setInterval(async () => {
      try {
        const statusResponse = await fetch(`${API_BASE_URL}/api/v1/tasks/${taskId}/status`, {
          headers: { "X-Task-Token": taskToken },
        });
        if (!statusResponse.ok) {
          throw new Error("Status polling failed");
        }

        const statusPayload: StatusResponse = await statusResponse.json();
        setStatus(statusPayload);

        if (statusPayload.cancellation_requested) {
          setCancelNotice("Cancellation requested. Waiting for the worker to stop.");
        }

        if (statusPayload.status === "completed") {
          window.clearInterval(interval);
          const resultResponse = await fetch(`${API_BASE_URL}/api/v1/tasks/${taskId}/result`, {
            headers: { "X-Task-Token": taskToken },
          });
          if (!resultResponse.ok) {
            throw new Error("Result retrieval failed");
          }
          const resultPayload: ResultResponse = await resultResponse.json();
          const token = encodeURIComponent(taskToken);
          setVideoSrc(`${API_BASE_URL}${resultPayload.video_url}?task_token=${token}`);
          setVideoDownloadUrl(`${API_BASE_URL}${resultPayload.download_url}?task_token=${token}`);

          setResult(resultPayload);
          setStep("result");
        }

        if (statusPayload.status === "failed") {
          window.clearInterval(interval);
          setError(statusPayload.error ?? "Processing failed");
          setStep("error");
        }

        if (statusPayload.status === "cancelled") {
          window.clearInterval(interval);
          setStep("cancelled");
        }
      } catch (pollError) {
        window.clearInterval(interval);
        setError(pollError instanceof Error ? pollError.message : "Polling failed");
        setStep("error");
      }
    }, 2000);

    return () => window.clearInterval(interval);
  }, [step, taskId, taskToken]);

  const downloadReport = () => {
    if (!taskId || !taskToken) {
      return;
    }

    (async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/tasks/${taskId}/report?format=${reportFormat}`, {
          headers: { "X-Task-Token": taskToken },
        });
        if (!response.ok) {
          setError("Report download failed");
          setStep("error");
          return;
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `${taskId}-report.${reportFormat}`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
      } catch {
        setError("Report download failed");
        setStep("error");
      }
    })();
  };

  return (
    <div className="page-stack inference-page">
      <section className="workspace-banner">
        <div>
          <p className="eyebrow">Inference workflow</p>
          <h1>Upload a clip, place the counting region, and run traffic analysis.</h1>
          <p className="hero-text">
            The backend extracts frame 20 for region placement, then tracks and counts edge crossings before generating the report.
          </p>
        </div>

        <div className="workspace-links">
          <Link className="button-secondary" href="/">
            Back to home
          </Link>
          <Link className="button-secondary" href="/dashboard">
            Open dashboard stub
          </Link>
        </div>
      </section>

      <div className="app-shell">
        <header className="app-header">
          <div>
            <p className="eyebrow">Smart Drone Traffic Analyzer</p>
            <h2>Traffic Intelligence Dashboard</h2>
            <p className="subtitle">
              Upload one video, define one counting region, and extract directional flow metrics.
            </p>
          </div>
          <span className="step-badge">{STEP_LABELS[step]}</span>
        </header>

        {step === "upload" && (
          <section className="panel">
            <h2>Upload Video</h2>
            <p>After upload, frame 20 opens for 4-point region placement before processing starts.</p>
            <div className="upload-drop">
              <label>
                {isUploading ? "Uploading..." : "Select Video File"}
                <input
                  className="hidden-file-input"
                  type="file"
                  accept="video/*"
                  onChange={uploadVideo}
                  disabled={!canUpload}
                />
              </label>
              <small>Recommended format: MP4. Maximum quality input provides better tracking stability.</small>
            </div>
          </section>
        )}

        {step === "line" && <LinePicker imageUrl={frameUrl} onConfirm={submitLine} />}

        {step === "processing" && (
          <section className="panel">
            <h2>Processing Video</h2>
            <p>Tracking vehicles and evaluating directional crossings.</p>
            <div className="processing-meta">
              <span className="stage-chip">{status?.stage ?? "Initializing model"}</span>
              <span>{(status?.progress_percent ?? 0).toFixed(1)}% complete</span>
            </div>
            {cancelNotice && <p className="notice-text">{cancelNotice}</p>}
            <progress value={status?.progress_percent ?? 0} max={100} />
            <div className="stat-grid">
              <article>
                <h3>Progress</h3>
                <p>{(status?.progress_percent ?? 0).toFixed(1)}%</p>
              </article>
              <article>
                <h3>Frames</h3>
                <p>
                  {status?.processed_frames ?? 0} / {status?.total_frames ?? 0}
                </p>
              </article>
              <article>
                <h3>Processing FPS</h3>
                <p>{status?.fps ?? 0}</p>
              </article>
            </div>
            <div className="controls">
              <button className="secondary" type="button" onClick={requestCancellation} disabled={isCancelling || !!status?.cancellation_requested}>
                {status?.cancellation_requested ? "Cancellation requested" : isCancelling ? "Requesting cancellation..." : "Cancel processing"}
              </button>
            </div>
          </section>
        )}

        {step === "result" && result && (
          <section className="result-grid">
            <div className="panel result-summary">
              <h2>Analysis Completed</h2>
              <p>Directional counts are computed after edge-crossing verification with track-level deduplication.</p>
              <div className="stat-grid">
                <article>
                  <h3>Total unique vehicles</h3>
                  <p>{result.total_unique_vehicles}</p>
                </article>
                <article>
                  <h3>North</h3>
                  <p>{result.per_direction_count.North ?? 0}</p>
                </article>
                <article>
                  <h3>South</h3>
                  <p>{result.per_direction_count.South ?? 0}</p>
                </article>
                <article>
                  <h3>East</h3>
                  <p>{result.per_direction_count.East ?? 0}</p>
                </article>
                <article>
                  <h3>West</h3>
                  <p>{result.per_direction_count.West ?? 0}</p>
                </article>
                <article>
                  <h3>Processing time (s)</h3>
                  <p>{result.processing_time_seconds}</p>
                </article>
              </div>
            </div>

            <div className="panel result-media">
              <MediaPlayer src={videoSrc} downloadUrl={videoDownloadUrl} poster={frameUrl} title="Processed output video" />
              <section className="downloads result-downloads">
                <label>
                  Report format
                  <select
                    value={reportFormat}
                    onChange={(event) => setReportFormat(event.target.value as "csv" | "xlsx")}
                  >
                    <option value="csv">CSV</option>
                    <option value="xlsx">XLSX</option>
                  </select>
                </label>
                <button className="primary" type="button" onClick={downloadReport}>
                  Download report
                </button>
              </section>
            </div>
          </section>
        )}

        {step === "error" && (
          <section className="panel error-panel">
            <h2>Request Failed</h2>
            <p>{error || "Unknown error"}</p>
            <button className="primary" type="button" onClick={() => window.location.reload()}>
              Restart flow
            </button>
          </section>
        )}

        {step === "cancelled" && (
          <section className="panel cancelled-panel">
            <h2>Processing Cancelled</h2>
            <p>Your cancellation request was applied and processing has stopped for this task.</p>
            <button className="primary" type="button" onClick={() => window.location.reload()}>
              Start new analysis
            </button>
          </section>
        )}
      </div>
    </div>
  );
}