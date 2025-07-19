import os
from os import environ,getenv
import logging
from logging.handlers import RotatingFileHandler

#--------------------------------------------
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "7599701202:AAHQjV1ZG9b8SUC3wn2vGIwkY2exNctPQIk")
APP_ID = int(os.environ.get("APP_ID", "28598696")) 
API_HASH = os.environ.get("API_HASH", "c89d5411dceeffa4bea9a8e975cf7b41") 
#--------------------------------------------
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1001746772803")) 
OWNER_ID = int(os.environ.get("OWNER_ID", "1479609725")) # Owner id
#--------------------------------------------
PORT = os.environ.get("PORT", "8001")
#--------------------------------------------
API_URL = os.environ.get("API_URI", "https://file.linkxshare.online")
SEARCH_API_BASE = os.environ.get("SEARCH_API_BASE", "https://daddy.linkxshare.online")
MY_ANIME_BASE = os.environ.get("MY_ANIME_BASE", "https://go.myanimeworld.in")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb+srv://harishsarkar1231:despacito@cluster0.kvhaait.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")

LIMIT_PER_DAY_FORWARD = int(os.environ.get("LIMIT_PER_DAY_FORWARD", "50"))
TG_BOT_WORKERS = int(os.environ.get("TG_BOT_WORKERS", "200"))
#--------------------------------------------
START_PIC = os.environ.get("START_PIC", "https://i.postimg.cc/2yf09LZ4/wallpaperflare-com-wallpaper.jpg")

HELP_TXT = (
    "<b><u>🛠️ ᴋɪᴛsᴜᴠᴇʀsᴇ ʙᴏᴛ ᴜsᴀɢᴇ</u></b>\n\n"
    "❏ <b>ᴍᴀɪɴ ᴄᴏᴍᴍᴀɴᴅs:</b>\n"
    "├ /start — Start the bot 🚀 (e.g. <code>/start</code>)\n"
    "├ /about — Bot info & legal links ℹ️ (e.g. <code>/about</code>)\n"
    "├ /help — Show all commands 📘 (e.g. <code>/help</code>)\n"
    "└ /mystats — Check your daily file usage 📊 (e.g. <code>/mystats</code>)\n\n"
    
    "❏ <b>sᴇᴀʀᴄʜ & ʙʀᴏᴡsᴇ:</b>\n"
    "├ /s naruto — Search any title 🔎 (e.g. <code>/s one piece</code>)\n"
    "├ /genre action — Search by genre 🎭 (e.g. <code>/genre romance</code>)\n"
    "├ /letters a — Browse titles by alphabet 🔤 (e.g. <code>/letters s</code>)\n"
    "├ /latest — Recently added content 🆕\n"
    "├ /popular — Most watched/trending 🔥\n"
    "├ /anime — Only anime shows 🧧\n"
    "├ /series — All TV series 📺\n"
    "├ /movies — Only movies 🎥\n"
    "├ /cartoon — Animated cartoons 🐭\n"
    "├ /crunchyroll — Crunchyroll shows 🍙\n"
    "├ /netflix — Netflix content 🍿\n"
    "└ /amazon — Amazon Prime shows 📦\n\n"

    "❏ <b>ʙʏ ʟᴀɴɢᴜᴀɢᴇ:</b>\n"
    "├ /hindi — Shows available in Hindi 🇮🇳\n"
    "├ /tamil — Tamil dubbed content 🎙️\n"
    "├ /telugu — Telugu dubbed content 🎧\n"
    "├ /malayalam — Malayalam content 🥥\n"
    "├ /kannada — Kannada content 🎶\n"
    "├ /bengali — Bengali dubbed content 🥁\n"
    "├ /english — English content 🇺🇸\n"
    "└ /japanese — Japanese originals 🇯🇵\n\n"

)


ABOUT_TXT = """
<b><u>ᴀʙᴏᴜᴛ ᴛʜᴇ ʙᴏᴛ</u></b>
◈ <b>ɴᴀᴍᴇ:</b> ᴋɪᴛsᴜᴠᴇʀsᴇ  
◈ <b>ᴄᴏɴᴛᴀᴄᴛ:</b> <a href='https://t.me/Contact_Support24x7_bot'>sᴜᴘᴘᴏʀᴛ ᴛᴇᴀᴍ</a>  
◈ <b>ᴡᴇʙsɪᴛᴇ:</b> <a href='https://go.myanimeworld.in'>ᴍʏᴀɴɪᴍᴇᴡᴏʀʟᴅ.ɪɴ</a>


<b><u>ʟᴇɢᴀʟ & ᴘʀɪᴠᴀᴄʏ</u></b>  
• <a href='https://myanimeworld.in/blog/disclaimer'>Disclaimer</a>  
• <a href='https://myanimeworld.in/blog/dmca'>DMCA</a>  
• <a href='https://myanimeworld.in/blog/privacy-policy'>Privacy Policy</a>  
• <a href='https://myanimeworld.in/blog/terms-of-service'>Terms of Service</a>
"""

START_MSG = os.environ.get(
    "START_MESSAGE",
    "<b>ʜᴇʟʟᴏ {first}!</b>\n"
    "<i>ᴛʜɪs ɪs</i> <b>ᴋɪᴛsᴜᴠᴇʀsᴇ</b> ✨ — ᴀ ʙᴏᴛ ᴛᴏ ᴀᴄᴄᴇss sʜᴀʀᴇᴅ ғɪʟᴇs ᴏɴ ᴛᴇʟᴇɢʀᴀᴍ.\n"
    "<b>➤</b> ᴅᴀɪʟʏ ʟɪᴍɪᴛ: <u>50 ғɪʟᴇs</u> ᴘᴇʀ ᴜsᴇʀ.\n"
    "<b>➤</b>🎬 <b>ᴡᴀᴛᴄʜ/ᴅᴏᴡɴʟᴏᴀᴅ: </b><a href='https://go.myanimeworld.in/'>ᴍʏᴀɴɪᴍᴇᴡᴏʀʟᴅ.ɪɴ</a>\n"
    "➤ <b>ᴜɴʟᴏᴄᴋ ғᴜʟʟ ᴀᴄᴄᴇss ʙʏ</b> <a href='https://t.me/+3tJ9XErvccdmM2Zl'>ᴊᴏɪɴɪɴɢ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ</a> ✅\n\n"

"❓ ɴᴇᴇᴅ ʜᴇʟᴘ?\n"
"➥ <a href='https://t.me/Contact_Support24x7_bot'>ᴄᴏɴᴛᴀᴄᴛ sᴜᴘᴘᴏʀᴛ</a>\n\n"

"🛡️ <i>ᴛʜɪs ʙᴏᴛ ᴏɴʟʏ sʜᴀʀᴇs ᴘᴜʙʟɪᴄ ᴛᴇʟᴇɢʀᴀᴍ ᴍᴇᴅɪᴀ. ɴᴏ ʜᴏsᴛɪɴɢ ᴏʀ ᴘɪʀᴀᴄʏ ɪɴᴠᴏʟᴠᴇᴅ.</i>"
)

#--------------------------------------------


LOG_FILE_NAME = "telegram_bot_logs.txt"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt='%d-%b-%y %H:%M:%S',
    handlers=[
        RotatingFileHandler(
            LOG_FILE_NAME,
            maxBytes=50000000,
            backupCount=10
        ),
        logging.StreamHandler()
    ]
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)


def LOGGER(name: str) -> logging.Logger:
    return logging.getLogger(name)
   