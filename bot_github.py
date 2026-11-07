"""
АВТОПОСТЕР НОВОСТЕЙ С ПАМЯТЬЮ (не постит дубликаты)
"""

import os, sys, subprocess, asyncio, logging, re, json, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

# Автоустановка библиотек
for pkg in ["feedparser==6.0.11", "python-telegram-bot==20.7"]:
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
HOURS_AGO = 48  # Берем новости за последние 48 часов

RU_FEEDS = [
    ("Хабр: ИИ", "https://habr.com/ru/hub/artificial_intelligence/rss/"),
    ("Хабр: Нейросети", "https://habr.com/ru/hub/neural_networks/rss/"),
    ("Хабр: Machine Learning", "https://habr.com/ru/hub/machine_learning/rss/"),
    ("Naked Science", "https://naked-science.ru/feed"),
]

EN_FEEDS = [
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
]

SIGNATURE = "\n\n🤖 Подписывайся: @newschanelll"

# Файл с памятью о posted новостях
POSTED_FILE = "posted_news.json"
MAX_POSTED_LINKS = 200  # Храним последние 200 ссылок

def load_posted_links():
    """Загружает список отправленных ссылок."""
    try:
        # Пытаемся скачать файл из репозитория
        import urllib.request
        url = "https://raw.githubusercontent.com/rafaello1988-source/main/posted_news.json"
        req = urllib.request.Request(url, headers={"User-Agent": "NewsBot/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            links = data.get("posted_links", [])
            log.info(f"📚 Загружено {len(links)} отправленных ссылок")
            return links
    except Exception as e:
        log.warning(f"⚠️ Не удалось загрузить posted_news.json: {e}")
        return []

def clean_html(text):
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', text).strip()
    return re.sub(r'\s+', ' ', text)

def translate_to_ru(text):
    if not text:
        return ""
    try:
        url = "https://api.mymemory.translated.net/get"
        params = urllib.parse.urlencode({
            "q": text[:500],
            "langpair": "en|ru"
        })
        req = urllib.request.Request(f"{url}?{params}", headers={"User-Agent": "NewsBot/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            translated = data.get("responseData", {}).get("translatedText", "")
            return translated if translated else text
    except Exception as e:
        log.warning(f"⚠️ Ошибка перевода: {e}")
        return text

def format_post(title, summary, link, source, is_translated=False):
    text = f"🔹 <b>{title}</b>\n\n"
    if summary:
        summary = summary[:300]
        last_dot = summary.rfind('.')
        if last_dot > 100:
            summary = summary[:last_dot+1]
        else:
            summary += "..."
        text += f"{summary}\n\n"
    
    if link:
        text += f"🔗 <a href=\"{link}\">Читать полностью</a>\n"
    
    if is_translated:
        text += f" <i>Источник: {source} (перевод)</i>"
    else:
        text += f"📰 <i>Источник: {source}</i>"
        
    text += SIGNATURE
    return text

async def main():
    if not BOT_TOKEN or not CHANNEL_ID:
        log.error("❌ Не задан токен или ID канала!")
        return

    bot = Bot(token=BOT_TOKEN)
    posted_links = load_posted_links()  # Загружаем память
    all_news = []

    log.info(" Собираю русскоязычные новости...")
    for source_name, url in RU_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                # Проверяем время
                published = entry.get('published_parsed')
                if published:
                    pub_date = datetime(*published[:6], tzinfo=timezone.utc)
                    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=HOURS_AGO)
                    if pub_date < cutoff_time:
                        continue

                title = clean_html(entry.get('title', ''))
                summary = clean_html(entry.get('summary', ''))
                link = entry.get('link', '')
                
                # ПРОВЕРКА: не отправляли ли уже эту новость?
                if link in posted_links:
                    log.info(f"⏭️ Пропускаю (уже отправлено): {title[:50]}")
                    continue
                
                if title and link:
                    all_news.append({
                        "title": title,
                        "summary": summary,
                        "link": link,
                        "source": source_name,
                        "translated": False,
                        "priority": 1
                    })
        except Exception as e:
            log.warning(f"⚠️ Ошибка {source_name}: {e}")

    log.info(f"✅ Найдено {len(all_news)} новых русских новостей")

    log.info(" Собираю англоязычные новости (с переводом)...")
    for source_name, url in EN_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                published = entry.get('published_parsed')
                if published:
                    pub_date = datetime(*published[:6], tzinfo=timezone.utc)
                    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=HOURS_AGO)
                    if pub_date < cutoff_time:
                        continue

                title_en = clean_html(entry.get('title', ''))
                summary_en = clean_html(entry.get('summary', ''))
                link = entry.get('link', '')
                
                # ПРОВЕРКА: не отправляли ли уже?
                if link in posted_links:
                    log.info(f"️ Пропускаю (уже отправлено): {title_en[:50]}")
                    continue
                
                if title_en and link:
                    title_ru = translate_to_ru(title_en)
                    summary_ru = translate_to_ru(summary_en) if summary_en else ""
                    
                    all_news.append({
                        "title": title_ru,
                        "summary": summary_ru,
                        "link": link,
                        "source": source_name,
                        "translated": True,
                        "priority": 2
                    })
        except Exception as e:
            log.warning(f"⚠️ Ошибка {source_name}: {e}")

    if not all_news:
        log.info("ℹ️ Новых новостей не найдено. Пропуск.")
        return

    all_news.sort(key=lambda x: x["priority"])
    posts_to_publish = all_news[:POSTS_PER_RUN]
    log.info(f" Публикую {len(posts_to_publish)} новостей...")

    new_posted_links = posted_links.copy()

    for i, item in enumerate(posts_to_publish):
        text = format_post(item["title"], item["summary"], item["link"], item["source"], item["translated"])
        try:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False
            )
            # Добавляем ссылку в память
            new_posted_links.append(item["link"])
            # Оставляем только последние MAX_POSTED_LINKS
            if len(new_posted_links) > MAX_POSTED_LINKS:
                new_posted_links = new_posted_links[-MAX_POSTED_LINKS:]
                
            lang = "🇷🇺" if not item["translated"] else "🇬→🇷🇺"
            log.info(f"✅ Пост {i+1}/{len(posts_to_publish)} {lang}: {item['title'][:40]}...")
            
            if i < len(posts_to_publish) - 1:
                await asyncio.sleep(3)
        except Exception as e:
            log.error(f"❌ Ошибка отправки поста {i+1}: {e}")

    log.info("🎉 Готово! Бот завершил работу.")

if __name__ == "__main__":
    asyncio.run(main())
