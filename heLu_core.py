import telebot
import json
import os
from openai import OpenAI
from supabase import create_client, Client

# --- CONFIGURACION (PON TUS CLAVES AQUI) ---
import os
TOKEN_TELEGRAM = os.environ.get("TOKEN_TELEGRAM")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

cliente_groq = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_API_KEY)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

SYSTEM_PROMPT = """Eres HeLu, el Director Central de Neogenesis Intelligence.
Tu usuario es Simón. Eres un supervisor estratégico. 
Responde de forma concisa y profesional. Recuerda lo que Simón te ha dicho antes."""

bot = telebot.TeleBot(TOKEN_TELEGRAM)

def guardar_mensaje(user_id, role, content):
    try:
        supabase.table("memoria_chat").insert({
            "user_id": user_id,
            "role": role,
            "content": content
        }).execute()
    except Exception as e:
        print(f"Error guardando en Supabase: {e}")
def obtener_historial(user_id):
    try:
        # Hacemos la consulta
        respuesta = supabase.table("memoria_chat")\
            .select("role, content")\
            .eq("user_id", user_id)\
            .order("created_at", desc=False)\
            .execute()
        
        # Si no hay datos, devolvemos vacio
        if not respuesta.data:
            return []
            
        # Tomamos los ultimos 10 mensajes
        historial = respuesta.data[-10:]
        
        mensajes = []
        for msg in historial:
            # Verificamos que sea un diccionario para evitar el error
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content:
                    mensajes.append({"role": role, "content": content})
            
        return mensajes
    except Exception as e:
        print(f"Error leyendo Supabase: {e}")
        return []
@bot.message_handler(func=lambda message: True)
def responder(mensaje):
    user_id = mensaje.chat.id
    texto_usuario = mensaje.text

    # 1. Guardar lo que dijo el usuario en la nube
    guardar_mensaje(user_id, "user", texto_usuario)

    # 2. Obtener la memoria de la nube
    historial = obtener_historial(user_id)
    
    # 3. Armar el contexto para Groq
    mensajes_groq = [{"role": "system", "content": SYSTEM_PROMPT}] + historial

    bot.send_chat_action(user_id, 'typing')

    try:
        respuesta_ia = cliente_groq.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=mensajes_groq
        ).choices[0].message.content
        
        # 4. Guardar la respuesta de HeLu en la nube
        guardar_mensaje(user_id, "assistant", respuesta_ia)
        
        bot.reply_to(mensaje, respuesta_ia)
        
    except Exception as e:
        bot.reply_to(mensaje, f"Error en Groq: {e}")

print("🤖 HeLu (Memoria en Supabase) encendido...")
bot.infinity_polling()
