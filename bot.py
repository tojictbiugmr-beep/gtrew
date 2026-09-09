import telebot
import os
import random
from openai import OpenAI
from memory import (
    load_state, save_state, add_to_history, add_world_event,
    set_world_fact, build_memory_context, maybe_summarize, reset_state, CLASS_STATS
)

# === КЛЮЧИ ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# === ИНИЦИАЛИЗАЦИЯ ===
bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)
MODEL = "groq/compound-mini"

# === СОСТОЯНИЕ ИГРОКОВ ===
player_state = {}

def get_state(chat_id):
    if chat_id not in player_state:
        state = load_state(chat_id)
        player_state[chat_id] = state
    return player_state[chat_id]

def save_chat(chat_id):
    state = player_state.get(chat_id)
    if state:
        save_state(chat_id, state)

# === ОТПРАВКА ДЛИННЫХ СООБЩЕНИЙ ===
def send_long_message(chat_id, text):
    limit = 4000
    if len(text) <= limit:
        bot.send_message(chat_id, text)
        return
    for i in range(0, len(text), limit):
        chunk = text[i:i+limit]
        bot.send_message(chat_id, chunk)

# === ПРОМПТ МАСТЕРА ===
SYSTEM_PROMPT = (
    "Ты - Dungeon Master мрачного фэнтези. Веди сюжет к ключевым точкам, "
    "но не лишай игрока свободы. Используй принцип 'Да, но...' или 'Нет, и...'. "
    "Каждое случайное событие должно быть связано с глобальным лором. "
    "Пиши атмосферно, на русском, без списков и маркеров. Только живой текст. "
    "Используй факты из памяти и НАВЫКИ героя для поддержания непрерывности мира."
)

# === ГЕНЕРАЦИЯ СЦЕНЫ ===
def generate_scene(state):
    memory = build_memory_context(state)
    status = (
        f"HP: {state['hp']}/{state['max_hp']}, факел: {'есть' if state['has_torch'] else 'нет'}, "
        f"ранен: {'да' if state['is_wounded'] else 'нет'}, шагов: {state['steps']}."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Контекст памяти:\n{memory}"},
        {"role": "user", "content": f"Опиши сцену в 2-3 предложениях. Контекст героя: {status}"}
    ]
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )
        scene_text = response.choices[0].message.content.strip()
        add_to_history(state, "assistant", scene_text)
        return scene_text
    except Exception as e:
        return f"Тьма сгущается... (ошибка: {e})"

# === СВОБОДНЫЙ РАЗГОВОР С ИИ ===
def chat_with_ai(user_text, state):
    memory = build_memory_context(state)
    status = (
        f"HP: {state['hp']}/{state['max_hp']}, факел: {'есть' if state['has_torch'] else 'нет'}, "
        f"ранен: {'да' if state['is_wounded'] else 'нет'}, шагов: {state['steps']}."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Контекст памяти:\n{memory}"}
    ]
    for entry in state["chat_history"]:
        messages.append({"role": entry["role"], "content": entry["content"]})
    user_msg = f"Игрок делает: {user_text}\nКонтекст героя: {status}"
    messages.append({"role": "user", "content": user_msg})

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=800,
            temperature=0.8
        )
        reply = response.choices[0].message.content.strip()
        add_to_history(state, "user", user_text)
        add_to_history(state, "assistant", reply)
        state["turn_count"] += 1
        maybe_summarize(state, client, MODEL)
        return reply
    except Exception as e:
        return f"Голос подземелья молчит... (ошибка: {e})"

# === МЕХАНИКА БРОСКА D20 И НАВЫКОВ ===

def calculate_bonus(state, skill_type):
    """Бонус = навык героя (отклонение от 10) + ситуативные модификаторы из фактов мира."""
    bonus = 0
    skills = state.get("skills", {})
    
    # Базовый бонус: насколько навык отличается от среднего значения 10
    if skill_type in skills:
        bonus += skills[skill_type] - 10

    # Ситуативные модификаторы (факты мира)
    facts = state.get("world_facts", {})

    if skill_type == "знание":
        if "Древний_пергамент" in facts:
            bonus += 2
        if "Кристалл_холодный_свет" in facts:
            bonus += 1

    elif skill_type == "ловкость":
        if "Холодный_ветер_в_зале" in facts:
            bonus -= 1

    return bonus

def roll_d20(state, skill_type="обычный"):
    roll = random.randint(1, 20)
    bonus = calculate_bonus(state, skill_type) if skill_type != "обычный" else 0
    total = roll + bonus

    result_type = ""
    description = ""

    if roll == 20:
        result_type = "КРИТИЧЕСКИЙ УСПЕХ"
        description = "Судьба благоволит тебе: даже если обстоятельства против, твой поступок выходит за рамки обычного."
    elif roll == 1:
        result_type = "КРИТИЧЕСКАЯ НЕУДАЧА"
        description = "Всё идёт не так: ты теряешь равновесие, инструмент ломается, или звук разносится по коридору, привлекая внимание."
    elif total >= 15:
        result_type = "УСПЕХ"
        description = "Тебе удаётся задуманное, хотя и не без усилий."
    elif total >= 10:
        result_type = "ПОГРАНИЧНЫЙ РЕЗУЛЬТАТ"
        description = "Ты почти справляешься, но что-то идёт не совсем так, как хотелось."
    else:
        result_type = "НЕУДАЧА"
        description = "К сожалению, попытка не удалась. Возможно, стоит попробовать другой подход."

    return roll, bonus, total, result_type, description

# === ОБРАБОТЧИКИ ===

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    state = reset_state(chat_id)
    player_state[chat_id] = state

    reply = (
        "Добро пожаловать в мрачные руины!\n\n"
        "Выбери класс героя, чтобы получить стартовые характеристики и 5 очков для прокачки:\n"
        "  /класс воин\n"
        "  /класс маг\n"
        "  /класс разбойник\n\n"
        "После выбора класса используй /прокачка, чтобы распределить очки."
    )
    send_long_message(chat_id, reply)
    save_chat(chat_id)

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("/класс "))
def set_class(message):
    chat_id = message.chat.id
    state = get_state(chat_id)
    text = message.text.lower()
    class_name = text.replace("/класс ", "").strip()

    if class_name not in CLASS_STATS:
        send_long_message(chat_id, "Неверный класс. Доступные: воин, маг, разбойник.")
        return

    state["class_name"] = class_name
    base_stats = CLASS_STATS[class_name]
    state["skills"] = base_stats.copy()
    state["skill_points_remaining"] = 5

    reply = (
        f"Ты выбрал класс: {class_name}.\n\n"
        f"Твои базовые характеристики: {', '.join([f'{k}: {v}' for k, v in base_stats.items()])}\n"
        f"У тебя есть {state['skill_points_remaining']} очков, чтобы усилить навыки.\n\n"
        "Используй команду /прокачка сила +2, /прокачка ловкость -1 и т. д., чтобы менять значения.\n"
        "Помни: нельзя тратить больше очков, чем у тебя есть, и нельзя опускать навык ниже 6."
    )
    send_long_message(chat_id, reply)
    save_chat(chat_id)

@bot.message_handler(func=lambda m: m.text and m.text.lower().startswith("/прокачка "))
def upgrade_skill(message):
    chat_id = message.chat.id
    state = get_state(chat_id)
    parts = message.text.lower().replace("/прокачка ", "").split()

    if len(parts) < 2:
        send_long_message(chat_id, "Формат: /прокачка <навык> <изменение>, например: /прокачка сила +2")
        return

    skill = parts[0]
    change_str = parts[1]

    if skill not in state["skills"]:
        send_long_message(chat_id, f"Неверный навык. Доступные: {', '.join(state['skills'].keys())}")
        return

    try:
        change = int(change_str)
    except ValueError:
        send_long_message(chat_id, "Изменение должно быть числом, например +2 или -1.")
        return

    current = state["skills"][skill]
    new_val = current + change

    if new_val < 6:
        send_long_message(chat_id, f"Навык нельзя опустить ниже 6. Сейчас: {current}.")
        return

    cost = abs(change)
    if change > 0 and cost > state["skill_points_remaining"]:
        send_long_message(chat_id, f"Не хватает очков прокачки. Осталось: {state['skill_points_remaining']}")
        return

    if change > 0:
        state["skill_points_remaining"] -= cost

    state["skills"][skill] = new_val

    reply = (
        f"{skill} изменён: {current} → {new_val}\n"
        f"Осталось очков прокачки: {state['skill_points_remaining']}\n\n"
        f"Текущие навыки: {', '.join([f'{k}: {v}' for k, v in state['skills'].items()])}"
    )

    # АВТОСЦЕНА, если прокачка последняя
    if state["skill_points_remaining"] == 0:
        reply += "\n\n✨ Очки распределены! Ты чувствуешь, как магия наполняет тебя, и решаешь двинуться дальше…"
        scene = generate_scene(state)
        reply += "\n" + scene

    send_long_message(chat_id, reply)
    save_chat(chat_id)


@bot.message_handler(func=lambda m: True)
def handle_all(message):
    chat_id = message.chat.id
    state = get_state(chat_id)
    text = message.text.lower().strip()

    # --- БРОСКИ КУБИКА ---
    if text in ("кубик", "d20", "dice"):
        roll, bonus, total, res_type, desc = roll_d20(state, "обычный")
        reply = (
            f"🎲 Бросок d20: {roll}\n"
            f"Бонус: 0\n"
            f"Итого: {total}\n"
            f"Результат: {res_type}\n"
            f"{desc}"
        )
        send_long_message(chat_id, reply)
        save_chat(chat_id)
        return

    if text.startswith("кубик ") or text.startswith("d20 "):
        parts = text.split()
        if len(parts) >= 2:
            skill = parts[1]
            roll, bonus, total, res_type, desc = roll_d20(state, skill)
            reply = (
                f"🎲 Бросок d20 ({skill}): {roll}\n"
                f"Бонус (навык + факты): {bonus}\n"
                f"Итого: {total}\n"
                f"Результат: {res_type}\n"
                f"{desc}"
            )
            send_long_message(chat_id, reply)
            save_chat(chat_id)
            return

    # --- СТАНДАРТНЫЕ КОМАНДЫ ---
    elif text == "вперёд":
        state["steps"] += 1
        roll = random.randint(1, 20)
        event = ""
        if roll <= 5:
            state["hp"] -= 1
            state["is_wounded"] = True
            event = "Что-то пошло не так… Ты оступился и ударился."
        elif roll >= 18:
            if state["hp"] < state["max_hp"]:
                state["hp"] += 1
                state["is_wounded"] = False
            event = "Удача на твоей стороне! Ты ловко перепрыгнул опасную трещину."
        scene = generate_scene(state)
        reply = scene
        if event:
            reply += f"\n{event}"
        reply += f"\nHP: {state['hp']}/{state['max_hp']}"
        send_long_message(chat_id, reply)
        save_chat(chat_id)

    elif text in ("факел", "свет"):
        if not state["has_torch"]:
            state["has_torch"] = True
            bot.reply_to(message, "Ты зажёг факел. Пламя дрожит от сквозняка.")
        else:
            bot.reply_to(message, "Факел уже горит.")
        save_chat(chat_id)

    elif text == "память":
        summary = state.get("story_summary", "(пока пусто)")
        facts = "\n".join([f"  {k}: {v}" for k, v in state.get("world_facts", {}).items()])
        if not facts:
            facts = "(пока пусто)"
        events = " | ".join(state.get("world_log", [])[-8:])
        if not events:
            events = "(пока пусто)"
        skills_str = ", ".join([f"{k}: {v}" for k, v in state.get("skills", {}).items()])
        class_name = state.get("class_name", "не выбран")
        points = state.get("skill_points_remaining", 0)

        send_long_message(chat_id,
            f"=== ПАМЯТЬ МАСТЕРА ===\n\n"
            f"Класс: {class_name}\n"
            f"Очки прокачки: {points}\n"
            f"Навыки: {skills_str}\n\n"
            f"Сводка сюжета:\n{summary}\n\n"
            f"Факты мира:\n{facts}\n\n"
            f"События:\n{events}\n\n"
            f"Ход: {state.get('turn_count', 0)}"
        )
        save_chat(chat_id)

    else:
        # Обычный ход игрока
        reply = chat_with_ai(message.text, state)
        send_long_message(chat_id, reply)
        save_chat(chat_id)

print("Бот запущен и готов к приключениям!")
bot.polling(none_stop=True)
