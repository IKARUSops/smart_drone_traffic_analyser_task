"use client";

import { useEffect, useRef, useState } from "react";

type SceneMode = "auto" | "top_down" | "angled";

type Props = {
  imageUrl: string;
  onConfirm: (payload: {
    line_points: number[][];
    image_width: number;
    image_height: number;
    scene_mode: SceneMode;
  }) => void;
};

export default function LinePicker({ imageUrl, onConfirm }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [points, setPoints] = useState<number[][]>([]);
  const [sceneMode, setSceneMode] = useState<SceneMode>("auto");

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

    if (points.length === 2) {
      ctx.strokeStyle = "#12ff8a";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(points[0][0], points[0][1]);
      ctx.lineTo(points[1][0], points[1][1]);
      ctx.stroke();
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
  }, [points]);

  const handleCanvasClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (points.length >= 2) {
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
  };

  const resetPoints = () => {
    setPoints([]);
  };

  const confirmPoints = () => {
    const canvas = canvasRef.current;
    if (!canvas || points.length !== 2) {
      return;
    }

    onConfirm({
      line_points: points,
      image_width: canvas.width,
      image_height: canvas.height,
      scene_mode: sceneMode,
    });
  };

  return (
    <section className="line-picker">
      <h2>Select exactly two points on frame 20 to define the counting line</h2>
      <p>
        Click once to place P1 and again to place P2. Your points are saved in OpenCV pixel coordinates.
      </p>

      <label className="mode-row">
        Scene mode:
        <select value={sceneMode} onChange={(event) => setSceneMode(event.target.value as SceneMode)}>
          <option value="auto">Auto</option>
          <option value="top_down">Top-down drone</option>
          <option value="angled">Angled road</option>
        </select>
      </label>

      <canvas ref={canvasRef} className="line-canvas" onClick={handleCanvasClick} />

      <div className="controls">
        <button type="button" onClick={resetPoints} className="secondary">
          Reset points
        </button>
        <button type="button" onClick={confirmPoints} disabled={points.length !== 2}>
          Confirm line and start processing
        </button>
      </div>
    </section>
  );
}
