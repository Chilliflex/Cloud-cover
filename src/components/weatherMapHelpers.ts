import type { ThunderstormCell } from "./weatherMapTypes";

export function createDivIcon(
  leaflet: typeof import("leaflet"),
  html: string,
  iconSize: [number, number],
  iconAnchor: [number, number]
) {
  return new leaflet.DivIcon({
    className: "weather-alert-icon",
    html,
    iconSize,
    iconAnchor,
  });
}

export function createThunderstormIcon(
  leaflet: typeof import("leaflet"),
  cell: ThunderstormCell,
  zoom: number
) {
  // Grow steadily as you zoom in so cells become more prominent.
  const size = Math.round(
    Math.max(14, Math.min(12 + (zoom - 3) * 4.5 + cell.count / 120, 58))
  );

  // Colder cloud tops = more severe convection.
  const glow =
    cell.temp < 190 ? "#ff3b3b" : cell.temp < 195 ? "#ff9500" : "#ffd21e";
  const boltSize = Math.round(size * 0.54);

  return new leaflet.DivIcon({
    className: "ts-icon",
    html: `
<div class="ts-cell" style="--ts-glow:${glow};width:${size}px;height:${size}px;">
  <span class="ts-glow"></span>
  <svg class="ts-bolt" width="${boltSize}" height="${boltSize}" viewBox="0 0 24 24" aria-hidden="true">
    <path d="M13 2 L5 13 h5 l-2 9 L19 10 h-6 z"
      fill="#fff3b0" stroke="rgba(0,0,0,0.45)" stroke-width="0.8"
      stroke-linejoin="round" />
  </svg>
</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

export function getSkyIcon(cc: number): string {
  if (cc < 10) return "☀️";
  if (cc < 30) return "🌤️";
  if (cc < 60) return "⛅";
  if (cc < 87) return "🌥️";
  return "☁️";
}

export function getCloudLabel(cc: number): string {
  if (cc < 10) return "Clear";
  if (cc < 30) return "Few Clouds";
  if (cc < 60) return "Partly Cloudy";
  if (cc < 87) return "Mostly Cloudy";
  return "Overcast";
}

export function ccToColor(cc: number): string {
  if (cc < 20) return "#fbbf24";
  if (cc < 50) return "#93c5fd";
  if (cc < 80) return "#e2e8f0";
  return "#94a3b8";
}

export function getCloudRainRisk(
  temp: number,
  cc: number
): { label: string; color: string } | null {
  if (temp > 100 && temp < 230)
    return { label: "⛈️  Convective Risk", color: "#ef4444" };
  if (temp > 100 && temp < 252)
    return { label: "🌧️  Heavy Rain Risk", color: "#f97316" };
  if (cc > 68 && (temp === 0 || temp < 272))
    return { label: "🌦️  Rain Possible", color: "#3b82f6" };
  return null;
}
