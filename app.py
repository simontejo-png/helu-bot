"""HeLu Telegram bot hosted as a Render Web Service.

The Telegram polling loop runs in one daemon thread inside the single Gunicorn
worker. Secrets are read only from environment variables; never log their values.
"""
import logging
import os
import threading
from datetime import datetime, timezone

import telebot
from flask import Flask, jsonify
from openai import OpenAI
from supabase import create_client

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("helu")
app = Flask(__name__)

TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()
SYSTEM_PROMPT = """Eres HeLu, el Director Central de Neogenesis Intelligence.
Tu usuario es Simón. Eres un supervisor estratégico.
Responde en español, de forma concisa, profesional y útil.
Usa el historial entregado como contexto; no inventes recuerdos.
"""

_missing = [name for name, value in {
    "TOKEN_TELEGRAM": TOKEN_TELEGRAM,
    "GROQ_API_KEY": GROQ_API_KEY,
    "SUPABASE_URL": SUPABASE_URL,
    "SUPABASE_KEY": SUPABASE_KEY,
}.items() if not value]

cliente_groq = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY) if GROQ_API_KEY else None
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
bot = telebot.TeleBot(TOKEN_TELEGRAM) if TOKEN_TELEGRAM else None
_polling_started = False
_polling_lock = threading.Lock()


def guardar_mensaje(user_id, role, content):
    if supabase is None:
        raise RuntimeError("Supabase no está configurado")
    supabase.table("memoria_chat").insert({
        "user_id": user_id, "role": role, "content": content
    }).execute()


def obtener_historial(user_id):
    if supabase is None:
        raise RuntimeError("Supabase no está configurado")
    respuesta = (supabase.table("memoria_chat")
        .select("role, content")
        .eq("user_id", user_id)
        .order("created_at", desc=False)
        .execute())
    historial = respuesta.data or []
    mensajes = []
    for msg in historial[-10:]:
        if isinstance(msg, dict) and msg.get("role") in ("user", "assistant") and msg.get("content"):
            mensajes.append({"role": msg["role"], "content": str(msg["content"])})
    return mensajes


if bot is not None:
    @bot.message_handler(content_types=["text"])
    def responder(mensaje):
        user_id = mensaje.chat.id
        texto = (mensaje.text or "").strip()
        if not texto:
            return
        if cliente_groq is None or supabase is None:
            bot.reply_to(mensaje, "HeLu está temporalmente sin configuración completa. Avísale al administrador.")
            return
        try:
            guardar_mensaje(user_id, "user", texto)
            historial = obtener_historial(user_id)
            bot.send_chat_action(user_id, "typing")
            respuesta = cliente_groq.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + historial,
                temperature=0.3,
                max_tokens=900,
            ).choices[0].message.content
            if not respuesta:
                raise RuntimeError("El proveedor devolvió una respuesta vacía")
            guardar_mensaje(user_id, "assistant", respuesta)
            bot.reply_to(mensaje, respuesta)
        except Exception:
            log.exception("Falló el procesamiento de un mensaje de Telegram")
            try:
                bot.reply_to(mensaje, "Tuve un problema procesando el mensaje. Inténtalo nuevamente en un momento.")
            except Exception:
                log.exception("No se pudo enviar el mensaje de error a Telegram")


def _run_polling():
    global _polling_started
    if _missing:
        log.error("HeLu no inicia Telegram; faltan variables: %s", ", ".join(_missing))
        return
    try:
        log.info("Iniciando polling de Telegram; modelo Groq: %s", GROQ_MODEL)
        bot.infinity_polling(timeout=20, long_polling_timeout=20, skip_pending=True)
    except Exception:
        log.exception("El polling de Telegram terminó inesperadamente")
    finally:
        _polling_started = False


def start_polling_once():
    global _polling_started
    with _polling_lock:
        if _polling_started or _missing:
            return
        _polling_started = True
        threading.Thread(target=_run_polling, name="helu-telegram-polling", daemon=True).start()


# Gunicorn imports app:app; start the bot at import time. Use one Gunicorn worker.
start_polling_once()


@app.get("/")
def home():
    return jsonify({
        "service": "HeLu", "product": "Neogenesis Intelligence",
        "status": "running" if not _missing and _polling_started else "degraded",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    })


@app.get("/health")
def health():
    return jsonify({
        "service": "HeLu",
        "status": "ok" if not _missing else "degraded",
        "telegram_configured": bool(TOKEN_TELEGRAM),
        "groq_configured": bool(GROQ_API_KEY),
        "supabase_configured": bool(SUPABASE_URL and SUPABASE_KEY),
        "polling_started": _polling_started,
        "missing_environment": _missing,
        "model": GROQ_MODEL,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    }), 200 if not _missing else 503


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
