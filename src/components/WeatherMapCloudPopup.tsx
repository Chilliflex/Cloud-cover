import type { ComponentType } from "react";
import type { CloudPopup } from "./weatherMapTypes";
import { ccToColor, getCloudLabel, getCloudRainRisk, getSkyIcon } from "./weatherMapHelpers";

interface WeatherMapCloudPopupProps {
  cloudPopup: CloudPopup;
  setCloudPopup: (value: null) => void;
  Popup: ComponentType<any>;
}

export default function WeatherMapCloudPopup({ cloudPopup, setCloudPopup, Popup }: WeatherMapCloudPopupProps) {
  return (
    <Popup
      position={[cloudPopup.lat, cloudPopup.lon]}
      autoPan={true}
      closeButton={false}
      className="cloud-info-popup"
    >
      <div
        style={{
          width: "160px",
          background: "rgba(10,16,30,0.97)",
          color: "white",
          padding: "8px",
          borderRadius: "14px",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          border: "1px solid rgba(255,255,255,0.09)",
          boxShadow: "0 14px 42px rgba(0,0,0,0.65)",
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
          <span
            style={{
              fontSize: "11px",
              fontWeight: 700,
              letterSpacing: "1px",
              color: "#64748b",
              textTransform: "uppercase",
            }}
          >
            ☁  Cloud Cover
          </span>
          <button
            onClick={(e) => {
              e.stopPropagation();
              setCloudPopup(null);
            }}
            style={{
              background: "rgba(255,255,255,0.06)",
              border: "none",
              color: "#94a3b8",
              width: "20px",
              height: "20px",
              borderRadius: "6px",
              cursor: "pointer",
              fontSize: "14px",
              lineHeight: "20px",
              textAlign: "center",
            }}
          >
            ✕
          </button>
        </div>

        <div style={{ display: "flex", alignItems: "flex-end", gap: "3px", marginBottom: "8px" }}>
          <span
            style={{
              fontSize: "32px",
              fontWeight: 800,
              lineHeight: 1,
              color: ccToColor(cloudPopup.cloudCover),
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {cloudPopup.cloudCover}
          </span>
          <span style={{ fontSize: "18px", fontWeight: 700, color: "#475569", paddingBottom: "6px" }}>%</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "7px", marginBottom: "8px" }}>
          <span style={{ fontSize: "18px" }}>{getSkyIcon(cloudPopup.cloudCover)}</span>
          <span style={{ fontSize: "13px", fontWeight: 600, color: "#e2e8f0" }}>{getCloudLabel(cloudPopup.cloudCover)}</span>
        </div>

        {(() => {
          const risk = getCloudRainRisk(cloudPopup.temp, cloudPopup.cloudCover);
          return risk ? (
            <div
              style={{
                fontSize: "12px",
                fontWeight: 600,
                color: risk.color,
                padding: "5px 9px",
                borderRadius: "8px",
                background: `${risk.color}1a`,
                border: `1px solid ${risk.color}35`,
                marginBottom: "10px",
              }}
            >
              {risk.label}
            </div>
          ) : null;
        })()}

        <div style={{ fontSize: "10px", color: "#475569", display: "flex", justifyContent: "space-between" }}>
          {cloudPopup.temp > 100 && (
            <span>
              BT {cloudPopup.temp} K ({(cloudPopup.temp - 273.15).toFixed(1)}°C)
            </span>
          )}
          <span>
            {cloudPopup.lat.toFixed(2)}°N {cloudPopup.lon.toFixed(2)}°E
          </span>
        </div>
      </div>
    </Popup>
  );
}
