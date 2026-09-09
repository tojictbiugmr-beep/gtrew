import telebot
import os
import random
from openai import OpenAI
from memory import (
    load_state, save_state, add_to_history, add_world_event,
    set_world_fact, update_world_fact, remove_world_fact,
    build_memory_context, maybe_summarize, reset_state
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
        {"role": "system", "content": f"Контекст памяти:\n{memory}"},
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

# === МЕХАНИКА БРОСКА D20 ===

def calculate_b
onus(state,
