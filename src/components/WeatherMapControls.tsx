import { memo } from "react";
import type { Palette, WeatherChannel, WeatherMode } from "./weatherMapTypes";
import { CHANNELS, MODES, PALETTES } from "./weatherMapConfig";

interface WeatherMapControlsProps {
  channel: WeatherChannel;
  setChannel: (value: WeatherChannel) => void;
  palette: Palette;
  setPalette: (value: Palette) => void;
  showOverlay: boolean;
  setShowOverlay: (value: boolean) => void;
  showAlerts: boolean;
  setShowAlerts: (value: boolean) => void;
  showThunderstorms: boolean;
  setShowThunderstorms: (value: boolean) => void;
  opacity: number;
  setOpacity: (value: number) => void;
  mode: WeatherMode;
  setMode: (value: WeatherMode) => void;
  date: string;
  setDate: (value: string) => void;
  time: string;
  setTime: (value: string) => void;
  isPlaying: boolean;
  setIsPlaying: (value: boolean) => void;
  speed: number;
  setSpeed: (value: number) => void;
  currentFrame: number;
  setCurrentFrame: (value: number) => void;
  setDisplayFrame: (value: number) => void;
  lastFrameIndex: number;
  animationLabel: string;
  isMobile: boolean;
  showControls: boolean;
  setShowControls: (value: boolean) => void;
}

function WeatherMapControls({
  channel,
  setChannel,
  palette,
  setPalette,
  showOverlay,
  setShowOverlay,
  showAlerts,
  setShowAlerts,
  showThunderstorms,
  setShowThunderstorms,
  opacity,
  setOpacity,
  mode,
  setMode,
  date,
  setDate,
  time,
  setTime,
  isPlaying,
  setIsPlaying,
  speed,
  setSpeed,
  currentFrame,
  setCurrentFrame,
  setDisplayFrame,
  lastFrameIndex,
  animationLabel,
  isMobile,
  showControls,
  setShowControls,
}: WeatherMapControlsProps) {
  const changeMode = (item: WeatherMode) => {
    setMode(item);

    if (item === "LIVE") {
      setDate("");
      setTime("");
      setIsPlaying(false);
      setCurrentFrame(lastFrameIndex);
      setDisplayFrame(lastFrameIndex);
    }

    if (item === "ANIMATION") {
      setDate("");
      setTime("");
    }
  };

  return (
    <>
      {!showControls && (
        <button
          onClick={() => setShowControls(true)}
          style={{
            position: "absolute",
            top: "calc(env(safe-area-inset-top, 0px) + 16px)",
            left: "calc(env(safe-area-inset-left, 0px) + 16px)",
            zIndex: 5000,
            width: "42px",
            height: "42px",
            borderRadius: "14px",
            border: "1px solid rgba(255,255,255,0.08)",
            background: "rgba(15,23,42,0.82)",
            backdropFilter: "blur(12px)",
            color: "white",
            fontSize: "22px",
            cursor: "pointer",
            boxShadow: "0 8px 20px rgba(0,0,0,0.4)",
          }}
        >
          ❯
        </button>
      )}

      {showControls && (
        <div
          className="glass-scroll"
          style={{
            position: "absolute",
            top: "calc(env(safe-area-inset-top, 0px) + 16px)",
            left: "calc(env(safe-area-inset-left, 0px) + 16px)",
            animation: isMobile ? "none" : "glassFloat 6s ease-in-out infinite",
            zIndex: 2000,
            maxHeight: "calc(100dvh - env(safe-area-inset-top, 0px) - env(safe-area-inset-bottom, 0px) - 32px)",
            overflowY: "auto",
            width: isMobile ? "min(88vw, 340px)" : "340px",
            padding: isMobile ? "16px" : "18px",
            borderRadius: isMobile ? "22px" : "28px",
            background: "linear-gradient( 180deg, rgba(15,23,42,0.82), rgba(15,23,42,0.62) )",
            backdropFilter: "blur(20px)",
            WebkitBackdropFilter: "blur(14px)",
            border: "1px solid rgba(255,255,255,0.12)",
            boxShadow: "0 10px 35px rgba(0,0,0,0.45)",
            color: "white",
            fontFamily: "var(--font-inter), sans-serif",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "18px",
            }}
          >
            <h2
              style={{
                margin: 0,
                fontSize: isMobile ? "28px" : "38px",
                fontWeight: 800,
                letterSpacing: "-1px",
                color: "white",
              }}
            >
              INSAT-3DR
            </h2>

            <button
              onClick={() => setShowControls(false)}
              style={{
                width: "38px",
                height: "38px",
                borderRadius: "12px",
                border: "1px solid rgba(255,255,255,0.08)",
                background: "rgba(255,255,255,0.08)",
                color: "white",
                fontSize: "22px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              ❮
            </button>
          </div>

          <div style={{ display: "flex", gap: "6px", marginBottom: "14px" }}>
            {MODES.map((item) => (
              <button
                key={item}
                onClick={() => changeMode(item)}
                style={{
                  flex: 1,
                  padding: "10px",
                  border: "none",
                  borderRadius: "12px",
                  cursor: "pointer",
                  background:
                    mode === item
                      ? "linear-gradient(135deg,#2563eb,#38bdf8)"
                      : "rgba(255,255,255,0.08)",
                  color: "white",
                  fontWeight: 700,
                  fontSize: "14px",
                  transition: "all 0.25s ease",
                  boxShadow:
                    mode === item ? "0 4px 15px rgba(37,99,235,0.45)" : "none",
                }}
              >
                {item}
              </button>
            ))}
          </div>

          <label>
            <b>Channel</b>
          </label>

          <select
            value={channel}
            onChange={(e) => setChannel(e.target.value as WeatherChannel)}
            style={{
              WebkitAppearance: "none",
              MozAppearance: "none",
              appearance: "none",
              width: "100%",
              marginTop: "6px",
              marginBottom: "14px",
              padding: "10px",
              borderRadius: "10px",
              border: "1px solid rgba(255,255,255,0.1)",
              background: "rgba(255,255,255,0.08)",
              color: "white",
              fontSize: "14px",
              outline: "none",
            }}
          >
            {CHANNELS.map((item) => (
              <option
                key={item.layer}
                value={item.layer}
                style={{ background: "#111827", color: "white" }}
              >
                {item.label}
              </option>
            ))}
          </select>

          <label>
            <b>Palette</b>
          </label>

          <select
            value={palette}
            onChange={(e) => setPalette(e.target.value as Palette)}
            style={{
              width: "100%",
              marginTop: "6px",
              marginBottom: "14px",
              padding: "10px",
              borderRadius: "10px",
              border: "1px solid rgba(255,255,255,0.1)",
              background: "rgba(255,255,255,0.08)",
              color: "white",
              fontSize: "14px",
              outline: "none",
            }}
          >
            {PALETTES.map((item) => (
              <option
                key={item}
                value={item}
                style={{ background: "#111827", color: "white" }}
              >
                {item}
              </option>
            ))}
          </select>

          <label
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              marginBottom: "10px",
            }}
          >
            <input
              type="checkbox"
              checked={showOverlay}
              onChange={() => setShowOverlay(!showOverlay)}
            />
            <b>Show Overlay</b>
          </label>

          <div style={{ marginTop: "18px", display: "flex", flexDirection: "column", gap: "14px" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "10px", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={showAlerts}
                onChange={() => setShowAlerts(!showAlerts)}
              />
              <b>Show Heavy Rain & Cloudburst</b>
            </label>

            <label style={{ display: "flex", alignItems: "center", gap: "10px", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={showThunderstorms}
                onChange={() => setShowThunderstorms(!showThunderstorms)}
              />
              <b>Show Thunderstorms</b>
            </label>
          </div>

          <label>
            <b>Opacity:</b> {opacity}
          </label>

          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            value={opacity}
            onChange={(e) => setOpacity(Number(e.target.value))}
            style={{
              width: "100%",
              marginTop: "6px",
              marginBottom: "14px",
              padding: "10px",
              borderRadius: "10px",
              border: "1px solid rgba(255,255,255,0.1)",
              background: "rgba(255,255,255,0.08)",
              color: "white",
              fontSize: "14px",
              outline: "none",
            }}
          />

          {mode === "ANIMATION" && (
            <>
              <hr />

              <h3>Animation</h3>

              <button
                onClick={() => setIsPlaying(!isPlaying)}
                style={{ padding: "8px 14px", cursor: "pointer", marginBottom: "10px" }}
              >
                {isPlaying ? "Pause" : "Play"}
              </button>

              <label>
                <b>Speed</b>
              </label>

              <input
                type="range"
                min="3500"
                max="5000"
                step="100"
                value={speed}
                onChange={(e) => setSpeed(Number(e.target.value))}
                style={{ width: "100%" }}
              />

              <p>{speed} ms</p>

              <p style={{ fontWeight: "bold", marginTop: "10px" }}>Current Frame:</p>
              <p>{animationLabel}</p>

              <input
                type="range"
                min="0"
                max={lastFrameIndex}
                step="1"
                value={currentFrame}
                onChange={(e) => {
                  const frame = Number(e.target.value);
                  setCurrentFrame(frame);
                  setDisplayFrame(frame);
                }}
                style={{ width: "100%", marginBottom: "10px" }}
              />
            </>
          )}

          {mode === "HISTORY" && (
            <>
              <hr />

              <h3>History Mode</h3>

              <label>
                <b>Date (IST)</b>
              </label>

              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                style={{ width: "100%", marginBottom: "10px" }}
              />

              <label>
                <b>Time (IST)</b>
              </label>

              <input
                type="time"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                style={{ width: "100%", marginBottom: "10px" }}
              />

              <hr />

              <p>
                <b>UTC:</b>
              </p>

              <p>{animationLabel}</p>
            </>
          )}
        </div>
      )}
    </>
  );
}

export default memo(WeatherMapControls);
