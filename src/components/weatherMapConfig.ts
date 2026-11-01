import type { Palette, WeatherChannel, WeatherMode } from "./weatherMapTypes";

export const CHANNELS = [
  {
    label: "TIR1",
    layer: "IMG_TIR1",
  },
  {
    label: "TIR2",
    layer: "IMG_TIR2",
  },
  {
    label: "MIR",
    layer: "IMG_MIR",
  },
] as const;

export const PALETTES = ["greyscale", "rainbow", "redblue", "ferret"] as const;

export const MODES: WeatherMode[] = ["LIVE", "HISTORY", "ANIMATION"];

export const LEGENDS: Record<WeatherChannel, { title: string; min: string; max: string }> = {
  IMG_TIR1: {
    title: "Cloud Top Temperature (K)",
    min: "180",
    max: "320",
  },
  IMG_TIR2: {
    title: "Thermal Infrared Temperature (K)",
    min: "180",
    max: "320",
  },
  IMG_MIR: {
    title: "Mid Infrared Brightness",
    min: "180",
    max: "340",
  },
};

export const PALETTE_GRADIENTS: Record<Palette, string> = {
  greyscale:
    "linear-gradient(to right,#ffffff,#d9d9d9,#a6a6a6,#737373,#404040,#000000)",
  rainbow:
    "linear-gradient(to left,#0000ff,#00ffff,#00ff00,#ffff00,#ff8000,#ff0000)",
  redblue:
    "linear-gradient(to right,#ff0000,#ff8080,#ffffff,#80bfff,#0066ff)",
  ferret:
    "linear-gradient(to left,#c94cff,#8b5cf6,#3b82f6,#22d3ee,#22c55e,#ffff00,#ff9800,#ff0000)",
};

export const GRID_DEG = 12 / 111;
