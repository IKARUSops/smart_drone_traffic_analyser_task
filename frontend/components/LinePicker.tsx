"use client";

import { useEffect, useRef, useState } from "react";

type SceneMode = "auto" | "top_down" | "angled";
type RegionOrientation = "horizontal" | "vertical";

type Props = {
  imageUrl: string;
  onConfirm: (payload: {
    box_points: number[][];
    image_width: number;
    image_height: number;
    scene_mode: SceneMode;
    region_orientation: RegionOrientation;
  }) => void;
};

export default function LinePicker({ imageUrl, onConfirm }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [points, setPoints] = useState<number[][]>([]);
  const [hoverPoint, setHoverPoint] = useState<number[] | null>(null);
  const [sceneMode, setSceneMode] = useState<SceneMode>("auto");
  const [regionOrientation, setRegionOrientation] = useState<RegionOrientation>("horizontal");
  const [validationError, setValidationError] = useState<string>("");

  const isConvexQuad = (quadPoints: number[][]): boolean => {
    if (quadPoints.length !== 4) {
      return false;
    }

    const cross = (o: number[], a: number[], b: number[]) =>
      (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);

    const signs: number[] = [];
    for (let i = 0; i < 4; i += 1) {
      const c = cross(quadPoints[i], quadPoints[(i + 1) % 4], quadPoints[(i + 2) % 4]);
      if (c === 0) {
        return false;
      }
      signs.push(c > 0 ? 1 : -1);
    }

    return signs.every((sign) => sign === signs[0]);
  };

  const redraw = () => {
    const canvas = canvasRef.current;
    const image = imageRef.current;
    if (!canvas || !image) {
      return;
    }

    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return;
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);

    points.forEach((point, index) => {
      ctx.fillStyle = "#ffcc00";
      ctx.beginPath();
      ctx.arc(point[0], point[1], 6, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "#111111";
      ctx.font = "bold 14px Space Mono, monospace";
      ctx.fillText(`P${index + 1}`, point[0] + 10, point[1] - 10);
    });

    if (points.length >= 2) {
      ctx.strokeStyle = "#12ff8a";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(points[0][0], points[0][1]);
      for (let i = 1; i < points.length; i += 1) {
        ctx.lineTo(points[i][0], points[i][1]);
      }
      if (points.length === 4) {
        ctx.closePath();
      }
      ctx.stroke();
    }

    if (hoverPoint && points.length >= 1 && points.length < 4) {
      const last = points[points.length - 1];
      ctx.strokeStyle = "#7fd8ff";
      ctx.setLineDash([8, 6]);
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(last[0], last[1]);
      ctx.lineTo(hoverPoint[0], hoverPoint[1]);

      if (points.length === 3) {
        // Preview closure back to P1 for easier box-shape estimation.
        ctx.lineTo(points[0][0], points[0][1]);
      }
      ctx.stroke();
      ctx.setLineDash([]);
    }
  };

  useEffect(() => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.src = imageUrl;
    image.onload = () => {
      imageRef.current = image;
      const canvas = canvasRef.current;
      if (!canvas) {
        return;
      }

      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      redraw();
    };
  }, [imageUrl]);

  useEffect(() => {
    redraw();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [points, hoverPoint]);

  const handleCanvasClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (points.length >= 4) {
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const x = Math.round((event.clientX - rect.left) * scaleX);
    const y = Math.round((event.clientY - rect.top) * scaleY);

    setPoints((current) => [...current, [x, y]]);
    setValidationError("");
  };

  const handleCanvasMove = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (points.length === 0 || points.length >= 4) {
      setHoverPoint(null);
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) {
      return;
    }

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    const x = Math.round((event.clientX - rect.left) * scaleX);
    const y = Math.round((event.clientY - rect.top) * scaleY);
    setHoverPoint([x, y]);
  };

  const handleCanvasLeave = () => {
    setHoverPoint(null);
  };

  const resetPoints = () => {
    setPoints([]);
    setHoverPoint(null);
    setValidationError("");
  };

  const confirmPoints = () => {
    const canvas = canvasRef.current;
    if (!canvas || points.length !== 4) {
      return;
    }

    if (!isConvexQuad(points)) {
      setValidationError("Points must form a convex quadrilateral in order (clockwise or counter-clockwise).");
      return;
    }

    onConfirm({
      box_points: points,
      image_width: canvas.width,
      image_height: canvas.height,
      scene_mode: sceneMode,
      region_orientation: regionOrientation,
    });
  };

  return (
    <section className="line-picker">
      <h2>Define Counting Region On Frame 20</h2>
      <p>
        Click four times in order around the lane region (for example: top-left, top-right, bottom-right, bottom-left).
      </p>

      <div className="picker-top-row">
        <label className="mode-row">
          Scene mode:
          <select value={sceneMode} onChange={(event) => setSceneMode(event.target.value as SceneMode)}>
            <option value="auto">Auto</option>
            <option value="top_down">Top-down drone</option>
            <option value="angled">Angled road</option>
          </select>
        </label>
        <label className="mode-row">
          Region orientation:
          <select
            value={regionOrientation}
            onChange={(event) => setRegionOrientation(event.target.value as RegionOrientation)}
          >
            <option value="horizontal">Horizontal flow (monitor top/bottom edges)</option>
            <option value="vertical">Vertical flow (monitor left/right edges)</option>
          </select>
        </label>
        <div className="point-list">
          <span className="point-pill">P1: {points[0] ? `${points[0][0]}, ${points[0][1]}` : "Not set"}</span>
          <span className="point-pill">P2: {points[1] ? `${points[1][0]}, ${points[1][1]}` : "Not set"}</span>
          <span className="point-pill">P3: {points[2] ? `${points[2][0]}, ${points[2][1]}` : "Not set"}</span>
          <span className="point-pill">P4: {points[3] ? `${points[3][0]}, ${points[3][1]}` : "Not set"}</span>
        </div>
      </div>

      <canvas
        ref={canvasRef}
        className="line-canvas"
        onClick={handleCanvasClick}
        onMouseMove={handleCanvasMove}
        onMouseLeave={handleCanvasLeave}
      />

      {validationError && <p className="error-text">{validationError}</p>}

      <div className="controls">
        <button type="button" onClick={resetPoints} className="secondary">
          Reset points
        </button>
        <button className="primary" type="button" onClick={confirmPoints} disabled={points.length !== 4}>
          Start analysis
        </button>
      </div>
    </section>
  );
}
