from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import aiohttp
import asyncio
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from urllib.parse import quote
from pyrogram.enums import ParseMode
import random
import base64
import httpx

from conf import (
    TG_BOT_TOKEN, APP_ID, API_HASH, CHANNEL_ID, API_URL,
    LIMIT_PER_DAY_FORWARD, MONGO_URL, OWNER_ID,
    START_MSG, START_PIC, ABOUT_TXT, HELP_TXT, MY_ANIME_BASE, SEARCH_API_BASE
)

# ✅ Only one instance
bot = Client(
    "my_bot",
    bot_token=TG_BOT_TOKEN,
    api_id=APP_ID,
    api_hash=API_HASH,
    plugins={"root": "plugins"},
)

delete_queue = asyncio.Queue()
semaphore = asyncio.Semaphore(3)
delete_task_started = False
sent_messages = {}

# MongoDB setup
mongo = MongoClient(MONGO_URL)
db = mongo["forwardbot"]
users_col = db["users"]
messages_col = db["messages"]  

EMOJI_REACTIONS = [
    "🔥", "🎬", "👀", "✨", "🍿", "💖", "📥", "🎉", "😍",
    "📽️", "❤️", "💯", "🎵", "📸", "🤩", "🎧", "👍", "💫", 
    "🪄", "📁", "💥", "🎶", "💾", "🙌"
]

async def background_auto_delete_loop():
    global delete_task_started
    print("Auto-delete task started at", datetime.now(timezone.utc))

    while True:
        try:
            now = datetime.now(timezone.utc)

            # Find all messages whose deletion_time has passed
            expired = messages_col.find({"deletion_time": {"$lte": now}})
            found = False

            for doc in expired:
                found = True
                chat_id = doc["chat_id"]
                msg_id = doc["msg_id"]

                try:
                    await bot.delete_messages(chat_id, msg_id)
                    print(f"✅ Deleted expired message: chat_id={chat_id}, msg_id={msg_id}")
                except Exception as e:
                    print(f"❌ Failed to delete: {chat_id}/{msg_id} → {e}")

                # Remove from DB regardless of success
                messages_col.delete_one({"_id": doc["_id"]})

            if not found:
                print("No expired messages to delete at", now)

        except Exception as e:
            print("💥 Error in auto-delete loop:", e)

        await asyncio.sleep(300)



@bot.on_message(filters.command("start") & (filters.private | filters.group))
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    now = datetime.now(timezone.utc)

    # Ensure user is tracked in MongoDB
    user_data = users_col.find_one({"_id": user_id})
    if not user_data:
        reset_time = now + timedelta(days=1)
        users_col.insert_one({
            "_id": user_id,
            "count": 0,
            "reset_time": reset_time
        })
        count = 0
    else:
        count = user_data.get("count", 0)
        reset_time = user_data.get("reset_time", now)

        # Ensure reset_time is timezone-aware
        if reset_time.tzinfo is None:
            reset_time = reset_time.replace(tzinfo=timezone.utc)

        # Reset daily quota if needed
        if now > reset_time:
            count = 0
            reset_time = now + timedelta(days=1)
            users_col.update_one(
                {"_id": user_id},
                {"$set": {"count": 0, "reset_time": reset_time}}
            )

    # ➤ Start without token
    if len(message.command) < 2:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("• ᴡᴀᴛᴄʜ/ᴅᴏᴡɴʟᴏᴀᴅ •", url=MY_ANIME_BASE)],
            [
                InlineKeyboardButton("• ᴀʙᴏᴜᴛ", callback_data="about"),
                InlineKeyboardButton("ʜᴇʟᴘ •", callback_data="help")
            ]
        ])
        return await message.reply_photo(
            photo=START_PIC,
            caption=START_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username="@" + message.from_user.username if message.from_user.username else "N/A",
                mention=message.from_user.mention,
                id=message.from_user.id
            ),
            reply_markup=keyboard
        )

    # ➤ Token-based flow
    token = message.command[1]
    api_url = f"{API_URL}/api/data.php?token={token}&key=despacito"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    return await message.reply("❌ API request failed.")
                data = await resp.json()
    except Exception as e:
        return await message.reply(f"❌ API error:\n{e}")

    forward_ids = data.get("forward_ids", [])
    if not forward_ids:
        return await message.reply(
            "➤ ɪғ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴡᴀᴛᴄʜ ᴏʀ ᴅᴏᴡɴʟᴏᴀᴅ ғɪʟᴇs, ɢᴏ ᴛᴏ <a href='https://go.myanimeworld.in/'>ᴍʏᴀɴɪᴍᴇᴡᴏʀʟᴅ.ɪɴ</a>.\n"
            "➤ ʏᴏᴜ <b>ᴍᴜsᴛ</b> <a href='https://t.me/+3tJ9XErvccdmM2Zl'>ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ</a> ᴛᴏ ᴀᴄᴄᴇss ғɪʟᴇs.\n\n",
            parse_mode=ParseMode.HTML
        )

    # ➤ Check quota
    remaining = LIMIT_PER_DAY_FORWARD - count
    if remaining <= 0:
        return await message.reply(
            f"🚫 You've reached your daily limit of {LIMIT_PER_DAY_FORWARD} file(s).\nTry again after 24 hours."
        )
    if len(forward_ids) > remaining:
        return await message.reply(
            f"⚠️ You can only get {remaining} more file(s) today.\nTry again tomorrow."
        )

    # ➤ Start background delete task once
    global delete_task_started
    if not delete_task_started:
        asyncio.create_task(background_auto_delete_loop())
        delete_task_started = True

    copied_messages = []
    sent_messages.setdefault(message.chat.id, [])

    for msg_id in forward_ids:
        try:
            async with semaphore:
                copied = await client.copy_message(
                    chat_id=message.chat.id,
                    from_chat_id=int(CHANNEL_ID),
                    message_id=int(msg_id)
                )
                copied_messages.append(copied.id)
            await asyncio.sleep(0.5)
        except Exception as e:
            await message.reply(f"⚠️ Failed to send message ID {msg_id}.\n{e}")
            continue

    if not copied_messages:
        return await message.reply("❌ Failed to send any files.")

    # ➤ Update user count
    users_col.update_one(
        {"_id": user_id},
        {"$inc": {"count": len(copied_messages)}}
    )

    # ➤ Send confirmation + emoji
    try:
        confirm_msg = await message.reply(
            f"✅ Successfully sent <b>{len(copied_messages)}</b> file(s).",
            parse_mode=ParseMode.HTML
        )
        copied_messages.append(confirm_msg.id)
        await message.reply(random.choice(EMOJI_REACTIONS), disable_notification=True)
    except Exception as e:
        print(f"Error sending confirmation: {e}")

    # ➤ Schedule deletion in 10 minutes
    delete_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    for msg_id in copied_messages:
        messages_col.insert_one({
        "chat_id": message.chat.id,
        "msg_id": msg_id,
        "deletion_time": delete_at
        })



# --- UTILS FOR /s COMMAND ---

def encode_query(q: str) -> str:
    return base64.urlsafe_b64encode(q.encode()).decode().rstrip("=")

def decode_query(b64_q: str) -> str:
    try:
        padding = 4 - (len(b64_q) % 4)
        if padding and padding < 4:
            b64_q += "=" * padding
        return base64.urlsafe_b64decode(b64_q.encode()).decode()
    except Exception as e:
        print(f"[DECODE ERROR] {e}")
        return ""

def format_results(items):
    text = ""
    for item in items:
        tmdb = item.get("tmdb", {})
        title = tmdb.get("title", "Unknown Title")
        url_path = tmdb.get("url", "")
        kind = tmdb.get("type", "movie")
        languages = item.get("languages", "Unknown")

        link_type = "series" if kind == "series" else "movie"
        url = f"{MY_ANIME_BASE}/{link_type}/{url_path}"

        text += (
            f"🎬 <b>{title}</b>\n"
            f"🔉 <b>Languages:</b> {languages}\n"
            f"🔗 <a href=\"{url}\">Watch/Download</a>\n\n"
        )
    return text.strip()



def build_keyboard(query, page, total_pages, content_type="", tag="s", user_id=None):
    b64 = encode_query(query)
    buttons = []

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"{tag}|{b64}|{page-1}|{content_type}|{user_id}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"{tag}|{b64}|{page+1}|{content_type}|{user_id}"))
    if nav:
        buttons.append(nav)

    if query.lower() not in ("movies", "series"):
        active = " ✅"
        buttons.append([
            InlineKeyboardButton("🎞 Movies" + (active if content_type == "movie" else ""), callback_data=f"{tag}|{b64}|1|movie|{user_id}"),
            InlineKeyboardButton("📺 Series" + (active if content_type == "series" else ""), callback_data=f"{tag}|{b64}|1|series|{user_id}"),
            InlineKeyboardButton("🌀 All" + (active if content_type == "" else ""), callback_data=f"{tag}|{b64}|1||{user_id}")
        ])

    # Close button
    if user_id:
        buttons.append([
            InlineKeyboardButton("❌ Close", callback_data=f"close|{user_id}")
        ])

    return InlineKeyboardMarkup(buttons)


@bot.on_callback_query(filters.regex(r"^close\|"))
async def close_callback_handler(client: Client, cq: CallbackQuery):
    parts = cq.data.split("|")
    if len(parts) != 2:
        return await cq.answer("❌ Invalid callback data.", show_alert=True)

    orig_user_id = parts[1]
    if str(cq.from_user.id) != str(orig_user_id):
        return await cq.answer("🤖 Access denied! This button was made with someone else’s sweat and tears. Respect it 😆", show_alert=True)

    try:
        await cq.message.delete()
    except Exception:
        await cq.message.edit("❌ Closed", reply_markup=None)


@bot.on_callback_query(filters.regex(r"^e\|"))
async def letters_callback_handler(client: Client, cq: CallbackQuery):
    parts = cq.data.split("|")
    if len(parts) != 5:  # e|b64_q|page|content_type|user_id
        return await cq.answer("❌ Invalid callback data.", show_alert=True)

    _, b64_q, page_str, content_type, orig_user_id = parts

    if str(cq.from_user.id) != str(orig_user_id):
        return await cq.answer("🤚 Not your button, chief. Start your own search like a legend 🚀", show_alert=True)

    # ⚠️ DO NOT call await cq.answer() again below this point

    letter = decode_query(b64_q)
    if not letter:
        return await cq.message.edit("❌ Failed to decode letter.")

    try:
        page = int(page_str)
    except ValueError:
        return await cq.message.edit("❌ Invalid page number.")

    params = {"page": page}
    if content_type:
        params["t"] = content_type

    try:
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(f"{SEARCH_API_BASE}/letters/{letter}", params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return await cq.message.edit(f"❌ API error: {e}")

    items = data.get("items", [])
    if not items:
        return await cq.message.edit("⚠️ No results found.")

    total = data.get("total_pages", 1)
    text = format_results(items)
    kb = build_keyboard(letter, page, total, content_type, tag="e", user_id=orig_user_id)

    await cq.message.edit(text, reply_markup=kb)


@bot.on_callback_query(filters.regex(r"^ep\|"))
async def endpoint_callback_handler(client: Client, cq: CallbackQuery):
    parts = cq.data.split("|")
    if len(parts) != 5:  # ep|b64_q|page|content_type|user_id
        return await cq.answer("❌ Invalid callback data.", show_alert=True)

    _, b64_q, page_str, content_type, orig_user_id = parts

    if str(cq.from_user.id) != str(orig_user_id):
        return await cq.answer("🚫 Button stealing detected. Initiating FBI trace... just kidding. Do your own search!", show_alert=True)

    # 👇 From here onward, do NOT use cq.answer again
    cmd = decode_query(b64_q)
    if not cmd or cmd not in API_ENDPOINTS:
        return await cq.message.edit("❌ Invalid command in callback.")

    try:
        page = int(page_str)
    except ValueError:
        return await cq.message.edit("❌ Invalid page number.")

    params = {"page": page}
    if content_type:
        params["t"] = content_type

    try:
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(f"{SEARCH_API_BASE}{API_ENDPOINTS[cmd]}", params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return await cq.message.edit(f"❌ API error: {e}")

    items = data.get("items", [])
    if not items:
        return await cq.message.edit("⚠️ No content found.")

    total = data.get("total_pages", 1)
    text = format_endpoint_results(items)
    kb = build_keyboard(cmd, page, total, content_type, tag="ep", user_id=orig_user_id)

    await cq.message.edit(text, reply_markup=kb)


@bot.on_callback_query(filters.regex(r"^s\|"))
async def callback_handler(client: Client, cq: CallbackQuery):
    parts = cq.data.split("|")
    if len(parts) != 5:  # s|b64_q|page|content_type|user_id
        return await cq.answer("❌ Invalid callback data.", show_alert=True)

    _, b64_q, page_str, content_type, orig_user_id = parts

    if str(cq.from_user.id) != str(orig_user_id):
        return await cq.answer("😬 Touching random buttons, huh? You must be fun at elevators.", show_alert=True)

    # ✅ DO NOT use cq.answer() again, unless necessary
    query = decode_query(b64_q)
    if not query:
        return await cq.message.edit("❌ Failed to decode query.")

    try:
        page = int(page_str)
    except ValueError:
        return await cq.message.edit("❌ Invalid page number.")

    params = {"q": query, "page": page}
    if content_type:
        params["t"] = content_type

    try:
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(f"{SEARCH_API_BASE}/search/", params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return await cq.message.edit(f"❌ API error: {e}")

    items = data.get("items", [])
    if not items:
        return await cq.message.edit("⚠️ No results found.")

    total = data.get("total_pages", 1)
    text = format_results(items)
    kb = build_keyboard(query, page, total, content_type, tag="s", user_id=orig_user_id)

    await cq.message.edit(text, reply_markup=kb)



# --- /s command handler ---
@bot.on_message((filters.private | filters.group) & filters.command("s"))
async def search_handler(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("❌ Please provide a search query.\n\nUsage: <code>/s naruto</code>")

    query = " ".join(message.command[1:])
    sent = await message.reply("🔍 Searching…")

    try:
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(f"{SEARCH_API_BASE}/search/", params={"q": query, "page": 1})
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return await sent.edit(f"❌ API error: {e}")

    items = data.get("items", [])
    if not items:
        return await sent.edit("⚠️ No results found.")

    total = data.get("total_pages", 1)
    text = format_results(items)
    kb = build_keyboard(query, 1, total, content_type="", tag="s", user_id=message.from_user.id)



    await sent.edit(text, reply_markup=kb)

# --- Callback query handler ---


API_ENDPOINTS = {
    "latest": "/latest/",
    "popular": "/popular/",
    "series": "/series/",
    "anime": "/anime/",
    "cartoon": "/cartoon/",
    "movies": "/movies/",
    "crunchyroll": "/platforms/crunchyroll",
    "netflix": "/platforms/netflix",
    "amazon": "/platforms/amazon%20video",
    
    
    "hindi": "/languages/hindi",
    "tamil": "/languages/tamil",
    "telugu": "/languages/telugu",
    "bengali": "/languages/bengali",
    "malayalam": "/languages/malayalam",
    "kannada": "/languages/kannada",
    "english": "/languages/english",
    "japanese": "/languages/japanese"
}

def format_endpoint_results(items):
    text = ""
    for item in items:
        tmdb = item.get("tmdb", {})
        title = tmdb.get("title", "Unknown Title")
        url_path = tmdb.get("url", "")
        kind = tmdb.get("type", "movie")
        languages = item.get("languages", "Unknown")

        link_type = "series" if kind == "series" else "movie"
        url = f"{MY_ANIME_BASE}/{link_type}/{url_path}"

        text += (
            f"🎬 <b>{title}</b>\n"
            f"🔉 <b>Languages:</b> {languages}\n"
            f"🔗 <a href=\"{url}\">Watch/Download</a>\n\n"
        )
    return text.strip()


@bot.on_message(filters.command([
    "latest", "popular", "series", "anime", "cartoon", "movies",
    "crunchyroll", "netflix", "amazon",
    "hindi", "tamil", "telugu", "bengali", "malayalam",
    "kannada", "english", "japanese"
]) & (filters.private | filters.group))
async def endpoint_command_handler(client: Client, message: Message):
    cmd = message.command[0].lstrip("/")
    endpoint = API_ENDPOINTS.get(cmd)
    if not endpoint:
        return await message.reply("❌ Invalid command.")

    sent = await message.reply("⏳ Fetching content...")

    try:
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(f"{SEARCH_API_BASE}{endpoint}")
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return await sent.edit(f"❌ API error: {e}")

    items = data.get("items", [])
    if not items:
        return await sent.edit("⚠️ No content found.")

    total_pages = data.get("total_pages", 1)
    query = cmd  # using command name
    text = format_endpoint_results(items)

    # 👇 Pass a unique tag to avoid collision with /search
    kb = build_keyboard(query, 1, total_pages, tag="ep", content_type="", user_id=message.from_user.id)  # ep = endpoint

    await sent.edit(text, reply_markup=kb)


# --- /genre {type} command ---
@bot.on_message(filters.command("genre") & (filters.private | filters.group))
async def genre_lookup_handler(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("❌ Please specify a genre e.g. \n\n <code>/genre horror</code>")

    genre_name = " ".join(message.command[1:]).strip().lower()
    sent = await message.reply("⏳ Searching genre...")

    try:
        encoded_genre = quote(genre_name)
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(f"{SEARCH_API_BASE}/genres/{encoded_genre}")
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return await sent.edit(f"❌ API error: {e}")

    items = data.get("items", [])
    if not items:
        return await sent.edit("⚠️ No content found for this genre.")

    total = data.get("total_pages", 1)
    text = format_results(items)
    kb = build_keyboard(genre_name, 1, total, content_type="", tag="s", user_id=message.from_user.id)


    await sent.edit(text, reply_markup=kb)
    

@bot.on_message(filters.command("letters") & (filters.private | filters.group))

async def letters_lookup_handler(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("❌ Please specify a letter, e.g.\n\n <code>/letters a</code>")

    letter = message.command[1].strip().lower()

    if not letter.isalpha() or len(letter) != 1:
        return await message.reply("❌ Only a single alphabet letter is allowed.")

    sent = await message.reply("⏳ Searching...")

    try:
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.get(f"{SEARCH_API_BASE}/letters/{letter}")
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return await sent.edit(f"❌ API error: {e}")

    items = data.get("items", [])
    if not items:
        return await sent.edit("⚠️ No content found for this letter.")

    total = data.get("total_pages", 1)
    text = format_results(items)
    kb = build_keyboard(letter, 1, total, tag="e", content_type="", user_id=message.from_user.id)  # 'e' for letter endpoint

    await sent.edit(text, reply_markup=kb)


@bot.on_callback_query()
async def cb_handler(client, callback_query: CallbackQuery):
    data = callback_query.data
    if data == "about":
        await callback_query.message.edit_text(
            text=ABOUT_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("« Back", callback_data="start_back")]]
            )
        )
    elif data == "help":
        await callback_query.message.edit_text(
            text=HELP_TXT,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("« Back", callback_data="start_back")]]
            )
        )
    elif data == "start_back":
        await callback_query.message.edit_text(
            text=START_MSG.format(
                first=callback_query.from_user.first_name,
                last=callback_query.from_user.last_name,
                username="@" + callback_query.from_user.username if callback_query.from_user.username else "N/A",
                mention=callback_query.from_user.mention,
                id=callback_query.from_user.id
            ),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ᴡᴀᴛᴄʜ/ᴅᴏᴡɴʟᴏᴀᴅ •", url=f"{MY_ANIME_BASE}")],
                [InlineKeyboardButton("• ᴀʙᴏᴜᴛ", callback_data="about"),
                 InlineKeyboardButton("ʜᴇʟᴘ •", callback_data="help")]
            ])
        )        

@bot.on_message(filters.command("reset") & filters.user(int(OWNER_ID)))
async def reset_all_users(client: Client, message: Message):
    try:
        reset_time = datetime.now(timezone.utc) + timedelta(days=1)
        users_col.update_many({}, {"$set": {"count": 0, "reset_time": reset_time}})
        await message.reply("✅ All user limits have been reset for the next 24 hours.")
    except Exception as e:
        await message.reply(f"❌ Reset failed:\n{e}")


@bot.on_message(filters.command("about") & (filters.private | filters.group))
async def about_command(client: Client, message: Message):
    await message.reply_photo(
        photo=START_PIC,
        caption=ABOUT_TXT,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("« Back", callback_data="start_back")]
        ])
    )

@bot.on_message(filters.command("help") & (filters.private | filters.group))
async def help_command(client: Client, message: Message):
    await message.reply_photo(
        photo=START_PIC,
        caption=HELP_TXT,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("« Back", callback_data="start_back")]
        ])
    )


# ✅ Run the bot
if __name__ == "__main__":
    bot.run()
