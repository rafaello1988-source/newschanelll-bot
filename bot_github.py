"""
АВТОПОСТЕР НОВОСТЕЙ ПРО ИИ НА РУССКОМ — для GitHub Actions
Запускается по расписанию, публикует 1 пост и завершается.
"""

import os, sys, subprocess, asyncio, logging, hashlib, json, re, urllib.request, urllib.parse
from pathlib import Path

# ---------- АВТОУСТАНОВКА БИБЛИОТЕК ----------
NEEDED = ["python-telegram-bot==20.7", "feedparser==6.0.11"]
def ensure_packages():
    for pkg in NEEDED:
        name = pkg.split("==")[0].replace("-", "_")
        try:
            __import__(name)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])
ensure_packages()
# ---------------------------------------------

import feedparser
from telegram import Bot
from telegram.constants import ParseMode

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger("newsbot")

# === НАСТРОЙКИ (берутся из переменных окружения GitHub) ===
BOT_TOKEN  = os.environ.get("BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@newschanelll")

RU_FEEDS = [
    ("Хабр: ИИ",          "https://habr.com/ru/hub/artificial_intelligence/rss/"),
    ("Хабр: Нейросети",   "https://habr.com/ru/hub/neural_networks/rss/"),
    ("Naked Science",     "https://naked-science.ru/feed"),
]

EN_FEEDS = [
    ("OpenAI Blog",       "https://openai.com/blog/rss.xml"),
    ("Hugging Face Blog", "https://huggingface.co/blog/feed.xml"),
    ("The Verge AI",      "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
]

SIGNATURE = "\n\n🤖 Подписывайся: @newschanelll"


def translate_to_ru(text: str) -> str:
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


def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def collect_news() -> list[dict]:
    fresh = []
    for source_name, url in RU_FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:5]:
                title = clean_html(e.get("title", ""))
                summary = clean_html(e.get("summary", ""))[:400]
                link = (e.get("link") or "").strip()
                if title:
                    fresh.append({"source": source_name, "title": title,
                                  "summary": summary, "link": link})
        except Exception:
            pass
    for source_name, url in EN_FEEDS:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:5]:
                title_en = clean_html(e.get("title", ""))
                summary_en = clean_html(e.get("summary", ""))[:400]
                link = (e.get("link") or "").strip()
                if title_en:
                    fresh.append({
                        "source": f"{source_name} (перевод)",
                        "title": translate_to_ru(title_en),
                        "summary": translate_to_ru(summary_en) if summary_en else "",
                        "link": link,
                    })
        except Exception:
            pass
    return fresh


def format_post(item: dict) -> str:
    text = f"🔹 <b>{item['title']}</b>\n\n"
    if item["summary"]:
        text += f"{item['summary']}\n\n"
    if item["link"]:
        text += f"🔗 <a href=\"{item['link']}\">Читать полностью</a>\n"
    text += f"📰 <i>Источник: {item['source']}</i>{SIGNATURE}"
    return text


async def main():
    if not BOT_TOKEN:
        log.error("❌ BOT_TOKEN не задан!")
        return
    bot = Bot(token=BOT_TOKEN)
    fresh = collect_news()
    if not fresh:
        log.info("Свежих новостей нет.")
        return
    item = fresh[0]
    text = format_post(item)
    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=text,
                               parse_mode=ParseMode.HTML, disable_web_page_preview=False)
        log.info(f"✅ Опубликовано: {item['title'][:60]}")
    except Exception as exc:
        log.error(f"❌ Ошибка: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
