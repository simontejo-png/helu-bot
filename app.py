import os
import threading
from flask import Flask
import telebot
from openai import OpenAI
from supabase import create_client

app = Flask(__name__)

# Leer las claves de Render
TOKEN_TELEGRAM = os.environ.get("TOKEN_TELEGRAM")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Conexiones
cliente_groq = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
bot = telebot.TeleBot(TOKEN_TELEGRAM)

# (Aqui va el resto de tu codigo de heLu_core, la logica del bot)
SYSTEM_PROMPT = "Eres HeLu, el Director Central de Neogenesis Intelligence."

def guardar_mensaje(user_id, role, content):
    try:
        supabase.table("memoria_chat").insert({"user_id": user_id, "role": role, "content": content}).execute()
    except Exception as e:
        print(f"Error guardando: {e}")

def obtener_historial(user_id):
    try:
        respuesta = supabase.table("memoria_chat").select("role, content").eq("user_id", user_id).order("created_at", desc=False).execute()
        historial = respuesta.data[-10:]
        mensajes = []
        for msg in historial:
            if isinstance(msg, dict):
                mensajes.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
        return mensajes
    except Exception as e:
        return []

@bot.message_handler(func=lambda message: True)
def responder(mensaje):
    user_id = mensaje.chat.id
    texto = mensaje.text
    guardar_mensaje(user_id, "user", texto)
    historial = obtener_historial(user_id)
    bot.send_chat_action(user_id, 'typing')
    try:
        respuesta = cliente_groq.chat.completions.create(model="openai/gpt-oss-20b", messages=[{"role": "system", "content": SYSTEM_PROMPT}] + historial).choices[0].message.content
        guardar_mensaje(user_id, "assistant", respuesta)
        bot.reply_to(mensaje, respuesta)
    except Exception as e:
        bot.reply_to(mensaje, f"Error: {e}")

@app.route('/')
def home():
    return "HeLu está vivo"

@app.route('/health')
def health():
    return "OK"

# --- AQUI ESTA LA MAGIA ---
# Iniciamos el bot de Telegram en un hilo separado antes de que Flask arranque
print("Iniciando bot de Telegram...")
threading.Thread(target=bot.infinity_polling, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
