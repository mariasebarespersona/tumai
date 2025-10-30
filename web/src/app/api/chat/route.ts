import { NextRequest, NextResponse } from "next/server";

// Minimal proxy to Python backend.
// Prefer BACKEND_URL; otherwise build from BACKEND_HOST/BACKEND_PORT (Render internal connection)
const BACKEND_URL =
  process.env.BACKEND_URL ||
  (process.env.BACKEND_HOST && process.env.BACKEND_PORT
    ? `http://${process.env.BACKEND_HOST}:${process.env.BACKEND_PORT}`
    : "http://127.0.0.1:7901");

export async function POST(req: NextRequest) {
  try {
    const form = await req.formData();
    const text = String(form.get("text") || "");
    const sessionId = String(form.get("session_id") || "web-ui");
    const propertyId = String(form.get("property_id") || "");
    const files = form.getAll("files");
    const audioFile = form.get("audio") as File | null;

    const fwd = new FormData();
    fwd.append("text", text);
    fwd.append("session_id", sessionId);
    if (propertyId) fwd.append("property_id", propertyId);
    
    // Handle audio file
    if (audioFile) {
      fwd.append("audio", audioFile, audioFile.name);
    }
    
    // Handle regular files
    for (const f of files) {
      if (f instanceof File) {
        fwd.append("files", f, f.name);
      }
    }

    // Expect your Python backend to expose a /ui_chat endpoint that accepts multipart/form-data
    const resp = await fetch(`${BACKEND_URL}/ui_chat`, { method: "POST", body: fwd });
    const textResp = await resp.text();
    let data: any = {};
    try { data = JSON.parse(textResp); } catch { /* leave as text */ }
    if (!resp.ok) {
      return NextResponse.json({ error: data?.detail || textResp || `HTTP ${resp.status}` }, { status: resp.status });
    }
    if (typeof data === "string") {
      return NextResponse.json({ answer: data });
    }
    return NextResponse.json({
      answer: data?.answer ?? data?.content ?? "(sin respuesta)",
      property_id: data?.property_id,
      property_name: data?.property_name, // Include property name from backend
      transcript: data?.transcript,
      audio_response: data?.audio_response, // For voice responses
    });
  } catch (e: any) {
    return NextResponse.json({ error: e?.message || String(e) }, { status: 500 });
  }
}