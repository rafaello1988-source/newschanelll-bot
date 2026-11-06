"""
АВТОПОСТЕР НОВОСТЕЙ ПРО ИИ — ГАРАНТИРОВАННАЯ ПУБЛИКАЦИЯ
"""

import os, sys, subprocess, asyncio, logging, json, re, urllib.request, urllib.parse
from datetime import datetime

# ---------- АВТОУСТАНОВКА БИБЛИОТЕК ----------
NEEDED = ["python-telegram-bot==20.7"]
def ensure_packages():
    for pkg in NEEDED:
        name = pkg.split("==")[0].replace("-", "_")
        try:
            __import__(name)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])
ensure_packages()
# ---------------------------------------------

from telegram import Bot
from telegram.constants import ParseMode

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger("newsbot")

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@newschanelll")
POSTS_PER_RUN = 3

SIGNATURE = "\n\n🤖 Подписывайся: @newschanelll"

# Надежные источники новостей (JSON API вместо RSS)
NEWS_SOURCES = [
    {
        "name": "TechCrunch AI",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "type": "rss"
    },
    {
        "name": "VentureBeat AI",
        "url": "https://venturebeat.com/category/ai/feed/",
        "type": "rss"
    },
    {
        "name": "AI News",
        "url": "https://artificialintelligence-news.com/feed/",
        "type": "rss"
    }
]


def fetch_rss_feed(url: str) -> list[dict]:
    """Парсит RSS-ленту и возвращает список новостей."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
        
        # Простой парсинг XML
        items = []
        import xml.etree.ElementTree as ET
        root = ET.fromstring(content)
        
        for item in root.iter("item"):
            title = item.find("title")
            link = item.find("link")
            description = item.find("description")
            
            if title is not None and title.text:
                items.append({
                    "title": clean_html(title.text),
                    "link": link.text if link is not None else "",
                    "summary": clean_html(description.text)[:300] if description is not None and description.text else ""
                })
        
        return items[:5]  # Берем только 5 последних
    except Exception as e:
        log.warning(f"Ошибка загрузки {url}: {e}")
        return []


def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def translate_to_ru(text: str) -> str:
    """Перевод через MyMemory API."""
    if not text:
        return ""
    try:
        url = "https://api.mymemory.translated.net/get"
        params = urllib.parse.urlencode({"q": text[:500], "langpair": "en|ru"})
        req = urllib.request.Request(f"{url}?{params}", headers={"User-Agent": "NewsBot/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("responseData", {}).get("translatedText", text)
    except Exception:
        return text


def format_post(title: str, summary: str, link: str, source: str) -> str:
    text = f"🔹 <b>{title}</b>\n\n"
    if summary:
        text += f"{summary}\n\n"
    if link:
        text += f"🔗 <a href=\"{link}\">Читать полностью</a>\n"
    text += f"📰 <i>Источник: {source}</i>{SIGNATURE}"
    return text


async def main():
    if not BOT_TOKEN:
        log.error("❌ BOT_TOKEN не задан!")
        return
    
    bot = Bot(token=BOT_TOKEN)
    
    # Собираем новости из всех источников
    all_news = []
    for source in NEWS_SOURCES:
        log.info(f"Загружаю {source['name']}...")
        items = fetch_rss_feed(source["url"])
        log.info(f"  Получено {len(items)} новостей")
        
        for item in items:
            # Переводим на русский
            title_ru = translate_to_ru(item["title"])
            summary_ru = translate_to_ru(item["summary"]) if item["summary"] else ""
            
            all_news.append({
                "title": title_ru,
                "summary": summary_ru,
                "link": item["link"],
                "source": f"{source['name']} (перевод)"
            })
    
    if not all_news:
        log.error("❌ Не удалось получить новости ни из одного источника!")
        # Создаем тестовый пост для проверки
        all_news.append({
            "title": "🧪 Тестовый пост — бот работает!",
            "summary": "Это тестовая публикация для проверки работы автопостера. Скоро здесь будут реальные новости про ИИ.",
            "link": "https://t.me/newschanelll",
            "source": "Система"
        })
        log.info("✅ Создан тестовый пост")
    
    # Публикуем POSTS_PER_RUN постов
    posts_to_publish = all_news[:POSTS_PER_RUN]
    
    for i, item in enumerate(posts_to_publish):
        text = format_post(item["title"], item["summary"], item["link"], item["source"])
        try:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False
            )
            log.info(f"✅ Пост {i+1}/{len(posts_to_publish)}: {item['title'][:50]}")
            if i < len(posts_to_publish) - 1:
                await asyncio.sleep(2)
        except Exception as exc:
            log.error(f"❌ Ошибка поста {i+1}: {exc}")
    
    log.info(f"🎉 Опубликовано {len(posts_to_publish)} постов")


if __name__ == "__main__":
    asyncio.run(main())
