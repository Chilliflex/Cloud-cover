import { Fragment, memo } from "react";
import type { ComponentType } from "react";
import type {
  MosdacAlertFeature,
  MosdacAlertFeatureProperties,
  ThunderstormCell,
} from "./weatherMapTypes";
import { createThunderstormIcon } from "./weatherMapHelpers";

interface WeatherMapAlertLayerProps {
  visibleAlerts: MosdacAlertFeature[];
  zoom: number;
  showAlerts: boolean;
  showThunderstorms: boolean;
  mosdacAlertIcons: {
    blueRainIcon?: L.DivIcon;
    cloudburstIcon?: L.DivIcon;
    nowcastRainIcon?: L.DivIcon;
  };
  thunderstormCells: ThunderstormCell[];
  leaflet: typeof import("leaflet") | null;
  Marker: ComponentType<any>;
  Popup: ComponentType<any>;
  Circle: ComponentType<any>;
}

const popupCardStyle: React.CSSProperties = {
  minWidth: "190px",
  background: "rgba(15,23,42,0.9)",
  color: "white",
  padding: "13px",
  borderRadius: "16px",
  backdropFilter: "blur(12px)",
  border: "1px solid rgba(255,255,255,0.08)",
  fontFamily: "var(--font-inter), sans-serif",
  lineHeight: "1.55",
  boxShadow: "0 12px 32px rgba(0,0,0,0.45)",
};

function WeatherMapAlertLayer({
  visibleAlerts,
  zoom,
  showAlerts,
  showThunderstorms,
  mosdacAlertIcons,
  thunderstormCells,
  leaflet,
  Marker,
  Popup,
  Circle,
}: WeatherMapAlertLayerProps) {
  const visibleThunderstorms = thunderstormCells.filter(
    (cell) =>
      cell.severity === "Severe" ||
      cell.severity === "Strong" ||
      cell.severity === "Moderate"
  );

  return (
    <>
      {showAlerts &&
        visibleAlerts.map((feature, index) => {
          const coords = feature.geometry?.coordinates;
          if (!coords) return null;

          const [lng, lat] = coords;
          const props = (feature.properties || feature) as MosdacAlertFeatureProperties;
          const forecast = (props.forecast || "").toString().toLowerCase();
          const isCloudburst = forecast.includes("cloud");
          const isCurrentRain = !!props.value;
          const radiusKm = parseFloat(props.rad_inf || "0");

          const alertDate = props.forecast_date || props.event_date || "";
          const alertTime = props.forecast_time || props.event_time || "";

          const icon = isCloudburst
            ? mosdacAlertIcons.cloudburstIcon
            : isCurrentRain
            ? mosdacAlertIcons.blueRainIcon
            : mosdacAlertIcons.nowcastRainIcon;

          const title = isCloudburst
            ? "CLOUDBURST (NOWCAST)"
            : isCurrentRain
            ? "HEAVY RAIN (CURRENT)"
            : "HEAVY RAIN (NOWCAST)";
          const accent = isCloudburst ? "#f97316" : "#38bdf8";

          return (
            <Fragment key={`alert-${index}`}>
              {/* True radius-of-influence circle (rad_inf km) for nowcast alerts. */}
              {!isCurrentRain && radiusKm > 0 && (
                <Circle
                  center={[lat, lng]}
                  radius={radiusKm * 1000}
                  interactive={false}
                  pathOptions={{
                    color: isCloudburst ? "#fb923c" : "#facc15",
                    weight: 1.3,
                    opacity: 0.7,
                    fillColor: isCloudburst ? "#fb923c" : "#facc15",
                    fillOpacity: 0.05,
                  }}
                />
              )}

              <Marker position={[lat, lng]} icon={icon}>
                <Popup closeButton autoPan={false}>
                  <div style={popupCardStyle}>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        fontWeight: 800,
                        fontSize: "13px",
                        letterSpacing: "0.4px",
                        marginBottom: "10px",
                      }}
                    >
                      <span
                        style={{
                          width: "8px",
                          height: "8px",
                          borderRadius: "50%",
                          background: accent,
                          boxShadow: `0 0 8px ${accent}`,
                        }}
                      />
                      {title}
                    </div>

                    <div style={{ fontSize: "12px", color: "#cbd5e1" }}>
                      <b style={{ color: "#fff" }}>Location</b>
                      <br />
                      {lat.toFixed(2)}°N, {lng.toFixed(2)}°E
                    </div>

                    {isCurrentRain ? (
                      <div style={{ marginTop: "8px", fontSize: "12px", color: "#cbd5e1" }}>
                        <b style={{ color: "#fff" }}>Rainfall</b>
                        <br />
                        {parseFloat(props.value as string).toFixed(1)} mm
                      </div>
                    ) : (
                      <>
                        {(alertDate || alertTime) && (
                          <div style={{ marginTop: "8px", fontSize: "12px", color: "#cbd5e1" }}>
                            <b style={{ color: "#fff" }}>Forecast issued</b>
                            <br />
                            {alertDate} {alertTime}
                          </div>
                        )}
                        <div style={{ marginTop: "8px", fontSize: "12px", color: "#cbd5e1" }}>
                          <b style={{ color: "#fff" }}>Validity</b>
                          <br />
                          Next 6 hours
                        </div>
                        {radiusKm > 0 && (
                          <div style={{ marginTop: "8px", fontSize: "12px", color: "#cbd5e1" }}>
                            <b style={{ color: "#fff" }}>Radius of influence</b>
                            <br />
                            {radiusKm.toFixed(1)} km
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </Popup>
              </Marker>
            </Fragment>
          );
        })}

      {showThunderstorms &&
        visibleThunderstorms.map((cell, index) => (
          <Marker
            key={`storm-${index}`}
            position={[cell.lat, cell.lon]}
            icon={leaflet ? createThunderstormIcon(leaflet, cell, zoom) : undefined}
          >
            <Popup>
              <div style={popupCardStyle}>
                <div
                  style={{
                    fontWeight: 800,
                    fontSize: "13px",
                    letterSpacing: "0.4px",
                    marginBottom: "8px",
                  }}
                >
                  ⚡ THUNDERSTORM CELL
                </div>
                <div style={{ fontSize: "12px", color: "#cbd5e1" }}>
                  Severity:{" "}
                  {cell.temp < 190
                    ? "🔴 Severe"
                    : cell.temp < 195
                    ? "🟠 Strong"
                    : "🟡 Moderate"}
                  <br />
                  Cloud-top temp: {cell.temp.toFixed(1)} K
                  <br />
                  Impact radius: {Math.round(Math.sqrt(cell.count) * 2)} km
                  <br />
                  Cell strength: {cell.count}
                </div>
              </div>
            </Popup>
          </Marker>
        ))}
    </>
  );
}

export default memo(WeatherMapAlertLayer);
