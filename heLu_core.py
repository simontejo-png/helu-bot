import telebot
import requests
import json
import os

TOKEN = "8960825461:AAFuuVIdvHF1Aql1RYTRAsRWnJ5gTErqNO4"
MEMORIA_FILE = "memoria_telegram.json"

SYSTEM_PROMPT = """Eres HeLu, el Director Central de Neogenesis Intelligence.
Tu usuario es Simon.
Eres un supervisor estrategico. 
Reglas:
1. Responde de forma concisa.
2. Si Simon te pide un plan, descomponlo en tareas.
3. Si Simon te pregunta por misiones, revisa tu archivo de misiones.
"""

bot = telebot.TeleBot(TOKEN)

def obtener_misiones():
    if os.path.exists("misiones_helu.json"):
        with open("misiones_helu.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def cargar_memoria():
    if os.path.exists(MEMORIA_FILE):
        with open(MEMORIA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return [{"role": "system", "content": SYSTEM_PROMPT}]

def guardar_memoria(historial):
    with open(MEMORIA_FILE, "w", encoding="utf-8") as f:
        json.dump(historial, f, ensure_ascii=False, indent=4)

@bot.message_handler(func=lambda message: True)
def responder(mensaje):
    chat_id = mensaje.chat.id
    texto_usuario = mensaje.text

    # 1. Comprobar si pide misiones (Supervisor)
    if "mision" in texto_usuario.lower() or "tarea" in texto_usuario.lower():
        misiones = obtener_misiones()
        if misiones:
            respuesta = "📋 *Misiones Pendientes:*\n"
            for m in misiones:
                respuesta += f"\n*Objetivo:* {m.get('objetivo', 'Sin titulo')}\n"
                for t in m.get('plan', []):
                    respuesta += f"  • {t.get('tarea', 'Tarea')} [{t.get('estado', 'Pendiente')}]\n"
            bot.reply_to(mensaje, respuesta, parse_mode='Markdown')
        else:
            bot.reply_to(mensaje, "No hay misiones registradas aun.")
        return

    # 2. Si es una conversacion normal, usar Ollama
    historial = cargar_memoria()
    historial.append({"role": "user", "content": texto_usuario})

    datos = {
        "model": "qwen2.5:3b",
        "messages": historial[-6:],
        "stream": False
    }

    bot.send_chat_action(chat_id, 'typing')

    try:
        respuesta = requests.post("http://localhost:11434/api/chat", json=datos)
        respuesta_texto = respuesta.json()['message']['content']
        
        historial.append({"role": "assistant", "content": respuesta_texto})
        guardar_memoria(historial)
        
        bot.reply_to(mensaje, respuesta_texto)
        
    except Exception as e:
        bot.reply_to(mensaje, f"Error: {e}")

print("🤖 HeLu Core (Supervisor) encendido en Telegram...")
bot.infinity_polling()
