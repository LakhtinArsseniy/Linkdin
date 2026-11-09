import logging
import sys
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from collector import collect_posts
from database import (
    init_db,
    save_post,
    get_new_posts,
    update_post_status,
)
from rewriter import rewrite_post
from telegram_bot import send_draft_to_owner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

BASE_DIR = SRC_DIR.parent
CONFIG_PATH = BASE_DIR / "config.json"


def load_config():
    import json

    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        return json.load(file)




def collect_new_posts(config):
    total_new = 0

    channels = config.get("telegram_channels", [])

    for channel in channels:
        channel = channel.lstrip("@")
        logging.info("Перевіряємо канал: %s", channel)

        try:
            posts = collect_posts(channel, limit=10)

            for post in posts:
                if save_post(post):
                    total_new += 1
                    logging.info(
                        "Збережено новий допис: %s",
                        post["url"],
                    )

        except Exception:
            logging.exception(
                "Помилка під час збору каналу %s",
                channel,
            )

    logging.info("Усього збережено нових дописів: %s", total_new)
    return total_new



def process_new_posts():
    config = load_config()
    init_db()

    new_count = collect_new_posts(config)
    logging.info("Нових дописів у цій перевірці: %s", new_count)
    posts = get_new_posts(limit=3)

    for post in posts:
        try:
            logging.info("Переробляємо допис: %s", post["source_url"])

            rewritten = rewrite_post(
                post["original_text"],
                post["source_url"],
                language="uk",
            )

            if not rewritten or not rewritten.strip():
                logging.warning("Gemini повернув порожній текст.")
                continue

            draft_id = send_draft_to_owner(
                text=rewritten,
                source_url=post["source_url"],
            )

            if draft_id:
                update_post_status(post["source_id"], "drafted")

                logging.info(
                    "Чернетку №%s надіслано на погодження.",
                    draft_id,
                )
        except Exception:
            logging.exception(
                "Не вдалося обробити допис із джерела %s",
                post["source_url"],
            )

def run_scheduler():
    logging.info("🚀 Планувальник запущено.")
    logging.info("Перевірка Telegram-каналів кожні 6 годин.")

    while True:
        try:
            process_new_posts()
        except Exception:
            logging.exception("Помилка автоматичної перевірки.")

        logging.info("Наступна перевірка через 6 годин.")
        time.sleep(6 * 60 * 60)


if __name__ == "__main__":
    run_scheduler()
