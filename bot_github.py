"""
АВТОПОСТЕР НОВОСТЕЙ С ПАМЯТЬЮ (через GitHub API)
"""

import os, sys, subprocess, asyncio, logging, re, json, urllib.request, urllib.parse, base64
from datetime import datetime, timedelta, timezone
import feedparser
from telegram import Bot
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
log = logging.getLogger(__name__)

# === НАСТРОЙКИ ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
GH_TOKEN = os.environ.get("GH_TOKEN")
REPO_OWNER = "rafaello1988-source"
REPO_NAME = "news-bot"  # Замени на имя твоего репозитория
POSTS_PER_RUN = 3
HOURS_AGO = 48
POSTED_FILE = "posted_news.json"
MAX_POSTED = 200

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

def load_posted():
    """Загружает отправленные ссылки из файла в репозитории."""
    try:
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{POSTED_FILE}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"token {GH_TOKEN}",
            "User-Agent": "NewsBot/1.0"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = base64.b64decode(data["content"]).decode("utf-8")
            posted_data = json.loads(content)
            links = set(posted_data.get("links", []))
            log.info(f"📚 Загружено {len(links)} отправленных ссылок")
            return links
    except Exception as e:
        log.warning(f"⚠️ Не удалось загрузить файл памяти: {e}. Начинаем с чистого листа.")
        return set()

def save_posted(links_set):
    """Сохраняет ссылки в файл в репозитории через GitHub API."""
    try:
        # Сначала получаем текущий SHA файла (нужен для обновления)
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{POSTED_FILE}"
        req = urllib.request.Request(url, headers={
            "Authorization": f"token {GH_TOKEN}",
            "User-Agent": "NewsBot/1.0"
        })
        
        sha = None
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                sha = data.get("sha")
        except:
            pass  # Файл ещё не существует
        
        # Подготавливаем данные
        links_list = list(links_set)[-MAX_POSTED:]
        content = json.dumps({"links": links_list}, ensure_ascii=False, indent=2)
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        
        # Отправляем PUT запрос
        payload = {
            "message": "Update posted news memory",
            "content": content_b64,
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha
        
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="PUT", headers={
            "Authorization": f"token {GH_TOKEN}",
            "User-Agent": "NewsBot/1.0",
            "Content-Type": "application/json"
        })
        
        with urllib.request.urlopen(req, timeout=10) as resp:
            log.info(f"💾 Память сохранена в репозиторий ({len(links_list)} ссылок)")
    except Exception as e:
        log.error(f"❌ Ошибка сохранения памяти: {e}")

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
        log.warning(f"⚠️ Ошибка перевода: {e}")
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
    if not BOT_TOKEN or not CHANNEL_ID or not GH_TOKEN:
        log.error("❌ Не задан токен бота, ID канала или GitHub токен!")
        return

    bot = Bot(token=BOT_TOKEN)
    posted_links = load_posted()
    all_news = []
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=HOURS_AGO)

    # Русские новости
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
                                     "link": link, "source": source_name, "translated": False})
        except Exception as e:
            log.warning(f"⚠️ Ошибка {source_name}: {e}")

    # Английские новости
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
                                     "link": link, "source": source_name, "translated": True})
        except Exception as e:
            log.warning(f"⚠️ Ошибка {source_name}: {e}")

    if not all_news:
        log.info("ℹ️ Новых новостей не найдено.")
        return

    posts_to_publish = all_news[:POSTS_PER_RUN]
    log.info(f"📝 Публикую {len(posts_to_publish)} новостей...")

    for i, item in enumerate(posts_to_publish):
        try:
            await bot.send_message(chat_id=CHANNEL_ID, 
                                   text=format_post(item["title"], item["summary"], item["link"], 
                                                   item["source"], item["translated"]), 
                                   parse_mode=ParseMode.HTML)
            posted_links.add(item["link"])
            log.info(f"✅ Пост {i+1}: {item['title'][:40]}...")
            if i < len(posts_to_publish) - 1:
                await asyncio.sleep(3)
        except Exception as e:
            log.error(f"❌ Ошибка отправки: {e}")

    save_posted(posted_links)
    log.info("🎉 Готово!")

if __name__ == "__main__":
    asyncio.run(main())
