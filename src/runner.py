import subprocess
import sys
import time

telegram_bot = subprocess.Popen(
    [sys.executable, "src/telegram_bot.py"]
)

try:
    from main import run_scheduler

    run_scheduler()

except KeyboardInterrupt:
    print("Зупинка сервісу...")

finally:
    telegram_bot.terminate()

    try:
        telegram_bot.wait(timeout=10)
    except subprocess.TimeoutExpired:
        telegram_bot.kill()