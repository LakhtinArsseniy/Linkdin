
import os
import logging
from pathlib import Path

import requests
from dotenv import load_dotenv

# Завантаження налаштувань
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN")

USER_INFO_URL = "https://api.linkedin.com/v2/userinfo"


def get_member_profile():
    """Отримує інформацію про авторизований LinkedIn-профіль."""

    if not ACCESS_TOKEN:
        raise RuntimeError(
            "Не знайдено LINKEDIN_ACCESS_TOKEN у .env"
        )

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
    }

    response = requests.get(
        USER_INFO_URL,
        headers=headers,
        timeout=30,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Помилка LinkedIn API: "
            f"{response.status_code} — {response.text}"
        )

    profile = response.json()

    if not profile.get("sub"):
        raise RuntimeError(
            "LinkedIn не повернув ідентифікатор профілю."
        )

    return profile


def check_linkedin_connection():
    """Перевіряє підключення до LinkedIn."""

    profile = get_member_profile()

    print("✅ LinkedIn успішно підключено!")
    print(f"Ім'я профілю: {profile.get('name', 'Не вказано')}")
    print("Ідентифікатор профілю отримано.")
    
    return profile


if __name__ == "__main__":
    try:
        check_linkedin_connection()
    except Exception:
        logging.exception("Не вдалося підключитися до LinkedIn.")


def publish_text_post(text: str) -> dict:
    """Публікує текстовий допис від імені авторизованого користувача."""

    if not text or not text.strip():
        raise ValueError("Текст допису не може бути порожнім.")

    # Отримуємо ID авторизованого користувача
    profile = get_member_profile()
    member_id = profile.get("sub")

    if not member_id:
        raise RuntimeError("Не вдалося отримати LinkedIn member ID.")

    author = f"urn:li:person:{member_id}"

    url = "https://api.linkedin.com/rest/posts"

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
        "Linkedin-Version": os.getenv("LINKEDIN_VERSION", "202610"),
    }

    payload = {
        "author": author,
        "commentary": text.strip(),
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30,
    )

    if response.status_code != 201:
        raise RuntimeError(
            f"LinkedIn API error {response.status_code}: {response.text}"
        )

    post_id = response.headers.get("x-restli-id")

    return {
        "success": True,
        "post_id": post_id,
        "url": (
            f"https://www.linkedin.com/feed/update/{post_id}/"
            if post_id else None
        ),
    }
