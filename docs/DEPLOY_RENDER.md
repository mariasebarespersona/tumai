## Deploy en Render (rápido y sin complicaciones)

Esta guía usa Render Blueprints (render.yaml) para levantar el backend (FastAPI) y el frontend (Next.js) con 1 click.

### Prerrequisitos
- Cuenta en Render con GitHub conectado.
- Secrets listos en Render: `OPENAI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (y opcional `LOGFIRE_TOKEN`).

### 1) Desplegar usando el blueprint
1. Haz push al repo con el archivo `render.yaml` en la raíz (ya añadido).
2. Abre: https://render.com/deploy?repo=<URL_DE_TU_REPO_GITHUB>
3. Render detectará `render.yaml` y te mostrará 2 servicios:
   - `rama-api` (Python/FastAPI)
   - `rama-web` (Next.js)
4. En la pantalla de variables, crea los secrets que falten (los que el blueprint marca con `fromSecret`).
5. Click en "Apply" → Render lanzará ambos servicios.

Notas:
- El backend expone FastAPI con `uvicorn` y tiene CORS abierto inicialmente (`ALLOW_ALL_CORS=1`) para simplificar. Luego puedes cambiar a `WEB_BASE` con el dominio de `rama-web` para endurecer CORS.
- El frontend obtiene `NEXT_PUBLIC_API_URL` automáticamente desde la URL pública de `rama-api` (via `fromService`).

### 2) Variables de entorno mínimas
- Backend (`rama-api`):
  - `OPENAI_API_KEY`
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - `ALLOW_ALL_CORS=1` (opcional; para producción reemplaza por `WEB_BASE=https://<tu-frontend>.onrender.com`)
  - `LOGFIRE_TOKEN` (opcional)

- Frontend (`rama-web`):
  - `NEXT_PUBLIC_API_URL` se inyecta automáticamente desde el backend.

### 3) Comandos y versiones
- Backend: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Python: `3.12.3`
- Frontend: `npm ci && npm run build` / `npm run start -p $PORT`
- Node: `20`

### 4) Post-deploy (sanidad)
1. Abre `https://<rama-web>.onrender.com` (Next.js).
2. Abre `/dashboard/evals` y verifica que carga sin CORS.
3. Envía un mensaje en el chat y da 👍; comprueba que aparece en el dashboard.

### 5) Desarrollo local mientras producción corre
- Sigue trabajando en ramas locales; cada push al repo no afecta producción hasta merge a `main` (si Render está apuntado a `main`).
- Si quieres previsualizaciones, crea un segundo blueprint/servicio “staging” o usa otra rama con auto-deploy activado.

### 6) Endurecer CORS (recomendado luego)
1. En `rama-api`, elimina `ALLOW_ALL_CORS` y añade:
   - `WEB_BASE=https://<rama-web>.onrender.com`
2. Redeploy del backend.

### 7) Problemas comunes
- `Failed to fetch` desde el frontend: revisa que `NEXT_PUBLIC_API_URL` apunte al backend público y CORS permita el dominio del frontend.
- `ModuleNotFoundError: openpyxl` en backend: ya se añadió a `requirements.txt`. Si aparece, redeploy forzando “Clear build cache”.

Listo. Con esto tienes la app funcionando en Render con el mínimo esfuerzo.


