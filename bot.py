import telebot
import random
import base64
from openai import OpenAI

# --- СЕКРЕТНАЯ ФРАЗА ---
SECRET = "mySecretDnd2026"

# --- ЗАШИФРОВАННЫЕ КЛЮЧИ ---
ENC_TELEGRAM = "VUFqXVtEXU1xW15zcXUPVUAqJioAV0cLLx0AZ0N4DCYHKxMoNBl0MRJKVF5+Cg=="
ENC_GROQ = "Cgo4Ogk0IjYhGStbdUpBFTU/DSE4KQ0ROSNWSVAFKyAnLyw8NAYdPRNncllTFUgGFAIQMCwxKBY="

# --- РАСШИФРОВКА ---
def decrypt(encrypted: str, secret: str) -> str:
    key_bytes = secret.encode("utf-8")
    xored = base64.b64decode(encrypted)
    raw = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(xored)])
    return raw.decode("utf-8")

TELEGRAM_TOKEN = decrypt(ENC_TELEGRAM, SECRET)
GROQ_API_KEY = decrypt(ENC_GROQ, SECRET)

# --- КЛИЕНТ GROQ ---
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# --- СОСТОЯНИЕ ИГРОКОВ ---
player_state = {}

def get_state(chat_id):
    if chat_id not in player_state:
        player_state[chat_id] = {
            "hp": 10,
            "has_torch": False,
            "is_wounded": False,
            "steps": 0
        }
    return player_state[chat_id]

# --- ГЕНЕРАЦИЯ СЦЕНЫ ---
def generate_scene(state):
    prompt = (
        "Ты Dungeon Master в стиле мрачного фэнтези. "
        "Опиши текущую сцену в 1–2 предложениях. "
        f"HP героя: {state['hp']}. Факел: {'есть' if state['has_torch'] else 'нет'}. "
        f"Ранен: {'да' if state['is_wounded'] else 'нет'}. "
        f"Шагов в подземелье: {state['steps']}. "
        "Тон атмосферный, без лишних предметов. Только описание."
    )
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Пиши кратко, атмосферно, 1–2 предложения. На русском."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=60,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Темнота окружает тебя. Ничего не разобрать."

# --- ОБРАБОТЧИКИ ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    state = get_state(message.chat.id)
    state["hp"] = 10
    state["has_torch"] = False
    state["is_wounded"] = False
    state["steps"] = 0
    scene = generate_scene(state)
    bot.reply_to(
        message,
        f"{scene}\n\nHP: {state['hp']}/10. "
        "Команды: «вперёд», «кубик», «факел»."
    )

@bot.message_handler(func=lambda m: True)
def echo_all(message):
    chat_id = message.chat.id
    state = get_state(chat_id)
    text = message.text.lower()

    if text == "вперёд":
        state["steps"] += 1
        scene = generate_scene(state)
        bot.reply_to(message, f"{scene}\nЧто будешь делать дальше?")
    elif text == "кубик" or text == "d20":
        bot.reply_to(message, f"🎲 d20: {random.randint(1, 20)}")
    elif text == "факел":
        if not state["has_torch"]:
            state["has_torch"] = True
            bot.reply_to(message, "Ты зажёг факел. Пламя дрожит от сквозняка.")
        else:
            bot.reply_to(message, "Факел уже горит.")
    else:
        bot.reply_to(message, "Команды: «вперёд», «кубик», «факел».")

print("Бот с Groq запущен...")
bot.polling(non
            e_stop=True)
