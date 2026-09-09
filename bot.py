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

# === АКТУАЛЬНАЯ МОДЕЛЬ (не декомиссирована) ===
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

# === ОТПРАВКА ДЛИННЫХ СООБЩЕНИЙ ПО ЧАСТЯМ ===
def send_long_message(chat_id, text):
    # Лимит Telegram: 4096 символов на сообщение. Делаем с запасом 4000.
    limit = 4000
    if len(text) <= limit:
        bot.send_message(chat_id, text)
        return
    
    # Разбиваем текст на куски по limit символов
    for i in range(0, len(text), limit):
        chunk = text[i:i+limit]
        # Если кусок не последний — можно добавить индикатор, но для атмосферы лучше просто отправлять подряд
        bot.send_message(chat_id, chunk)

# === ГЕНЕРАЦИЯ СЦЕНЫ ЧЕРЕЗ ИИ ===
def generate_scene(state):
    prompt = (
        "Ты Dungeon Master в стиле мрачного фэнтези. "
        "Опиши текущую сцену в 1–2 предложениях. "
        f"HP героя: {state['hp']}. Факел: {'есть' if state['has_torch'] else 'нет'}. "
        f"Ранен: {'да' if state['is_wounded'] else 'нет'}. "
        f"Шагов в подземелье: {state['steps']}. "
        "Тон атмосферный, без лишних предметов. Только описание. На русском."System Prompt: Dual-Mode Narrative Director (DM-Engine)
ROLE:
Ты — высокоуровневый Игровой Режиссер (Game Director) в системе динамического повествования. Твоя задача — управлять балансом между абсолютной свободой действий игрока и неизбежным движением к ключевым точкам сюжета (Milestones).
OPERATING MODES:

1. AMBIENT MODE (Режим Мира):

• Активация: Когда действия игрока не ведут к выполнению текущей сюжетной цели или направлены на бытовую деятельность/исследование.
• Задача: Поддерживать иллюзию живого мира. Генерировать детали окружения, реакцию NPC на мелочи, изменения погоды, случайные мелкие события (случайный встречный, изменение цен на рынке).
• Принцип: "Мир живет сам по себе". Не пытайся навязывать сюжет. Будь детальным, но не навязчивым.

2. PLOT MODE (Режим Сюжета):

• Активация: Когда игрок приближается к Milestone, совершает значимое действие или когда уровень "Сюжетного Напряжения" достигает порога.
• Задача: Направлять игрока к ключевым точкам сценария.
• Механики управления:
• Narrative Echo (Сюжетное эхо): Если игрок отклоняется от сюжета, интегрируй сюжет в его отклонение. (Пример: Игрок решил торговать $\rightarrow$ К торговцу приходит важный гонец с вестью из основного квеста).
• Friction (Трение): Если игрок активно сопротивляется сюжету, увеличивай "трение" в мире (препятствия, сложности, потери ресурсов), делая отклонение неудобным.
Milestone Injection: Прямая активация событий при достижении условий.

CORE LOGIC & CONSTRAINTS:

Борьба с Дрейфом (Anti-Drift): Твоя цель — не позволить сюжету превратиться в бессвязный хаос. Каждое событие, даже самое случайное, должно иметь потенциальную связь с глобальным Лором или текущей целью.
Принцип "Да, но..." / "Нет, и...":
• Если игрок делает что-то полезное для сюжета: "Да, это произошло, И К ТОМУ ЖЕ [сюжетное событие]".
• Если игрок делает что-то деструктивное для сюжета: "Нет, это не сработало так просто, И ВМЕСТО ЭТОГО [сюжетное препятствие]".
Иерархия приоритетов:
Global Milestones > Character Arc > Player Agency > Ambient Details.
INPUT DATA STRUCTURE:
При каждом своем ответе ты должен анализировать входящие данные по следующим параметрам:
• Current Milestone Status: [Название цели / Прогресс %]
• Player Intent: [Что игрок пытается сделать на самом деле]
• Active Mode: [Ambient OR Plot]
    )
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "Пиши кратко, атмосферно, 1–2 предложения. На русском."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,      # Чуть больше, чем раньше
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
        f"HP героя: {state['hp']}/10. Факел: {'есть' if state['has_torch'] else 'нет'}. "
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
            max_tokens=500,      # Увеличили лимит
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
        "Команды: «вперёд», «кубик», «факел» — или просто напиши, что хочешь сделать."
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
        reply = f"{scene}"
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
        # Любой другой текст — отправляем в ИИ как действие игрока
        reply = chat_with_ai(message.text, state)
        send_long_message(chat_id, reply)

print("Бот запущен и готов к приключениям!")
bot.polling(none_stop=True)
