"""
АВТОПОСТЕР — ИСПРАВЛЕННАЯ ВЕРСИЯ
"""

import os, sys, subprocess, asyncio, logging, json, re, urllib.request
from datetime import datetime

# Автоустановка библиотек
for pkg in ["python-telegram-bot==20.7"]:
    try:
        __import__("telegram")
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

from telegram import Bot
from telegram.constants import ParseMode

# Настройки
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)


async def main():
    if not BOT_TOKEN:
        log.error("❌ BOT_TOKEN не задан!")
        return
    
    if not CHANNEL_ID:
        log.error("❌ CHANNEL_ID не задан!")
        return
    
    log.info(f"🔑 Токен: {BOT_TOKEN[:20]}...")
    log.info(f" Канал: {CHANNEL_ID}")
    
    bot = Bot(token=BOT_TOKEN)
    
    # ТЕСТ 1: Проверяем, видит ли бот канал
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        log.info(f"✅ Канал найден: {chat.title}")
    except Exception as e:
        log.error(f"❌ Ошибка доступа к каналу: {e}")
        log.error("💡 Проверь: 1) бот добавлен в канал, 2) он администратор")
        return
    
    # ТЕСТ 2: Пробуем отправить тестовое сообщение
    test_text = (
        "🧪 <b>ТЕСТ БОТА</b>\n\n"
        "Если ты видишь это сообщение — бот работает!\n"
        "Скоро здесь начнут появляться новости про ИИ.\n\n"
        f"⏰ Время: {datetime.now().strftime('%H:%M')}"
    )
    
    try:
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text=test_text,
            parse_mode=ParseMode.HTML
        )
        log.info("✅ ТЕСТОВОЕ СООБЩЕНИЕ ОТПРАВЛЕНО!")
    except Exception as e:
        log.error(f"❌ Не удалось отправить сообщение: {e}")
        log.error("💡 Проверь права администратора у бота")
        return
    
    log.info("🎉 Бот работает! Теперь настраиваем RSS...")


if __name__ == "__main__":
    asyncio.run(main())
