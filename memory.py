import json
import os

MEMORY_DIR = "memory_data"
os.makedirs(MEMORY_DIR, exist_ok=True)

RECENT_HISTORY_LIMIT = 6
WORLD_LOG_LIMIT = 15
SUMMARY_MAX_CHARS = 600
SUMMARY_EVERY_TURNS = 8
SKILL_POINTS_START = 5

CLASS_STATS = {
    "воин": {"сила": 14, "выносливость": 14, "ловкость": 10, "знание": 8, "восприятие": 10},
    "маг": {"сила": 8, "выносливость": 10, "ловкость": 10, "знание": 14, "восприятие": 12},
    "разбойник": {"сила": 10, "выносливость": 10, "ловкость": 14, "знание": 10, "восприятие": 14},
}

def _path(chat_id):
    return os.path.join(MEMORY_DIR, f"{chat_id}.json")

def _save(chat_id, data):
    path = _path(chat_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[memory] Сохранено: {path}")
    except Exception as e:
        print(f"[memory] Ошибка сохранения: {e}")

def _load(chat_id):
    path = _path(chat_id)
    if not os.path.exists(path):
        print(f"[memory] Файл не найден: {path}")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[memory] Загружено: {path}, facts={len(data.get('world_facts', {}))}")
        return data
    except Exception as e:
        print(f"[memory] Ошибка загрузки: {e}")
        return None

def default_state():
    return {
        "hp": 10,
        "max_hp": 10,
        "has_torch": False,
        "is_wounded": False,
        "steps": 0,
        "in_combat": False,
        "combat_order": [],
        "current_turn": 0,
        "enemies": [],
        "location": "Вход в подземелье",
        "turn_count": 0,
        "chat_history": [],
        "world_log": [],
        "world_facts": {},
        "story_summary": "",
        "class_name": None,
        "skill_points_remaining": SKILL_POINTS_START,
        "skills": {
            "сила": 10,
            "ловкость": 10,
            "выносливость": 10,
            "знание": 10,
            "восприятие": 10
        }
    }

def load_state(chat_id):
    data = _load(chat_id)
    if data is not None:
        default = default_state()
        for key in default:
            if key not in data:
                data[key] = default[key]
        return data
    return default_state()

def save_state(chat_id, state):
    _save(chat_id, state)

def add_to_history(state, role, text):
    state["chat_history"].append({"role": role, "content": text})
    if len(state["chat_history"]) > RECENT_HISTORY_LIMIT:
        old = state["chat_history"].pop(0)
        if old["role"] == "user":
            add_world_event(state, f"Игрок: {old['content'][:80]}")
        else:
            add_world_event(state, f"Мастер: {old['content'][:80]}")

def add_world_event(state, event_text):
    state["world_log"].append(event_text)
    if len(state["world_log"]) > WORLD_LOG_LIMIT:
        state["world_log"] = state["world_log"][-WORLD_LOG_LIMIT:]

def set_world_fact(state, key, value):
    state["world_facts"][key] = value

def update_world_fact(state, key, value):
    state["world_facts"][key] = value

def remove_world_fact(state, key):
    state["world_facts"].pop(key, None)

def build_memory_context(state):
    parts = []
    facts = state.get("world_facts", {})
    if facts:
        facts_str = "\n".join([f"- {k}: {v}" for k, v in facts.items()])
        parts.append(f"ФАКТЫ МИРА:\n{facts_str}")
    summary = state.get("story_summary", "")
    if summary:
        parts.append(f"СВОДКА СЮЖЕТА:\n{summary}")
    log = state.get("world_log", [])
    if log:
        recent = log[-5:]
        parts.append(f"НЕДАВНИЕ СОБЫТИЯ:\n" + " | ".join(recent))
    parts.append(f"ЛОКАЦИЯ: {state.get('location', 'неизвестно')}")
    history = state.get("chat_history", [])
    if history:
        hist_str = "\n".join(
            [f"{'Игрок' if h['role'] == 'user' else 'Мастер'}: {h['content'][:200]}"
             for h in history]
        )
        parts.append(f"ПОСЛЕДНИЙ ДИАЛОГ:\n{hist_str}")
    skills = state.get("skills", {})
    skills_str = ", ".join([f"{k}: {v}" for k, v in skills.items()])
    parts.append(f"НАВЫКИ ГЕРОЯ: {skills_str}")
    return "\n\n".join(parts)

def extract_facts(state, client, model):
    log = state.get("world_log", [])
    history = state.get("chat_history", [])
    existing_facts = state.get("world_facts", {})
    recent_events = " | ".join(log[-10:]) if log else ""
    recent_dialog = "\n".join(
        [f"{'И' if h['role'] == 'user' else 'М'}: {h['content'][:150]}"
         for h in history]
    ) if history else ""
    existing_str = "; ".join([f"{k}: {v}" for k, v in existing_facts.items()])

    if not recent_events and not recent_dialog:
        return

    prompt = (
        "Ты - архивариус игрового мира. Извлеки ТОЛЬКО новые устойчивые факты: имена NPC, места, предметы, договорённости, ключевые решения. "
        "НЕ выдумывай. НЕ дублируй уже известные. Формат — JSON-объект {\"Ключ\": \"Значение\"}. Если новых нет — верни {}.\n\n"
        f"УЖЕ ИЗВЕСТНЫЕ ФАКТЫ:\n{existing_str}\n\n"
        f"СОБЫТИЯ:\n{recent_events}\n{recent_dialog}\n\n"
        "НОВЫЕ ФАКТЫ (JSON):"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.2
        )
        raw = response.choices[0].message.content.strip()
        if "{" in raw:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            raw = raw[start:end]
        new_facts = json.loads(raw)
        for key, value in new_facts.items():
            state["world_facts"][key] = value
    except Exception:
        pass

def maybe_summarize(state, client, model):
    if state["turn_count"] % SUMMARY_EVERY_TURNS != 0 or state["turn_count"] == 0:
        return
    log = state.get("world_log", [])
    if len(log) < 5:
        return
    extract_facts(state, client, model)
    old_summary = state.get("story_summary", "")
    recent_events = " | ".join(log[-10:])
    history_str = "\n".join(
        [f"{'И' if h['role'] == 'user' else 'М'}: {h['content'][:150]}"
         for h in state.get("chat_history", [])]
    )
    prompt = (
        "Сожми историю приключения в ОДИН абзац (до 500 символов). Опиши ТЕКУЩУЮ ситуацию и куда движется сюжет. "
        "Не перечисляй факты о мире отдельно. Пиши на русском.\n\n"
        f"ПРЕДЫДУЩАЯ СВОДКА:\n{old_summary}\n\n"
        f"НОВЫЕ СОБЫТИЯ:\n{recent_events}\n{history_str}\n\n"
        "НОВАЯ СВОДКА:"
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3
        )
        new_summary = response.choices[0].message.content.strip()
        if len(new_summary) > SUMMARY_MAX_CHARS:
            new_summary = new_summary[:SUMMARY_MAX_CHARS] + "..."
        state["story_summary"] = new_summary
        if len(state["world_log"]) > 5:
            state["world_log"] = state["world_log"][-5:]
    except Exception:
        pass

def reset_state(chat_id):
    path = _path(chat_id)
    if os.path.exists(path):
        os.remove(path)
    state = default_state()
    set_world_fact(state, "Подземелье", "древние руины под заброшенным замком")
    set_world_fact(state, "Цель", "найти источник тьмы в глубинах")
    add_world_event(state, "Герой вошёл в подземелье")
    _save(chat_id, state)
    return state
