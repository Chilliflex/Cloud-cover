// Shared request headers so MOSDAC accepts our proxied requests. Reused by
// every /api/mosdac-* route instead of being copy-pasted in each one.
export const MOSDAC_HEADERS = {
  Referer: "https://www.mosdac.gov.in/live/index_one.php?url_name=india",
  Origin: "https://www.mosdac.gov.in",
};

const MONTHS = [
  "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
  "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
];

function generateMosdacPath(utcDatetime: string) {
  const date = new Date(utcDatetime);

  // INSAT-3R live frames publish on half-hourly slots. Always resolve to the
  // most recent valid slot (:15 or :45).
  let minutes = date.getUTCMinutes();

  if (minutes >= 15 && minutes <= 44) {
    minutes = 15;
  } else {
    // 45 → 59 and 00 → 14 both map to the :45 slot. For 00 → 14 that slot
    // belongs to the previous hour, so step the hour back.
    minutes = 45;
    if (date.getUTCMinutes() <= 14) {
      date.setUTCHours(date.getUTCHours() - 1);
    }
  }

  date.setUTCMinutes(minutes);
  date.setUTCSeconds(0);
  date.setUTCMilliseconds(0);

  const year = date.getUTCFullYear();
  const month = MONTHS[date.getUTCMonth()];
  const day = String(date.getUTCDate()).padStart(2, "0");
  const hours = String(date.getUTCHours()).padStart(2, "0");
  const mins = String(minutes).padStart(2, "0");

  const folder = `${day}${month}`;
  const filename = `3RIMG_${day}${month}${year}_${hours}${mins}_L1B_STD_V01R00.h5`;

  return `https://www.mosdac.gov.in/live_data/wms/live3RL1BSTD4km/products/Insat3r/3R_IMG/${year}/${folder}/${filename}`;
}

export function buildMosdacUrl(params: URLSearchParams) {
  const datetime = params.get("datetime");

  // Fall back to the current live slot when datetime is missing or unparseable,
  // instead of a fixed past date, so the proxy self-heals.
  const parsed = new Date(datetime ?? "");
  const utcDatetime =
    datetime && !Number.isNaN(parsed.getTime())
      ? datetime
      : snapToSlotDate(new Date()).toISOString();

  const url = new URL(generateMosdacPath(utcDatetime));

  // Copy incoming params through (uppercased, WMS-style), skipping our own.
  params.forEach((value, key) => {
    if (key !== "_t" && key !== "datetime") {
      url.searchParams.set(key.toUpperCase(), value);
    }
  });

  // Required WMS params.
  url.searchParams.set("SERVICE", "WMS");
  url.searchParams.set("REQUEST", "GetMap");
  url.searchParams.set("VERSION", "1.3.0");
  url.searchParams.set("FORMAT", "image/png");
  url.searchParams.set("TRANSPARENT", "true");

  // Stable working scaling for the INSAT-3R greyscale/boxfill palettes.
  url.searchParams.set("COLORSCALERANGE", "462,946");
  url.searchParams.set("BELOWMINCOLOR", "extend");
  url.searchParams.set("ABOVEMAXCOLOR", "extend");

  url.searchParams.set("STYLES", params.get("styles") || "boxfill/greyscale");

  return url.toString();
}

export function getFallbackDatetime(utcDatetime: string) {
  const date = new Date(utcDatetime);
  date.setUTCMinutes(date.getUTCMinutes() - 30);
  return date.toISOString();
}

// Snap a time to MOSDAC's live half-hourly slot (:15 / :45).
// Mirrors the grouping used by generateMosdacPath above.
export function snapToSlotDate(input: Date): Date {
  const date = new Date(input.getTime());
  const minutes = date.getUTCMinutes();

  if (minutes >= 15 && minutes <= 44) {
    date.setUTCMinutes(15, 0, 0);
  } else {
    if (minutes <= 14) {
      date.setUTCHours(date.getUTCHours() - 1);
    }
    date.setUTCMinutes(45, 0, 0);
  }

  return date;
}
