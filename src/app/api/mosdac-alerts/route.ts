import { MOSDAC_HEADERS } from "../../../lib/mosdac";

export async function GET() {
  try {
    const response = await fetch(
      "https://www.mosdac.gov.in/live/backend/rain_cloudburst.php",
      { headers: MOSDAC_HEADERS, cache: "no-store" }
    );

    const text = await response.text();

    // The upstream response occasionally has stray characters around the JSON,
    // so slice from the first "{" to the last "}" before parsing — server-side,
    // so the client can just call res.json().
    const start = text.indexOf("{");
    const end = text.lastIndexOf("}");
    if (start === -1 || end === -1) {
      return Response.json({ features: [] });
    }

    const parsed = JSON.parse(text.slice(start, end + 1));
    return Response.json(parsed, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (error) {
    console.error("MOSDAC alerts fetch failed:", error);
    return Response.json({ features: [] });
  }
}
