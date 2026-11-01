import {
  buildMosdacUrl,
  getFallbackDatetime,
  MOSDAC_HEADERS,
} from "../../../lib/mosdac";

const DEBUG = process.env.NODE_ENV !== "production";

// 1x1 transparent PNG, returned when MOSDAC has no tile for the requested slot.
const EMPTY_TILE = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==",
  "base64"
);

function pngResponse(body: ArrayBuffer | Buffer, cacheControl?: string) {
  const headers: Record<string, string> = { "Content-Type": "image/png" };
  if (cacheControl) headers["Cache-Control"] = cacheControl;
  return new Response(body as BodyInit, { headers });
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const targetUrl = buildMosdacUrl(searchParams);

    // Prepare a one-slot-older fallback in case the requested frame 404s.
    const fallbackParams = new URLSearchParams(searchParams);
    fallbackParams.set(
      "datetime",
      getFallbackDatetime(searchParams.get("datetime") || "")
    );
    const fallbackUrl = buildMosdacUrl(fallbackParams);

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    const response = await fetch(targetUrl, {
      headers: MOSDAC_HEADERS,
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (!response.ok) {
      const fallback = await fetch(fallbackUrl, { headers: MOSDAC_HEADERS });
      if (fallback.ok) {
        return pngResponse(await fallback.arrayBuffer());
      }
      return pngResponse(EMPTY_TILE);
    }

    const imageBuffer = await response.arrayBuffer();
    if (DEBUG) console.log("MOSDAC SIZE:", imageBuffer.byteLength);

    // History frames never change, so cache them hard; live frames briefly.
    const isHistory = searchParams.has("datetime");
    return pngResponse(
      imageBuffer,
      isHistory ? "public, max-age=86400" : "public, max-age=300"
    );
  } catch (error) {
    console.error("MOSDAC WMS proxy failed:", error);
    return pngResponse(EMPTY_TILE);
  }
}
