import telebot
import os
import random
from openai import OpenAI

# === КЛЮЧИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ BOTHOST ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# === ИНИЦИАЛИЗАЦИЯ ===
bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

MODEL = "llama-3.3-70b-versatile"

# === СОСТОЯНИЕ ИГРОКОВ ===
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

# === ГЕНЕРАЦИЯ СЦЕНЫ ЧЕРЕЗ ИИ ===
def generate_scene(state):
    prompt = (
        "Ты Dungeon Master в стиле мрачного фэнтези. "
        "Опиши текущую сцену в 1–2 предложениях. "
        f"HP героя: {state['hp']}. Факел: {'есть' if state['has_torch'] else 'нет'}. "
        f"Ранен: {'да' if state['is_wounded'] else 'нет'}. "
        f"Шагов в подземелье: {state['steps']}. "
        "Тон атмосферный, без лишних предметов. Только описание. На русском."
    )
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "Пиши кратко, атмосферно, 1–2 предложения. На русском."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Тьма сгущается... (ошибка: {e})"

# === СВОБОДНЫЙ РАЗГОВОР С ИИ ===
def chat_with_ai(user_text, state):
    system_prompt = (
        "Ты Dungeon Master в мрачном фэнтези-подземелье. "
        "Отвечай коротко, атмосферно, на русском. "
        f"HP героя: {state['hp']}. Факел: {'есть' if state['has_torch'] else 'нет'}. "
        f"Ранен: {'да' if state['is_wounded'] else 'нет'}. "
        f"Шагов: {state['steps']}."
    )
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text}
            ],
            max_tokens=150,
            temperature=0.8
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Голос подземелья молчит... (ошибка: {e})"

# === ОБРАБОТЧИКИ ===

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
        f"🎭 {scene}\n\n"
        f"❤️ HP: {state['hp']}/10\n"
        "Команды: «вперёд», «кубик», «факел» — или просто напиши, что хочешь сделать."
    )

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    chat_id = message.chat.id
    state = get_state(chat_id)
    text = message.text.lower().strip()

    if text == "вперёд":
        state["steps"] += 1
        # Случайное событие
        roll = random.randint(1, 20)
        if roll <= 5:
            state["hp"] -= 1
            state["is_wounded"] = True
            event = "Что-то пошло не так..."
        elif roll >= 18:
            state["hp"] = min(state["hp"] + 1, 10)
            state["is_wounded"] = False
            event = "Удача на твоей стороне!"
        else:
            event = ""

        scene = generate_scene(state)
        reply = f"{scene}"
        if event:
            reply += f"\n⚡️ {event}"
        reply += f"\n❤️ HP: {state['hp']}/10"
        bot.reply_to(message, reply)

    elif text in ("кубик", "d20", "dice"):
        bot.reply_to(message, f"🎲 d20: {random.randint(1, 20)}")

    elif text == "факел":
        if not state["has_torch"]:
            state["has_torch"] = True
            bot.reply_to(message, "🔥 Ты зажёг факел. Пламя дрожит от сквозняка.")
        else:
            bot.reply_to(message, "Факел уже горит.")

    else:
        # Любой другой текст — отправляем в ИИ как действие игрока
        reply = chat_with_ai(message.text, state)
        bot.reply_to(message, reply)

print("Бот запущен и готов к приключениям!")
bot.polling(none_stop=True)
