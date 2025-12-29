import os
import re
import uuid
import telebot
import yt_dlp
from fastapi import FastAPI, Request

# ================= CONFIG =================
BOT_TOKEN = os.getenv("7907868252:AAF15geicSBKFaFRpR7uLS5dCClI7SrPuak")
WEBHOOK_URL = os.getenv("https://bot-kwai-tiktok.onrender.com")

if not BOT_TOKEN or not WEBHOOK_URL:
    raise RuntimeError("BOT_TOKEN ou WEBHOOK_URL não definido")

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = FastAPI()

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ================= UTIL =================
def is_valid_url(url: str) -> bool:
    return url.startswith("http")


def barra_progresso(percent: int) -> str:
    total = 10
    filled = int((percent / 100) * total)
    return "█" * filled + "░" * (total - filled)


def progresso_hook(chat_id, msg_id):
    last = {"p": -1}

    def hook(d):
        try:
            if d["status"] == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes", 0)

                if total:
                    percent = int(downloaded * 100 / total)
                    if percent != last["p"]:
                        last["p"] = percent
                        bot.edit_message_text(
                            f"⏳ Baixando...\n\n{barra_progresso(percent)} {percent}%",
                            chat_id,
                            msg_id
                        )

            elif d["status"] == "finished":
                bot.edit_message_text(
                    "✅ Download concluído!\n📤 Enviando vídeo...",
                    chat_id,
                    msg_id
                )
        except:
            pass

    return hook


def baixar_video(url, chat_id, msg_id):
    file_id = str(uuid.uuid4())
    output = f"{DOWNLOAD_DIR}/{file_id}.mp4"

    ydl_opts = {
        "outtmpl": output,
        "format": "mp4/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "socket_timeout": 30,
        "progress_hooks": [progresso_hook(chat_id, msg_id)],
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 12) "
                "Chrome/120.0.0.0 Mobile"
            )
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return output if os.path.exists(output) else None
    except:
        return None

# ================= BOT COMMANDS =================
@bot.message_handler(commands=["start"])
def start(msg):
    bot.reply_to(
        msg,
        "📥 *Downloader TikTok / Kwai*\n\n"
        "Use:\n"
        "`/download LINK_DO_VIDEO`",
        parse_mode="Markdown"
    )


@bot.message_handler(commands=["download"])
def download(msg):
    status = None
    video_path = None

    try:
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(msg, "❌ Envie o link.")
            return

        url = parts[1].strip()
        if not is_valid_url(url):
            bot.reply_to(msg, "❌ Link inválido.")
            return

        status = bot.reply_to(msg, "⏳ Iniciando download...")

        video_path = baixar_video(url, msg.chat.id, status.message_id)

        if not video_path:
            bot.edit_message_text(
                "❌ Falha ao baixar o vídeo.",
                msg.chat.id,
                status.message_id
            )
            return

        with open(video_path, "rb") as video:
            bot.send_video(
                msg.chat.id,
                video,
                supports_streaming=True,
                timeout=180
            )

    except Exception as e:
        bot.reply_to(msg, f"❌ Erro:\n{e}")

    finally:
        try:
            if status:
                bot.delete_message(msg.chat.id, status.message_id)
        except:
            pass

        try:
            if video_path and os.path.exists(video_path):
                os.remove(video_path)
        except:
            pass

# ================= WEBHOOK =================
@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = telebot.types.Update.de_json(data)
    bot.process_new_updates([update])
    return {"ok": True}


@app.on_event("startup")
def on_startup():
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    print("Webhook ativo")

@app.on_event("shutdown")
def on_shutdown():
    bot.remove_webhook()