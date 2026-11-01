export type GeoJsonObject = unknown;

export type MosdacAlertFeatureProperties = {
  name?: string;
  value?: string;
  rad_inf?: string;
  event_date?: string;
  forecast_date?: string;
  event_time?: string;
  forecast_time?: string;
  forecast?: string;
  [key: string]: unknown;
};

export type MosdacAlertFeature = {
  geometry?: { coordinates?: [number, number] };
  properties?: MosdacAlertFeatureProperties;
  [key: string]: unknown;
};

export type CloudPoint = {
  gridLat: number;
  gridLon: number;
  cloudCover: number;
  temp: number;
  [key: string]: unknown;
};

export type ThunderstormCell = {
  lat: number;
  lon: number;
  temp: number;
  count: number;
  severity: string;
  [key: string]: unknown;
};

export type CloudPopup = {
  lat: number;
  lon: number;
  cloudCover: number;
  temp: number;
};

export type WeatherChannel = "IMG_TIR1" | "IMG_TIR2" | "IMG_MIR";

export type Palette = "greyscale" | "rainbow" | "redblue" | "ferret";

export type WeatherMode = "LIVE" | "HISTORY" | "ANIMATION";
