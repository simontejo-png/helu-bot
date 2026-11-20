HeLu Telegram Bot — Render Web Service

RENDER CONFIGURATION
Service type: Web Service, not Background Worker. Free plan does not support free workers.
Runtime: Python 3.
Build command: pip install -r requirements.txt
Start command: gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 90 (PORT is supplied automatically by Render).
Health check path: /health

The Telegram polling loop starts once when the single Gunicorn worker imports app:app. Do not increase Gunicorn workers: each worker would create another Telegram poller.

REQUIRED RENDER ENVIRONMENT VARIABLES
TOKEN_TELEGRAM
GROQ_API_KEY
SUPABASE_URL
SUPABASE_KEY
Optional: GROQ_MODEL (defaults to openai/gpt-oss-20b).

Never put secrets in Git or logs. Supabase must contain a memoria_chat table with user_id, role, content, and created_at columns. Keep user_id compatible with the existing integer Telegram chat ID.

FREE PLAN CAVEAT
Render Free Web Services sleep after 15 minutes without inbound HTTP or WebSocket traffic and may restart at any time. Telegram polling is outbound traffic and does not keep the service awake. For a pilot, configure an external uptime monitor to request /health every 5 minutes. This can keep inbound traffic flowing but is not an uptime guarantee or production SLA.

HEALTH SEMANTICS
/health reports whether Telegram, Groq and Supabase variables are configured. It does not verify external credentials or the Supabase schema end-to-end. Confirm operation by sending a Telegram message and checking both the reply and a persisted row in Supabase.
