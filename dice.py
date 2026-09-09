import random
from openai import OpenAI

# === Модель для определения необходимости броска ===
MODEL = "groq/compound-mini"

# === Пороги результатов ===
THRESHOLDS = {
    "critical_success": 20,
    "success": 15,
    "partial": 10
}

# === Ситуативные модификаторы (факты мира) ===
FACT_MODIFIERS = {
    "знание": {
        "Древний_пергамент": 2,
        "Кристалл_холодный_свет": 1
    },
    "ловкость": {
        "Холодный_ветер_в_зале": -1
    }
}

# === Сопоставление русских навыков с действиями ===
SKILL_ALIASES = {
    "сила": ["сила", "толкать", "ломать", "удар", "поднять", "тащить", "форсировать"],
    "ловкость": ["ловкость", "уклониться", "прыгнуть", "взломать", "прокрасться", "балансировать", "пробраться"],
    "выносливость": ["выносливость", "устоять", "пережить", "противостоять", "сопротивляться"],
    "знание": ["знание", "изучить", "осмотреть", "прочитать", "расшифровать", "понять", "исследовать", "анализ"],
    "восприятие": ["восприятие", "заметить", "найти", "обнаружить", "прислушаться", "принюхаться", "поиск"]
}

# === Ключевые слова, указывающие на рискованное действие ===
RISK_KEYWORDS = [
    "прыгнуть", "перепрыгнуть", "перебраться", "пробраться", "взломать",
    "толкнуть", "сломать", "форсировать", "поднять", "тащить",
    "атаковать", "убить", "сразиться", "уклониться", "блокировать",
    "перейти", "мост", "пропасть", "обрыв", "обвал", "ловушка",
    "проползти", "карабкаться", "взобраться", "спуститься",
    "открыть", "разблокировать", "взлом", "подобрать замок",
    "осмотреть", "изучить", "исследовать", "найти", "обнаружить",
    "прочитать", "расшифровать", "понять",
    "устоять", "сопротивляться", "пережить"
]


def determine_skill(action_text):
    """Определяет нужный навык по тексту действия."""
    text = action_text.lower()
    for skill, aliases in SKILL_ALIASES.items():
        if any(alias in text for alias in aliases):
            return skill
    return None


def is_risky_action(action_text):
    """Быстрая проверка: содержит ли действие рискованные ключевые слова."""
    text = action_text.lower()
    return any(keyword in text for keyword in RISK_KEYWORDS)


def calculate_bonus(state, skill_type):
    """Бонус = навык героя (отклонение от 10) + ситуативные модификаторы из фактов мира."""
    bonus = 0
    skills = state.get("skills", {})

    if skill_type in skills:
        bonus += skills[skill_type] - 10

    facts = state.get("world_facts", {})
    modifiers = FACT_MODIFIERS.get(skill_type, {})
    for fact_key, mod_value in modifiers.items():
        if fact_key in facts:
            bonus += mod_value

    return bonus


def roll_d20(state, skill_type="обычный"):
    """Бросок d20 с бонусами и определением результата."""
    roll = random.randint(1, 20)
    bonus = calculate_bonus(state, skill_type) if skill_type != "обычный" else 0
    total = roll + bonus

    if roll == 20:
        result_type = "КРИТИЧЕСКИЙ УСПЕХ"
        description = "Судьба благоволит тебе: даже если обстоятельства против, твой поступок выходит за рамки обычного."
    elif roll == 1:
        result_type = "КРИТИЧЕСКАЯ НЕУДАЧА"
        description = "Всё идёт не так: ты теряешь равновесие, инструмент ломается, или звук разносится по коридору, привлекая внимание."
    elif total >= THRESHOLDS["success"]:
        result_type = "УСПЕХ"
        description = "Тебе удаётся задуманное, хотя и не без усилий."
    elif total >= THRESHOLDS["partial"]:
        result_type = "ПОГРАНИЧНЫЙ РЕЗУЛЬТАТ"
        description = "Ты почти справляешься, но что-то идёт не совсем так, как хотелось."
    else:
        result_type = "НЕУДАЧА"
        description = "К сожалению, попытка не удалась. Возможно, стоит попробовать другой подход."

    return {
        "roll": roll,
        "bonus": bonus,
        "total": total,
        "result_type": result_type,
        "description": description,
        "skill_type": skill_type
    }


def format_roll_result(result):
    """Форматирует результат броска для отправки игроку."""
    skill_str = f" ({result['skill_type']})" if result["skill_type"] != "обычный" else ""
    return (
        f"🎲 Бросок d20{skill_str}: {result['roll']}\n"
        f"Бонус: {result['bonus']}\n"
        f"Итого: {result['total']}\n"
        f"Результат: {result['result_type']}\n"
        f"{result['description']}"
    )


def check_action(action_text, state, client, model=MODEL):
    """
    Определяет через ИИ, нужен ли бросок кубика для действия игрока.
    Возвращает None если бросок не нужен, или dict с результатом броска.
    """
    # Быстрый фильтр по ключевым словам
    if not is_risky_action(action_text):
        return None

    # ИИ-запрос: определить, нужен ли бросок и какой навык
    facts = state.get("world_facts", {})
    facts_str = "; ".join([f"{k}: {v}" for k, v in facts.items()])
    summary = state.get("story_summary", "")
    skills = state.get("skills", {})
    skills_str = ", ".join([f"{k}: {v}" for k, v in skills.items()])

    prompt = (
        "Ты — судья в D&D-подобной игре. Игрок описывает действие. "
        "Определи, нужен ли бросок кубика (проверка навыка).\n\n"
        "Правила:\n"
        "- Бросок НУЖЕН при риске, опасности, неопределённости, физическом усилии, осмотре с поиском скрытого.\n"
        "- Бросок НЕ НУЖЕН при обычном перемещении, простом диалоге, безобидных действиях без риска.\n"
        "- Если бросок нужен — выбери ОДИН навык из: сила, ловкость, выносливость, знание, восприятие.\n\n"
        "Ответ строго в формате JSON:\n"
        '{"need_roll": true, "skill": "ловкость", "difficulty": 15, "reason": "прыжок через пропасть"}\n'
        'или {"need_roll": false, "reason": "обычное движение"}\n\n'
        f"Контекст мира:\nСводка: {summary}\nФакты: {facts_str}\nНавыки: {skills_str}\n\n"
        f"Действие игрока: {action_text}\n\n"
        "Ответ (JSON):"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.2
        )
        raw = response.choices[0].message.content.strip()

        import json
        if "{" in raw:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            raw = raw[start:end]
        decision = json.loads(raw)

        if not decision.get("need_roll", False):
            return None

        skill = decision.get("skill", "восприятие")
        if skill not in ["сила", "ловкость", "выносливость", "знание", "восприятие"]:
            skill = "восприятие"

        difficulty = decision.get("difficulty", 10)
        reason = decision.get("reason", "")

        result = roll_d20(state, skill)
        result["difficulty"] = difficulty
        result["reason"] = reason

        return result

    except Exception:
        # Если ИИ не ответил — пробуем определить навык по ключевым словам
        skill = determine_skill(action_text)
        if skill is None:
            return None
        result = roll_d20(state, skill)
        result["difficulty"] = 10
        result["reason"] = ""
        return result
