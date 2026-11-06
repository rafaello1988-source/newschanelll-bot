"""
ФИНАЛЬНЫЙ АВТОПОСТЕР НОВОСТЕЙ ПРО ИИ НА РУССКОМ
С переводом английских новостей и приоритетом русских источников.
"""

import os, sys, subprocess, asyncio, logging, re, json, urllib.request, urllib.parse

# Автоустановка библиотек
for pkg in ["feedparser==6.0.11"]:
    try:
        import feedparser
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])
        import feedparser

from telegram import Bot
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# === НАСТРОЙКИ ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
POSTS_PER_RUN = 3

# Русскоязычные источники (приоритетные — без перевода)
RU_FEEDS = [
    ("Хабр: ИИ", "https://habr.com/ru/hub/artificial_intelligence/rss/"),
    ("Хабр: Нейросети", "https://habr.com/ru/hub/neural_networks/rss/"),
    ("Хабр: Machine Learning", "https://habr.com/ru/hub/machine_learning/rss/"),
    ("Naked Science", "https://naked-science.ru/feed"),
]

# Англоязычные источники (будем переводить)
EN_FEEDS = [
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
]

SIGNATURE = "\n\n🤖 Подписывайся: @newschanelll"


def clean_html(text):
    """Удаляет HTML-теги."""
    return re.sub(r'<[^>]+>', '', text).strip()


def translate_to_ru(text):
    """Бесплатный перевод через MyMemory API (без ключа, до 5000 слов/день)."""
    if not text:
        return ""
    try:
        url = "https://api.mymemory.translated.net/get"
        params = urllib.parse.urlencode({
            "q": text[:500],
            "langpair": "en|ru"
        })
        req = urllib.request.Request(
            f"{url}?{params}",
            headers={"User-Agent": "NewsBot/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            translated = data.get("responseData", {}).get("translatedText", "")
            return translated if translated else text
    except Exception as e:
        log.warning(f"⚠️ Ошибка перевода: {e}")
        return text


def format_post(title, summary, link, source, is_translated=False):
    """Форматирует пост для Telegram."""
    text = f"🔹 <b>{title}</b>\n\n"
    if summary:
        # Обрезаем до 300 символов
        text += f"{summary[:300]}...\n\n"
    if link:
        text += f"🔗 <a href=\"{link}\">Читать полностью</a>\n"
    if is_translated:
        text += f"📰 <i>Источник: {source} (перевод)</i>"
    else:
        text += f"📰 <i>Источник: {source}</i>"
    text += SIGNATURE
    return text


async def main():
    if not BOT_TOKEN or not CHANNEL_ID:
        log.error("❌ Не задан токен или ID канала!")
        return

    bot = Bot(token=BOT_TOKEN)
    all_news = []

    # 1. Сначала собираем русскоязычные новости (без перевода)
    log.info("📡 Собираю русскоязычные новости...")
    for source_name, url in RU_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                title = clean_html(entry.get('title', ''))
                summary = clean_html(entry.get('summary', ''))
                link = entry.get('link', '')
                
                if title and link:
                    all_news.append({
                        "title": title,
                        "summary": summary,
                        "link": link,
                        "source": source_name,
                        "translated": False,
                        "priority": 1  # Высокий приоритет
                    })
        except Exception as e:
            log.warning(f"⚠️ Ошибка {source_name}: {e}")

    log.info(f"✅ Найдено {len(all_news)} русских новостей")

    # 2. Потом собираем англоязычные (с переводом)
    log.info("📡 Собираю англоязычные новости (с переводом)...")
    for source_name, url in EN_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                title_en = clean_html(entry.get('title', ''))
                summary_en = clean_html(entry.get('summary', ''))
                link = entry.get('link', '')
                
                if title_en and link:
                    # Переводим заголовок и описание
                    title_ru = translate_to_ru(title_en)
                    summary_ru = translate_to_ru(summary_en) if summary_en else ""
                    
                    all_news.append({
                        "title": title_ru,
                        "summary": summary_ru,
                        "link": link,
                        "source": source_name,
                        "translated": True,
                        "priority": 2  # Меньший приоритет
                    })
        except Exception as e:
            log.warning(f"⚠️ Ошибка {source_name}: {e}")

    if not all_news:
        log.error("❌ Не удалось получить новости ни из одного источника!")
        return

    # 3. Сортируем: сначала русские, потом переведённые
    all_news.sort(key=lambda x: x["priority"])

    # 4. Публикуем
    posts_to_publish = all_news[:POSTS_PER_RUN]
    log.info(f"📝 Публикую {len(posts_to_publish)} новостей...")

    for i, item in enumerate(posts_to_publish):
        text = format_post(
            item["title"], 
            item["summary"], 
            item["link"], 
            item["source"],
            item["translated"]
        )
        try:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False
            )
            lang = "🇷🇺" if not item["translated"] else "🇬🇧→🇷🇺"
            log.info(f"✅ Пост {i+1}/{len(posts_to_publish)} {lang}: {item['title'][:40]}...")
            
            # Пауза 3 секунды между постами
            if i < len(posts_to_publish) - 1:
                await asyncio.sleep(3)
        except Exception as e:
            log.error(f"❌ Ошибка отправки поста {i+1}: {e}")

    log.info("🎉 Готово! Бот завершил работу.")


if __name__ == "__main__":
    asyncio.run(main())
