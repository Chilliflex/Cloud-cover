import { memo } from "react";
import type { Palette } from "./weatherMapTypes";
import { LEGENDS } from "./weatherMapConfig";

interface WeatherMapLegendProps {
  currentLegend: (typeof LEGENDS)[keyof typeof LEGENDS];
  currentGradient: string;
  palette: Palette;
  showLegend: boolean;
  setShowLegend: (value: boolean) => void;
  showAlertLegend: boolean;
  setShowAlertLegend: (value: boolean) => void;
  isMobile: boolean;
}

function WeatherMapLegend({
  currentLegend,
  currentGradient,
  palette,
  showLegend,
  setShowLegend,
  showAlertLegend,
  setShowAlertLegend,
  isMobile,
}: WeatherMapLegendProps) {
  // Safe-area-aware anchors so panels clear the iPhone home indicator / notch.
  const bottomInset = "calc(env(safe-area-inset-bottom, 0px) + 22px)";
  const leftInset = "calc(env(safe-area-inset-left, 0px) + 22px)";
  const rightInset = "calc(env(safe-area-inset-right, 0px) + 22px)";
  const minValue = Number(currentLegend.min);
  const maxValue = Number(currentLegend.max);
  const ticks =
    Number.isFinite(minValue) && Number.isFinite(maxValue)
      ? Array.from({ length: 6 }, (_, i) =>
          Math.round(minValue + ((maxValue - minValue) * i) / 5)
        )
      : [180, 210, 240, 270, 300, 320];

  return (
    <>
      {!showAlertLegend && (
        <button
          onClick={() => setShowAlertLegend(true)}
          style={{
            position: "absolute",
            bottom: bottomInset,
            left: leftInset,
            zIndex: 9999,
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

      {showAlertLegend && (
        <div
          style={{
            position: "absolute",
            bottom: bottomInset,
            left: leftInset,
            zIndex: 9999,
            background: "linear-gradient(180deg,rgba(15,23,42,0.78),rgba(15,23,42,0.58))",
            backdropFilter: "blur(16px)",
            border: "1px solid rgba(255,255,255,0.12)",
            borderRadius: "18px",
            padding: isMobile ? "10px" : "12px",
            color: "white",
            minWidth: isMobile ? "0" : "190px",
            maxWidth: "min(46vw, 220px)",
            boxShadow: "0 10px 25px rgba(0,0,0,0.45)",
            fontFamily: "var(--font-inter), sans-serif",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "10px",
            }}
          >
            <div style={{ fontSize: "14px", fontWeight: 700 }}>Weather Alerts</div>
            <button
              onClick={() => setShowAlertLegend(false)}
              style={{
                width: "30px",
                height: "30px",
                borderRadius: "10px",
                border: "1px solid rgba(255,255,255,0.08)",
                background: "rgba(255,255,255,0.08)",
                color: "white",
                fontSize: "18px",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              ❮
            </button>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "9px", marginBottom: "9px" }}>
            <span style={{ fontSize: "16px", width: "18px", textAlign: "center" }}>🌧️</span>
            <div>
              <div style={{ fontSize: "12px", fontWeight: 600 }}>Current Heavy Rain</div>
              <div style={{ fontSize: "10px", color: "#94a3b8" }}>Live rainfall observed now</div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "9px", marginBottom: "9px" }}>
            <span style={{ fontSize: "16px", width: "18px", textAlign: "center" }}>☔</span>
            <div>
              <div style={{ fontSize: "12px", fontWeight: 600 }}>Nowcast Rain + Radius</div>
              <div style={{ fontSize: "10px", color: "#94a3b8" }}>Expected within 6 hours</div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "9px", marginBottom: "9px" }}>
            <span style={{ fontSize: "16px", width: "18px", textAlign: "center" }}>⛈️</span>
            <div>
              <div style={{ fontSize: "12px", fontWeight: 600 }}>Cloudburst</div>
              <div style={{ fontSize: "10px", color: "#94a3b8" }}>Intense localized downpour</div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "9px" }}>
            <span style={{ fontSize: "16px", width: "18px", textAlign: "center", color: "#facc15" }}>⚡</span>
            <div>
              <div style={{ fontSize: "12px", fontWeight: 600 }}>Thunderstorm</div>
              <div style={{ fontSize: "10px", color: "#94a3b8" }}>Deep convective cloud cell</div>
            </div>
          </div>
        </div>
      )}

      {!showLegend && (
        <button
          onClick={() => setShowLegend(true)}
          style={{
            position: "absolute",
            bottom: bottomInset,
            right: rightInset,
            zIndex: 9999,
            width: "42px",
            height: "42px",
            borderRadius: "14px",
            border: "1px solid rgba(255,255,255,0.08)",
            background: "rgba(15,23,42,0.82)",
            backdropFilter: "blur(12px)",
            color: "white",
            fontSize: "22px",
            cursor: "pointer",
          }}
        >
          ❮
        </button>
      )}

      {showLegend && (
        <div
          style={{
            position: "absolute",
            bottom: bottomInset,
            right: rightInset,
            zIndex: 9999,
            width: isMobile ? "min(66vw, 260px)" : "320px",
            maxWidth: "calc(100vw - 32px)",
            background: "linear-gradient(180deg,rgba(15,23,42,0.78),rgba(15,23,42,0.58))",
            backdropFilter: "blur(16px)",
            border: "1px solid rgba(255,255,255,0.12)",
            borderRadius: isMobile ? "18px" : "24px",
            padding: isMobile ? "12px" : "14px",
            boxShadow: "0 12px 35px rgba(0,0,0,0.5)",
            color: "white",
          }}
        >
          <div style={{ fontSize: "15px", fontWeight: 700, letterSpacing: "0.3px", fontFamily: "var(--font-inter), sans-serif", marginBottom: "12px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
              <div style={{ fontSize: "15px", fontWeight: 700 }}>
                {currentLegend.title}
                <div
                  style={{
                    width: "60px",
                    height: "3px",
                    borderRadius: "999px",
                    background: "linear-gradient(90deg, #2563eb,#38bdf8)",
                    marginTop: "6px",
                    marginBottom: "10px",
                  }}
                />
              </div>
              <button
                onClick={() => setShowLegend(false)}
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
                ✕
              </button>
            </div>
          </div>

          <div style={{ height: "18px", borderRadius: "12px", background: currentGradient, boxShadow: "inset 0 0 10px rgba(255,255,255,0.25)" }} />

          <div style={{ display: "flex", justifyContent: "space-between", marginTop: "8px" }}>
            {ticks.map((_, i) => (
              <div key={i} style={{ width: "2px", height: "10px", background: "rgba(255,255,255,0.8)" }} />
            ))}
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", marginTop: "6px", fontSize: "11px", fontWeight: 700 }}>
            {ticks.map((value, i) => (
              <span key={i}>{value}</span>
            ))}
          </div>

          <div style={{ marginTop: "10px", fontSize: "10px", color: "#cbd5e1", display: "flex", justifyContent: "space-between" }}>
            <span>Severe Thunderstorms</span>
            <span>Clear Sky / Surface</span>
          </div>

          <div style={{ marginTop: "8px", fontSize: "11px", color: "#94a3b8" }}>Palette: {palette}</div>
        </div>
      )}
    </>
  );
}

export default memo(WeatherMapLegend);
