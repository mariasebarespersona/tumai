#!/usr/bin/env python3
"""
Script para obtener un token JWT real de Microsoft Graph API.
Requiere: pip install msal requests
"""

import sys
import json

try:
    from msal import PublicClientApplication
except ImportError:
    print("ERROR: Necesitas instalar msal: pip install msal")
    sys.exit(1)

# Configuración - Reemplaza con tus valores
CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70d66767"  # Graph Explorer app ID (público)
SCOPES = [
    "Files.ReadWrite.All",
    "Sites.ReadWrite.All",
    "User.Read"
]

def get_token():
    """Obtiene un token JWT de Microsoft Graph."""
    app = PublicClientApplication(
        client_id=CLIENT_ID,
        authority="https://login.microsoftonline.com/common"
    )
    
    print("🔐 Iniciando autenticación...")
    print("Se abrirá una ventana del navegador para iniciar sesión.")
    print()
    
    # Intentar obtener token del caché primero
    accounts = app.get_accounts()
    result = None
    
    if accounts:
        print(f"📋 Encontradas {len(accounts)} cuenta(s) en caché.")
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
    
    # Si no hay token en caché, hacer login interactivo
    if not result:
        print("🔑 Iniciando sesión interactiva...")
        result = app.acquire_token_interactive(scopes=SCOPES)
    
    if "access_token" in result:
        token = result["access_token"]
        print("✅ Token obtenido exitosamente!")
        print()
        print("=" * 80)
        print("TOKEN (copia esto a GRAPH_ACCESS_TOKEN en web/.env.local):")
        print("=" * 80)
        print(token)
        print("=" * 80)
        print()
        print(f"📊 Token info:")
        print(f"   - Tipo: JWT")
        print(f"   - Longitud: {len(token)} caracteres")
        print(f"   - Empieza con: {token[:10]}...")
        print(f"   - Tiene puntos: {'Sí' if '.' in token else 'No'}")
        print()
        return token
    else:
        print("❌ Error al obtener token:")
        print(json.dumps(result, indent=2))
        sys.exit(1)

if __name__ == "__main__":
    get_token()

