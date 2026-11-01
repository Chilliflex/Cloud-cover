import { buildMosdacUrl, snapToSlotDate } from "../../../lib/mosdac";

const MOSDAC_HEADERS = {
  Referer: "https://www.mosdac.gov.in/live/index_one.php?url_name=india",
  Origin: "https://www.mosdac.gov.in",
};

// How many 30-min slots back to probe before giving up.
const MAX_CANDIDATES = 6;
const SLOT_MS = 30 * 60 * 1000;

// A tiny GetMap over India — enough to tell "frame exists" (200/png, ~KBs)
// from "not ready yet" (404, tiny xml error).
function buildProbeUrl(datetimeIso: string, layers: string, styles: string) {
  const params = new URLSearchParams();
  params.set("datetime", datetimeIso);
  params.set("layers", layers);
  params.set("styles", styles);
  params.set("crs", "EPSG:4326");
  params.set("bbox", "5,65,38,98");
  params.set("width", "48");
  params.set("height", "48");
  return buildMosdacUrl(params);
}

async function frameExists(datetimeIso: string, layers: string, styles: string) {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 6000);
    const res = await fetch(buildProbeUrl(datetimeIso, layers, styles), {
      headers: MOSDAC_HEADERS,
      signal: controller.signal,
    });
    clearTimeout(timeout);

    const contentType = res.headers.get("content-type") || "";
    return res.ok && contentType.includes("image");
  } catch {
    return false;
  }
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const layers = searchParams.get("layers") || "IMG_TIR1";
  const styles = searchParams.get("styles") || "boxfill/greyscale";

  const newestSlot = snapToSlotDate(new Date());

  for (let i = 0; i < MAX_CANDIDATES; i++) {
    const candidate = new Date(newestSlot.getTime() - i * SLOT_MS);
    const iso = candidate.toISOString();

    if (await frameExists(iso, layers, styles)) {
      return Response.json(
        { datetime: iso, probedBack: i },
        { headers: { "Cache-Control": "public, max-age=120" } }
      );
    }
  }

  // Nothing responded — fall back to a safely-old slot so the UI still shows something.
  const fallback = new Date(newestSlot.getTime() - 2 * SLOT_MS).toISOString();
  return Response.json(
    { datetime: fallback, probedBack: -1 },
    { headers: { "Cache-Control": "public, max-age=60" } }
  );
}
