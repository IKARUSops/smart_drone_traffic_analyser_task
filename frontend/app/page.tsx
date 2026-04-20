"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";

import LinePicker from "@/components/LinePicker";
import { ResultResponse, StatusResponse, UploadResponse } from "@/types/api";

type Step = "upload" | "line" | "processing" | "result" | "error";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function HomePage() {
  const [step, setStep] = useState<Step>("upload");
  const [taskId, setTaskId] = useState<string>("");
  const [taskToken, setTaskToken] = useState<string>("");
  const [frameUrl, setFrameUrl] = useState<string>("");
  const [videoUrl, setVideoUrl] = useState<string>("");
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [result, setResult] = useState<ResultResponse | null>(null);
  const [error, setError] = useState<string>("");
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [reportFormat, setReportFormat] = useState<"csv" | "xlsx">("csv");

  const canUpload = useMemo(() => !isUploading && step === "upload", [isUploading, step]);

  useEffect(() => {
    return () => {
      if (frameUrl) {
        URL.revokeObjectURL(frameUrl);
      }
      if (videoUrl) {
        URL.revokeObjectURL(videoUrl);
      }
    };
  }, [frameUrl, videoUrl]);

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

  const submitLine = async (payload: {
    line_points: number[][];
    image_width: number;
    image_height: number;
    scene_mode: "auto" | "top_down" | "angled";
  }) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/tasks/${taskId}/line`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Task-Token": taskToken,
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error("Failed to submit line");
      }

      setStep("processing");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to submit line");
      setStep("error");
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

        if (statusPayload.status === "completed") {
          window.clearInterval(interval);
          const resultResponse = await fetch(`${API_BASE_URL}/api/v1/tasks/${taskId}/result`, {
            headers: { "X-Task-Token": taskToken },
          });
          if (!resultResponse.ok) {
            throw new Error("Result retrieval failed");
          }
          const resultPayload: ResultResponse = await resultResponse.json();

          const videoResponse = await fetch(`${API_BASE_URL}${resultPayload.video_url}`, {
            headers: { "X-Task-Token": taskToken },
          });
          if (!videoResponse.ok) {
            throw new Error("Processed video retrieval failed");
          }
          const videoBlob = await videoResponse.blob();
          setVideoUrl(URL.createObjectURL(videoBlob));

          setResult(resultPayload);
          setStep("result");
        }

        if (statusPayload.status === "failed") {
          window.clearInterval(interval);
          setError(statusPayload.error ?? "Processing failed");
          setStep("error");
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
    <main className="page-root">
      <div className="app-shell">
        <header>
          <p className="eyebrow">Smart Drone Traffic Analyzer</p>
          <h1>Vehicle Flow Intelligence From A Single Video</h1>
        </header>

        {step === "upload" && (
          <section className="panel">
            <h2>Upload your traffic video</h2>
            <p>After upload, frame 20 will open for line placement before processing starts.</p>
            <input type="file" accept="video/*" onChange={uploadVideo} disabled={!canUpload} />
          </section>
        )}

        {step === "line" && <LinePicker imageUrl={frameUrl} onConfirm={submitLine} />}

        {step === "processing" && (
          <section className="panel">
            <h2>Processing video and tracking vehicles</h2>
            <p>{status?.stage ?? "Initializing model"}</p>
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
          </section>
        )}

        {step === "result" && result && (
          <section className="panel">
            <h2>Analysis completed</h2>
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

            <video controls width={900} src={videoUrl} />

            <section className="downloads">
              <label>
                Report format
                <select value={reportFormat} onChange={(event) => setReportFormat(event.target.value as "csv" | "xlsx")}>
                  <option value="csv">CSV</option>
                  <option value="xlsx">XLSX</option>
                </select>
              </label>
              <button type="button" onClick={downloadReport}>
                Download report
              </button>
            </section>
          </section>
        )}

        {step === "error" && (
          <section className="panel error-panel">
            <h2>Something failed</h2>
            <p>{error || "Unknown error"}</p>
            <button type="button" onClick={() => window.location.reload()}>
              Restart flow
            </button>
          </section>
        )}
      </div>
    </main>
  );
}
