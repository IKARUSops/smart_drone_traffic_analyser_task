"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type Props = {
  src: string;
  downloadUrl: string;
  poster?: string;
  title?: string;
};

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) {
    return "0:00";
  }

  const totalSeconds = Math.floor(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const remainingSeconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
  }

  return `${minutes}:${String(remainingSeconds).padStart(2, "0")}`;
}

export default function MediaPlayer({ src, downloadUrl, poster, title = "Processed video" }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const [isReady, setIsReady] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [volume, setVolume] = useState(1);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isBuffering, setIsBuffering] = useState(false);
  const [error, setError] = useState("");

  const progressPercent = useMemo(() => {
    if (!duration) {
      return 0;
    }
    return Math.min(100, (currentTime / duration) * 100);
  }, [currentTime, duration]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) {
      return;
    }

    const handleLoadedMetadata = () => {
      setDuration(video.duration || 0);
      setCurrentTime(video.currentTime || 0);
      setIsReady(true);
      setError("");
    };

    const handleTimeUpdate = () => setCurrentTime(video.currentTime || 0);
    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleWaiting = () => setIsBuffering(true);
    const handlePlaying = () => setIsBuffering(false);
    const handleCanPlay = () => setIsReady(true);
    const handleVolumeChange = () => {
      setIsMuted(video.muted);
      setVolume(video.volume);
    };
    const handleEnded = () => setIsPlaying(false);
    const handleError = () => {
      const mediaError = video.error;
      setIsBuffering(false);
      setError(mediaError ? `Playback error (${mediaError.code})` : "Playback failed");
    };

    video.addEventListener("loadedmetadata", handleLoadedMetadata);
    video.addEventListener("timeupdate", handleTimeUpdate);
    video.addEventListener("play", handlePlay);
    video.addEventListener("pause", handlePause);
    video.addEventListener("waiting", handleWaiting);
    video.addEventListener("stalled", handleWaiting);
    video.addEventListener("playing", handlePlaying);
    video.addEventListener("canplay", handleCanPlay);
    video.addEventListener("volumechange", handleVolumeChange);
    video.addEventListener("ended", handleEnded);
    video.addEventListener("error", handleError);

    handleVolumeChange();

    return () => {
      video.removeEventListener("loadedmetadata", handleLoadedMetadata);
      video.removeEventListener("timeupdate", handleTimeUpdate);
      video.removeEventListener("play", handlePlay);
      video.removeEventListener("pause", handlePause);
      video.removeEventListener("waiting", handleWaiting);
      video.removeEventListener("stalled", handleWaiting);
      video.removeEventListener("playing", handlePlaying);
      video.removeEventListener("canplay", handleCanPlay);
      video.removeEventListener("volumechange", handleVolumeChange);
      video.removeEventListener("ended", handleEnded);
      video.removeEventListener("error", handleError);
    };
  }, [src]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) {
      return;
    }
    video.playbackRate = playbackRate;
  }, [playbackRate]);

  const togglePlay = async () => {
    const video = videoRef.current;
    if (!video) {
      return;
    }

    if (video.paused) {
      try {
        await video.play();
      } catch {
        setError("Unable to start playback");
      }
      return;
    }

    video.pause();
  };

  const seekTo = (nextTime: number) => {
    const video = videoRef.current;
    if (!video || !Number.isFinite(duration)) {
      return;
    }

    video.currentTime = Math.max(0, Math.min(duration, nextTime));
    setCurrentTime(video.currentTime);
  };

  const toggleMute = () => {
    const video = videoRef.current;
    if (!video) {
      return;
    }
    video.muted = !video.muted;
  };

  const changeVolume = (nextVolume: number) => {
    const video = videoRef.current;
    if (!video) {
      return;
    }
    video.volume = nextVolume;
    video.muted = nextVolume === 0;
  };

  const toggleFullscreen = async () => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    if (document.fullscreenElement) {
      await document.exitFullscreen();
      return;
    }

    await container.requestFullscreen();
  };

  const openInNewTab = () => {
    window.open(src, "_blank", "noopener,noreferrer");
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === " " || event.key === "k" || event.key === "K") {
      event.preventDefault();
      void togglePlay();
    }
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      seekTo(currentTime - 10);
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      seekTo(currentTime + 10);
    }
    if (event.key === "m" || event.key === "M") {
      event.preventDefault();
      toggleMute();
    }
    if (event.key === "f" || event.key === "F") {
      event.preventDefault();
      void toggleFullscreen();
    }
  };

  return (
    <div className="player-shell" ref={containerRef} tabIndex={0} onKeyDown={handleKeyDown}>
      <div className="player-header">
        <div>
          <p className="player-kicker">Playback</p>
          <h3>{title}</h3>
        </div>
        <div className="player-actions">
          <button type="button" className="secondary" onClick={openInNewTab}>
            Open raw media
          </button>
          <a className="primary player-download" href={downloadUrl} target="_blank" rel="noreferrer">
            Download file
          </a>
        </div>
      </div>

      <div className="player-stage">
        <video
          ref={videoRef}
          className="player-video"
          src={src}
          poster={poster}
          preload="metadata"
          playsInline
        />

        {!isReady && !error && (
          <div className="player-overlay">
            <div>
              <p className="player-kicker">Loading</p>
              <h4>Preparing playback</h4>
              <p>Video metadata and buffer are being read.</p>
            </div>
          </div>
        )}

        {isBuffering && !error && <div className="player-badge">Buffering</div>}

        {error && (
          <div className="player-overlay error-overlay">
            <div>
              <p className="player-kicker">Playback error</p>
              <h4>{error}</h4>
              <p>The stream is not ready. Try opening the raw media or downloading the file.</p>
            </div>
            <div className="player-actions">
              <button type="button" className="primary" onClick={() => videoRef.current?.load()}>
                Retry stream
              </button>
              <button type="button" className="secondary" onClick={openInNewTab}>
                Open in new tab
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="player-controls">
        <div className="player-row">
          <button type="button" className="primary" onClick={togglePlay}>
            {isPlaying ? "Pause" : "Play"}
          </button>
          <button type="button" className="secondary" onClick={() => seekTo(currentTime - 10)}>
            -10s
          </button>
          <button type="button" className="secondary" onClick={() => seekTo(currentTime + 10)}>
            +10s
          </button>
          <button type="button" className="secondary" onClick={toggleMute}>
            {isMuted ? "Unmute" : "Mute"}
          </button>
          <button type="button" className="secondary" onClick={toggleFullscreen}>
            Fullscreen
          </button>
        </div>

        <input
          className="player-seek"
          type="range"
          min={0}
          max={duration || 0}
          step="0.1"
          value={Math.min(currentTime, duration || 0)}
          onChange={(event) => seekTo(Number(event.target.value))}
          aria-label="Seek"
        />

        <div className="player-meta">
          <span>
            {formatTime(currentTime)} / {formatTime(duration)}
          </span>
          <span>{Math.round(progressPercent)}% played</span>
          <label>
            Volume
            <input
              className="player-volume"
              type="range"
              min={0}
              max={1}
              step="0.01"
              value={isMuted ? 0 : volume}
              onChange={(event) => changeVolume(Number(event.target.value))}
              aria-label="Volume"
            />
          </label>
          <label>
            Speed
            <select value={playbackRate} onChange={(event) => setPlaybackRate(Number(event.target.value))}>
              <option value={0.5}>0.5x</option>
              <option value={1}>1x</option>
              <option value={1.25}>1.25x</option>
              <option value={1.5}>1.5x</option>
              <option value={2}>2x</option>
            </select>
          </label>
        </div>
      </div>
    </div>
  );
}
