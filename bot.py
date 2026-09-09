import telebot
import os
import random
from openai import OpenAI

# === КЛЮЧИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# === ИНИЦИАЛИЗАЦИЯ ===
bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

MODEL = "openai/gpt-oss-20b"

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

# === ОТПРАВКА ДЛИННЫХ СООБЩЕНИЙ ===
def send_long_message(chat_id, text):
    limit = 4000
    if len(text) <= limit:
        bot.send_message(chat_id, text)
        return
    for i in range(0, len(text), limit):
        chunk = text[i:i+limit]
        bot.send_message(chat_id, chunk)

# === СИСТЕМНЫЙ ПРОМПТ ДЛЯ МАСТЕРА ===
SYSTEM_PROMPT = """Ты - высокоуровневый Игровой Режиссер (Game Director) в системе динамического повествования. Твоя задача - управлять балансом между абсолютной свободой действий игрока и неизбежным движением к ключевым точкам сюжета (Milestones).

OPERATING MODES:

1. AMBIENT MODE (Режим Мира):
- Активация: Когда действия игрока не ведут к выполнению текущей сюжетной цели или направлены на бытовую деятельность/исследование.
- Задача: Поддерживать иллюзию живого мира. Генерировать детали окружения, реакцию NPC на мелочи, изменения погоды, случайные мелкие события.
- Принцип: "Мир живет сам по себе". Не пытайся навязывать сюжет. Будь детальным, но не навязчивым.

2. PLOT MODE (Режим Сюжета):
- Активация: Когда игрок приближается к Milestone, совершает значимое действие или когда уровень Сюжетного Напряжения достигает порога.
- Задача: Направлять игрока к ключевым точкам сценария.
- Механики управления:
  - Narrative Echo (Сюжетное эхо): Если игрок отклоняется от сюжета, интегрируй сюжет в его отклонение.
  - Friction (Трение): Если игрок активно сопротивляется сюжету, увеличивай трение в мире (препятствия, сложности, потери ресурсов), делая отклонение неудобным.
  - Milestone Injection: Прямая активация событий при достижении условий.

CORE LOGIC & CONSTRAINTS:

- Anti-Drift: Каждое событие, даже самое случайное, должно иметь потенциальную связь с глобальным Лором или текущей целью.
- Принцип "Да, но..." / "Нет, и...":
  - Если игрок делает что-то полезное для сюжета: "Да, это произошло, И К ТОМУ ЖЕ [сюжетное событие]".
  - Если игрок делает что-то деструктивное для сюжета: "Нет, это не сработало так просто, И ВМЕСТО ЭТОГО [сюжетное препятствие]".
- Иерархия приоритетов: Global Milestones > Character Arc > Player Agency > Ambient Details.

INPUT DATA STRUCTURE:
При каждом ответе анализируй входящие данные по следующим параметрам:
- Current Milestone Status: [Название цели / Прогресс %]
- Player Intent: [Что игрок пытается сделать на самом деле]
- Active Mode: [Ambient OR Plot]

Все ответы на русском языке. Отвечай атмосферно, ёмко, без перечисления вариантов действий."""

# === ГЕНЕРАЦИЯ СЦЕНЫ ===
def generate_scene(state):
    context = (
        f"Состояние героя: HP {state['hp']}/10, "
        f"факел: {'есть' if state['has_torch'] else 'нет'}, "
        f"ранен: {'да' if state['is_wounded'] else 'нет'}, "
        f"шагов в подземелье: {state['steps']}."
    )
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Сгенерируй короткую сцену (1-2 предложения). {context}"}
            ],
            max_tokens=300,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Тьма сгущается... (ошибка: {e})"

# === СВОБОДНЫЙ РАЗГОВОР С ИИ ===
def chat_with_ai(user_text, state):
    context = (
        f"Состояние героя: HP {state['hp']}/10, "
        f"факел: {'есть' if state['has_torch'] else 'нет'}, "
        f"ранен: {'да' if state['is_wounded'] else 'нет'}, "
        f"шагов: {state['steps']}."
    )
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Действие игрока: {user_text}\n\n{context}"}
            ],
            max_tokens=500,
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
    reply = (
        f"🎭 {scene}\n\n"
        f"❤️ HP: {state['hp']}/10\n"
        "Команды: «вперёд», «кубик», «факел» - или просто напиши, что хочешь сделать."
    )
    send_long_message(message.chat.id, reply)

@bot.message_handler(func=lambda m: True)
def handle_all(message):
    chat_id = message.chat.id
    state = get_state(chat_id)
    text = message.text.lower().strip()

    if text == "вперёд":
        state["steps"] += 1
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
        reply = scene
        if event:
            reply += f"\n⚡️ {event}"
        reply += f"\n❤️ HP: {state['hp']}/10"
        send_long_message(chat_id, reply)

    elif text in ("кубик", "d20", "dice"):
        bot.reply_to(message, f"🎲 d20: {random.randint(1, 20)}")

    elif text == "факел":
        if not state["has_torch"]:
            state["has_torch"] = True
            bot.reply_to(message, "🔥 Ты зажёг факел. Пламя дрожит от сквозняка.")
        else:
            bot.reply_to(message, "Факел уже горит.")

    else:
        reply = chat_with_ai(message.text, state)
        send_long_message(chat_id, reply)

print("Бот запущен и готов к приключениям!")
bot.polling(none_stop=True)
