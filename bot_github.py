"""
АВТОПОСТЕР НОВОСТЕЙ С ПАМЯТЬЮ + РАСШИРЕННЫЕ ИСТОЧНИКИ
"""

import os, sys, subprocess, asyncio, logging, re, json, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone
import feedparser
from telegram import Bot
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
POSTS_PER_RUN = 3
HOURS_AGO = 12  # Только свежие новости за последние 12 часов
POSTED_FILE = "posted_news.json"
MAX_POSTED = 200

RU_FEEDS = [
    ("Хабр: ИИ", "https://habr.com/ru/hub/artificial_intelligence/rss/"),
    ("Хабр: Нейросети", "https://habr.com/ru/hub/neural_networks/rss/"),
    ("Хабр: Machine Learning", "https://habr.com/ru/hub/machine_learning/rss/"),
    ("Naked Science", "https://naked-science.ru/feed"),
    ("CNews", "https://www.cnews.ru/inc/rss/news.xml"),
    ("iXBT", "https://www.ixbt.com/rss/allnews.xml"),
]

EN_FEEDS = [
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("Wired AI", "https://www.wired.com/feed/tag/ai/latest/rss"),
]

SIGNATURE = "\n\n🤖 Подписывайся: @newschanelll_ai"

def load_posted():
    if os.path.exists(POSTED_FILE):
        try:
            with open(POSTED_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                links = set(data.get("links", []))
                log.info(f"Загружено {len(links)} отправленных ссылок из памяти")
                return links
        except Exception as e:
            log.warning(f"Ошибка чтения файла памяти: {e}")
    log.info("Память пуста, начинаем с чистого листа")
    return set()

def save_posted(links_set):
    try:
        with open(POSTED_FILE, 'w', encoding='utf-8') as f:
            links_list = list(links_set)[-MAX_POSTED:]
            json.dump({"links": links_list}, f, ensure_ascii=False, indent=2)
        log.info(f"Память обновлена и сохранена ({len(links_list)} ссылок)")
    except Exception as e:
        log.error(f"Ошибка сохранения памяти: {e}")

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
        params = urllib.parse.urlencode({"q": text[:500], "langpair": "en|ru"})
        req = urllib.request.Request(f"{url}?{params}", headers={"User-Agent": "NewsBot/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("responseData", {}).get("translatedText", text)
    except Exception as e:
        log.warning(f"Ошибка перевода: {e}")
        return text

def format_post(title, summary, link, source, translated=False):
    text = f"🔹 <b>{title}</b>\n\n"
    if summary:
        summary = summary[:300]
        last_dot = summary.rfind('.')
        text += f"{summary[:last_dot+1] if last_dot > 100 else summary + '...'}\n\n"
    if link:
        text += f"🔗 <a href=\"{link}\">Читать полностью</a>\n"
    text += f"📰 <i>Источник: {source}{' (перевод)' if translated else ''}</i>{SIGNATURE}"
    return text

async def main():
    if not BOT_TOKEN or not CHANNEL_ID:
        log.error("Не задан токен или ID канала!")
        return

    bot = Bot(token=BOT_TOKEN)
    posted_links = load_posted()
    all_news = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=HOURS_AGO)

    for source_name, url in RU_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                published = entry.get('published_parsed')
                if published:
                    pub_date = datetime(*published[:6], tzinfo=timezone.utc)
                    if pub_date < cutoff_time:
                        continue
                link = entry.get('link', '')
                if link in posted_links:
                    continue
                title = clean_html(entry.get('title', ''))
                if title and link:
                    all_news.append({"title": title, "summary": clean_html(entry.get('summary', '')),
                                     "link": link, "source": source_name, "translated": False, "priority": 1})
        except Exception as e:
            log.warning(f"Ошибка {source_name}: {e}")

    for source_name, url in EN_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                published = entry.get('published_parsed')
                if published:
                    pub_date = datetime(*published[:6], tzinfo=timezone.utc)
                    if pub_date < cutoff_time:
                        continue
                link = entry.get('link', '')
                if link in posted_links:
                    continue
                title_en = clean_html(entry.get('title', ''))
                if title_en and link:
                    all_news.append({"title": translate_to_ru(title_en),
                                     "summary": translate_to_ru(clean_html(entry.get('summary', ''))),
                                     "link": link, "source": source_name, "translated": True, "priority": 2})
        except Exception as e:
            log.warning(f"Ошибка {source_name}: {e}")

    if not all_news:
        log.info("Новых новостей не найдено. Бот завершает работу без постов.")
        return

    all_news.sort(key=lambda x: x["priority"])
    posts_to_publish = all_news[:POSTS_PER_RUN]
    log.info(f"Публикую {len(posts_to_publish)} новостей...")

    for i, item in enumerate(posts_to_publish):
        try:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=format_post(item["title"], item["summary"], item["link"], item["source"], item["translated"]),
                parse_mode=ParseMode.HTML
            )
            posted_links.add(item["link"])
            log.info(f"✅ Пост {i+1}: {item['title'][:40]}...")
            if i < len(posts_to_publish) - 1:
                await asyncio.sleep(3)
        except Exception as e:
            log.error(f"Ошибка отправки: {e}")

    save_posted(posted_links)
    log.info("Готово!")

if __name__ == "__main__":
    asyncio.run(main())
