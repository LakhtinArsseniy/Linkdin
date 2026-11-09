import json
import logging
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) "
                  "AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36"
}


def load_channels():
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        config = json.load(file)

    return config["telegram_channels"]


def collect_posts(channel, limit=10):
    url = f"https://t.me/s/{channel}"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )
        response.raise_for_status()
    except requests.RequestException as error:
        logging.error("Не вдалося завантажити @%s: %s", channel, error)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    messages = soup.select(".tgme_widget_message_wrap")

    posts = []

    for message in messages:
        text_element = message.select_one(".tgme_widget_message_text")

        if not text_element:
            continue

        text = text_element.get_text(" ", strip=True)

        if not text:
            continue

        post_element = message.select_one(".tgme_widget_message")
        post_id = post_element.get("data-post", "") if post_element else ""

        if not post_id:
            link = message.select_one(".tgme_widget_message_date")
            href = link.get("href", "") if link else ""
            match = re.search(r"/([^/]+/\d+)$", href)
            post_id = match.group(1) if match else ""

        if not post_id:
            continue

        posts.append({
            "id": post_id,
            "channel": channel,
            "text": text,
            "url": f"https://t.me/{post_id}"
        })

    # Показуємо найновіші пости першими.
    return list(reversed(posts[-limit:]))


def main():
    channels = load_channels()

    for channel in channels:
        logging.info("Збираю пости з @%s", channel)
        posts = collect_posts(channel)

        if not posts:
            print(f"\nДля @{channel} публічних текстових постів не знайдено.")
            continue

        for post in posts:
            print("\n" + "=" * 60)
            print(f"Канал: @{post['channel']}")
            print(f"ID: {post['id']}")
            print(f"Посилання: {post['url']}")
            print(f"Текст: {post['text']}")

        time.sleep(1)


if __name__ == "__main__":
    main()
