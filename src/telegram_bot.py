import os
import logging
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from database import (
    get_draft,
    save_draft,
    update_draft_status,
    get_last_published_at,
    save_last_published_at,
)
from rewriter import rewrite_post
from linkedin_client import publish_text_post

# Завантаження .env
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OWNER_ID = int(os.getenv("TELEGRAM_OWNER_ID", "0"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Клавіатура чернетки
def draft_keyboard(draft_id):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Схвалити",
                callback_data=f"approve:{draft_id}",
            ),
            InlineKeyboardButton(
                "❌ Відхилити",
                callback_data=f"reject:{draft_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔄 Переписати",
                callback_data=f"rewrite:{draft_id}",
            ),
        ],
    ])


# Команда /start
async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "Привіт! Я бот для підготовки LinkedIn-публікацій.\n\n"
        "Команди:\n"
        "/testdraft — створити тестову чернетку."
    )


# Команда /testdraft
async def testdraft(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Немає доступу.")
        return

    text = (
        "Кібербезпека починається з простих звичок.\n\n"
        "Регулярні оновлення програмного забезпечення, "
        "багатофакторна автентифікація та контроль доступу "
        "допомагають зменшити ризики для бізнесу.\n\n"
        "#Кібербезпека #CyberSecurity #Technology"
    )

    source_url = "https://example.com/test-source"

    draft_id = save_draft(text, source_url)

    await update.message.reply_text(
        f"📝 Тестова чернетка №{draft_id}\n\n"
        f"{text}\n\n"
        f"Джерело: {source_url}\n\n",
        reply_markup=draft_keyboard(draft_id),
    )


# Обробка кнопок
async def handle_button(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if query.from_user.id != OWNER_ID:
        await query.answer(
            "⛔ Немає доступу.",
            show_alert=True,
        )
        return

    await query.answer()

    try:
        action, draft_id_text = query.data.split(":", 1)
        draft_id = int(draft_id_text)
    except (ValueError, AttributeError):
        await query.message.reply_text("❌ Некоректна команда.")
        return

    draft = get_draft(draft_id)

    if draft is None:
        await query.message.reply_text("Чернетку не знайдено.")
        return

    if draft["status"] != "pending":
        await query.message.reply_text(
            "Цю чернетку вже опрацьовано."
        )
        return

    
    if action == "approve":
        # Перевіряємо інтервал між публікаціями
        last_published = get_last_published_at()

        if last_published:
            last_time = datetime.fromisoformat(last_published)
            now = datetime.now(timezone.utc)
            next_allowed = last_time + timedelta(days=3)

            if now < next_allowed:
                remaining = next_allowed - now
                hours = int(remaining.total_seconds() // 3600)
                days = hours // 24
                hours = hours % 24

                await query.message.reply_text(
                    f"⏳ Наступна публікація буде доступна "
                    f"через {days} дн. {hours} год.\n"
                    "Чернетка залишилася очікувати підтвердження."
                )
                return

        # Захист від повторного підтвердження
        if not update_draft_status(draft_id, "publishing"):
            await query.message.reply_text(
                "Цю чернетку вже опрацьовують."
            )
            return

        await query.edit_message_reply_markup(reply_markup=None)

        status_message = await query.message.reply_text(
            "⏳ Публікую допис у LinkedIn..."
        )

        try:
            result = await asyncio.to_thread(
                publish_text_post,
                draft["text"],
            )

            # Зберігаємо час лише після успішної публікації
            save_last_published_at()
            update_draft_status(draft_id, "published")

            message = "✅ Допис успішно опубліковано в LinkedIn!"

            if result.get("url"):
                message += f"\n\nПосилання: {result['url']}"

            await status_message.edit_text(message)

        except Exception:
            logging.exception(
                "Помилка публікації чернетки №%s",
                draft_id,
            )

            update_draft_status(draft_id, "pending")

            await status_message.edit_text(
                "❌ Не вдалося опублікувати допис.\n"
                "Чернетку повернуто до очікування. "
                "Перевір помилку в терміналі."
            )

    # Відхилення
    elif action == "reject":
        update_draft_status(draft_id, "rejected")

        await query.edit_message_reply_markup(
            reply_markup=None
        )

        await query.message.reply_text(
            "❌ Чернетку відхилено."
        )

    # Переписування через Gemini
    elif action == "rewrite":
        update_draft_status(draft_id, "rewrite_requested")

        await query.edit_message_reply_markup(
            reply_markup=None
        )

        status_message = await query.message.reply_text(
            "🔄 Переписую допис через Gemini. Зачекай..."
        )

        try:
            new_text = await asyncio.to_thread(
                rewrite_post,
                draft["text"],
                draft["source_url"],
                "uk",
            )

            if not new_text or not new_text.strip():
                raise ValueError(
                    "Gemini повернув порожній текст."
                )

            new_draft_id = save_draft(
                new_text,
                draft["source_url"],
            )

            await status_message.edit_text(
                "✅ Нову версію створено!"
            )

            await query.message.reply_text(
                f"📝 Нова версія чернетки №{new_draft_id}\n\n"
                f"{new_text}\n\n"
                f"Джерело: {draft['source_url']}\n\n"
                "Вибери дію:",
                reply_markup=draft_keyboard(new_draft_id),
            )

        except Exception:
            logging.exception(
                "Помилка під час переписування чернетки №%s",
                draft_id,
            )

            await status_message.edit_text(
                "❌ Не вдалося переписати допис. "
                "Спробуй пізніше."
            )

    else:
        await query.message.reply_text("Невідома дія.")



# Надсилання чернетки власнику
async def send_draft_message(
    context,
    draft_id,
    text,
    source_url,
):
    await context.bot.send_message(
        chat_id=OWNER_ID,
        text=(
            f"📝 Чернетка №{draft_id}\n\n"
            f"{text}\n\n"
            f"Джерело: {source_url}\n\n"
            "Вибери дію:"
        ),
        reply_markup=draft_keyboard(draft_id),
    )


# Синхронне надсилання для main.py
def send_draft_to_owner(text, source_url):
    if not TOKEN:
        raise RuntimeError(
            "Не задано TELEGRAM_BOT_TOKEN у .env"
        )

    if OWNER_ID == 0:
        raise RuntimeError(
            "Вкажи TELEGRAM_OWNER_ID у .env"
        )

    draft_id = save_draft(text, source_url)

    async def send():
        from telegram import Bot

        async with Bot(token=TOKEN) as bot:
            await bot.send_message(
                chat_id=OWNER_ID,
                text=(
                    f"📝 Чернетка №{draft_id}\n\n"
                    f"{text}\n\n"
                    f"Джерело: {source_url}\n\n"
                    "Вибери дію:"
                ),
                reply_markup=draft_keyboard(draft_id),
            )

    try:
        asyncio.run(send())
        return draft_id
    except Exception:
        logging.exception(
            "Не вдалося надіслати чернетку в Telegram."
        )
        raise


# Запуск бота
def main():
    if not TOKEN:
        raise RuntimeError(
            "Не задано TELEGRAM_BOT_TOKEN у .env"
        )

    if OWNER_ID == 0:
        raise RuntimeError(
            "Вкажи TELEGRAM_OWNER_ID у .env"
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("testdraft", testdraft)
    )

    app.add_handler(
        CallbackQueryHandler(handle_button)
    )

    print("Telegram-бот запущено.")

    app.run_polling()


if __name__ == "__main__":
    main()
