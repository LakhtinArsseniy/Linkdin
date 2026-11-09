import os
import time
import random

from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError(
        "Не знайдено GEMINI_API_KEY у файлі .env"
    )

client = genai.Client(api_key=api_key)



def rewrite_post(text: str, source_url: str, language: str = "uk") -> str:
    language_name = {
        "uk": "українською мовою",
        "en": "англійською мовою",
    }.get(language, "українською мовою")

    prompt = f"""
Ти редактор професійної сторінки LinkedIn про кібербезпеку,
штучний інтелект та інформаційні технології.

Перепиши матеріал у форматі професійного LinkedIn-посту.

Вимоги:
- Пиши {language_name}.
- Почни з короткого, цікавого першого рядка.
- Використовуй 1–2 змістовні абзаци.
- Прибери лайку, образи та зайвий рекламний шум.
- Не вигадуй фактів, цифр або цитат.
- Зберігай застереження щодо неперевіреної інформації.
- Додай 3–5 доречних хештегів.
- Наприкінці додай посилання на першоджерело.
- Поверни тільки готовий пост.

Посилання на джерело: {source_url}

Оригінальний матеріал:
{text}
"""

    for attempt in range(3):
        try:
            print(f"Надсилаю запит до Gemini, спроба {attempt + 1}/3...")

            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
            )

            result = (response.text or "").strip()

            if not result:
                raise RuntimeError("Gemini повернув порожню відповідь")

            return result

        except Exception as error:
            error_text = str(error)
            temporary_error = any(
                code in error_text
                for code in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "500", "INTERNAL")
            )

            if not temporary_error or attempt == 2:
                raise

            delay = 2 ** (attempt + 1) + random.uniform(0, 1)
            print(
                f"Gemini тимчасово недоступний. "
                f"Спроба {attempt + 2}/3 через {delay:.1f} с."
            )
            time.sleep(delay)

    raise RuntimeError("Не вдалося отримати відповідь від Gemini")


    if not result:
        raise RuntimeError("Gemini повернув порожню відповідь")

    return result
