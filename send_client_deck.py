from __future__ import annotations
import env_loader  # carga .env
from tools.email_tool import send_email


def main(to_email: str, deck_path: str | None = None):
    import os
    # Prefer the 5-slide refined deck by default, fallback to previous if missing
    path = deck_path or "client_deck_rama_5.pptx"
    if not os.path.exists(path):
        path = "client_deck_rama.pptx"
    with open(path, "rb") as f:
        data = f.read()
    subject = "RAMA Agentic AI – Presentación para demo"
    html = (
        "<html><body>"
        "<p>Hola,</p>"
        "<p>Te comparto la presentación del proyecto RAMA Agentic AI para la demo de hoy.</p>"
        "<p>Incluye visión general, flujo de trabajo, plantillas por propiedad (Documentos, Números, Resumen) y beneficios.</p>"
        "<p>Quedo atento a cualquier duda.</p>"
        "<p>Un saludo,</p>"
        "<p>RAMA Team</p>"
        "</body></html>"
    )
    res = send_email([to_email], subject, html, attachments=[("client_deck_rama.pptx", data)])
    print(res)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python send_client_deck.py <email> [path_to_pptx]")
        sys.exit(1)
    deck_path = sys.argv[2] if len(sys.argv) >= 3 else None
    main(sys.argv[1], deck_path)


