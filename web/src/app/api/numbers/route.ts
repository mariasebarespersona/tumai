import { NextRequest, NextResponse } from "next/server";

// Minimal proxy to Python backend for numbers endpoint.
// Prefer BACKEND_URL; otherwise build from BACKEND_HOST/BACKEND_PORT (Render internal connection)
const BACKEND_URL = (() => {
  if (process.env.BACKEND_URL) return process.env.BACKEND_URL;
  const host = process.env.BACKEND_HOST;
  // Prefer HTTPS to public host; Render terminates TLS at the edge
  if (host) return `https://${host}`;
  return "http://127.0.0.1:7901";
})();

export async function GET(req: NextRequest) {
  try {
    const { searchParams } = new URL(req.url);
    const propertyId = searchParams.get("property_id");
    const templateKey = searchParams.get("template_key");

    if (!propertyId) {
      return NextResponse.json({ error: "property_id is required" }, { status: 400 });
    }

    // Build query string for backend
    const queryParams = new URLSearchParams({ property_id: propertyId });
    if (templateKey) {
      queryParams.append("template_key", templateKey);
    }

    // Forward request to Python backend
    const resp = await fetch(`${BACKEND_URL}/api/numbers?${queryParams.toString()}`, {
      method: "GET",
      headers: {
        "Accept": "application/json",
      },
    });

    if (!resp.ok) {
      const errorText = await resp.text();
      let errorData: any = {};
      try {
        errorData = JSON.parse(errorText);
      } catch {
        // Leave as text
      }
      return NextResponse.json(
        { error: errorData?.error || errorText || `HTTP ${resp.status}` },
        { status: resp.status }
      );
    }

    const data = await resp.json();
    return NextResponse.json(data);
  } catch (e: any) {
    console.error("[api/numbers] Error:", e);
    return NextResponse.json({ error: e?.message || String(e) }, { status: 500 });
  }
}

