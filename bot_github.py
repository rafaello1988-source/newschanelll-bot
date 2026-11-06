"""
ФИНАЛЬНЫЙ АВТОПОСТЕР НОВОСТЕЙ ПРО ИИ
Запускается по расписанию, публикует 3 свежие новости.
"""

import os, sys, subprocess, asyncio, logging, re, time

# Автоустановка библиотеки для чтения RSS
try:
    import feedparser
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "feedparser", "-q"])
    import feedparser

from telegram import Bot
from telegram.constants import ParseMode
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# === НАСТРОЙКИ ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
POSTS_PER_RUN = 3  # Количество постов за один запуск

# Источники новостей (RSS)
RSS_FEEDS = [
    ("Хабр: ИИ", "https://habr.com/ru/hub/artificial_intelligence/rss/"),
    ("Хабр: Нейросети", "https://habr.com/ru/hub/neural_networks/rss/"),
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
]

SIGNATURE = "\n\n🤖 Подписывайся: @newschanelll"

def clean_html(text):
    return re.sub(r'<[^>]+>', '', text).strip()

def format_post(title, summary, link, source):
    text = f"🔹 <b>{title}</b>\n\n"
    if summary:
        text += f"{summary[:300]}...\n\n"
    if link:
        text += f"🔗 <a href=\"{link}\">Читать полностью</a>\n"
    text += f"📰 <i>Источник: {source}</i>{SIGNATURE}"
    return text

async def main():
    if not BOT_TOKEN or not CHANNEL_ID:
        log.error("❌ Не задан токен или ID канала!")
        return

    bot = Bot(token=BOT_TOKEN)
    all_news = []

    # 1. Собираем новости из всех лент
    for source_name, url in RSS_FEEDS:
        log.info(f"📡 Проверяю ленту: {source_name}")
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]: # Берем по 5 последних из каждой ленты
                title = clean_html(entry.get('title', ''))
                summary = clean_html(entry.get('summary', ''))
                link = entry.get('link', '')
                
                if title and link:
                    all_news.append({
                        "title": title,
                        "summary": summary,
                        "link": link,
                        "source": source_name
                    })
        except Exception as e:
            log.warning(f"⚠️ Ошибка чтения {source_name}: {e}")

    if not all_news:
        log.error("❌ Не удалось получить новости. Проверьте RSS-ссылки.")
        return

    # 2. Публикуем последние новости (берем самые свежие)
    posts_to_publish = all_news[:POSTS_PER_RUN]
    log.info(f"📝 Найдено {len(all_news)} новостей. Публикую {len(posts_to_publish)}...")

    for i, item in enumerate(posts_to_publish):
        text = format_post(item["title"], item["summary"], item["link"], item["source"])
        try:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False
            )
            log.info(f"✅ Пост {i+1}/{len(posts_to_publish)} отправлен: {item['title'][:40]}...")
            # Пауза 3 секунды между постами, чтобы Telegram не заблокировал за спам
            if i < len(posts_to_publish) - 1:
                await asyncio.sleep(3)
        except Exception as e:
            log.error(f"❌ Ошибка отправки поста {i+1}: {e}")

    log.info("🎉 Готово! Бот завершил работу.")

if __name__ == "__main__":
    asyncio.run(main())
