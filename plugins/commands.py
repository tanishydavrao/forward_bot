from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
import httpx
from datetime import datetime, timezone
from conf import MONGO_URL, LIMIT_PER_DAY_FORWARD, OWNER_ID, SEARCH_API_BASE, MY_ANIME_BASE, OWNER_ID, MONGO_URL
from pymongo.errors import PyMongoError

# MongoDB Setup
mongo = MongoClient(MONGO_URL)
db = mongo["forwardbot"]
users_col = db["users"]
failed_col = db["failed_users"] 

@Client.on_message(filters.command("stats") & filters.user(int(OWNER_ID)))
async def admin_stats_handler(client: Client, message: Message):
    total_users = users_col.count_documents({})
    now = datetime.now(timezone.utc)

    active_today = users_col.count_documents({
        "reset_time": {"$gt": now},
        "count": {"$gt": 0}
    })

    sent_today = users_col.aggregate([
        {"$match": {"reset_time": {"$gt": now}}},
        {"$group": {"_id": None, "total": {"$sum": "$count"}}}
    ])
    sent_count = next(sent_today, {}).get("total", 0)

    at_limit = users_col.count_documents({
        "reset_time": {"$gt": now},
        "count": LIMIT_PER_DAY_FORWARD
    })

    text = (
        "<b>📊 Admin Bot Statistics</b>\n\n"
        f"👥 Total Users: <code>{total_users}</code>\n"
        f"🟢 Active Today: <code>{active_today}</code>\n"
        f"📦 Files Sent Today: <code>{sent_count}</code>\n"
        f"🚫 Users at Limit: <code>{at_limit}</code>\n"
    )

    await message.reply_text(text)


# ✅ User Stats
@Client.on_message(filters.command("mystats") & (filters.private | filters.group))
async def user_stats_handler(client: Client, message: Message):
    user_id = message.from_user.id
    now = datetime.now(timezone.utc)

    user_data = users_col.find_one({"_id": user_id})

    if not user_data:
        return await message.reply("❌ No data found for you.")

    count = user_data.get("count", 0)
    reset_time = user_data.get("reset_time", now)
    if reset_time.tzinfo is None:
        reset_time = reset_time.replace(tzinfo=timezone.utc)

    remaining = max(0, LIMIT_PER_DAY_FORWARD - count)

    text = (
        "<b>📈 Your Usage Stats</b>\n\n"
        f"📤 Files Sent: <code>{count}</code> / <code>{LIMIT_PER_DAY_FORWARD}</code>\n"
        f"🕓 Remaining Today: <code>{remaining}</code>\n"
        f"♻️ Reset Time: <code>{reset_time.strftime('%Y-%m-%d %H:%M:%S')}</code> UTC"
    )

    await message.reply_text(text)

@Client.on_message(filters.command("all") & filters.user(int(OWNER_ID)))
async def broadcast_handler(client, message: Message):
    if not message.reply_to_message:
        return await message.reply("❌ Reply to a message you want to broadcast.")

    msg = message.reply_to_message
    users = users_col.find({})
    total = 0
    success = 0
    failed = 0

    await message.reply("📤 Broadcast started...")

    for user in users:
        user_id = user["_id"]
        total += 1
        try:
            await msg.copy(chat_id=user_id)
            success += 1
        except Exception as e:
            failed += 1
            print(f"❌ Failed for {user_id}: {e}")
            failed_col.update_one(
                {"_id": user_id},
                {"$set": {"reason": str(e)}},
                upsert=True
            )
            continue

    report = (
        f"📊 <b>Broadcast Summary</b>\n"
        f"👥 Total Users: {total}\n"
        f"✅ Sent: {success}\n"
        f"❌ Failed: {failed}"
    )
    await message.reply(report)


# Utility: Clean and format languages
def clean_languages(lang_str):
    return ", ".join([x.strip().capitalize() for x in lang_str.replace("-", ",").split(",")])

# Clean command: Remove blocked/deleted users
@Client.on_message(filters.command("clean") & filters.user(int(OWNER_ID)))
async def clean_invalid_users(client: Client, message: Message):
    total = 0
    removed = 0
    errors = 0

    await message.reply("🧹 Cleaning users who failed during broadcast...")

    try:
        failed_user_ids = [u["_id"] for u in db["failed_users"].find()]
        total = len(failed_user_ids)

        for uid in failed_user_ids:
            try:
                users_col.delete_one({"_id": uid})
                removed += 1
            except PyMongoError as e:
                print(f"MongoDB deletion error: {e}")
                errors += 1

        # Clear failed_users list after cleanup
        db["failed_users"].delete_many({})

    except Exception as e:
        return await message.reply(f"❌ Error while cleaning: <code>{e}</code>")

    await message.reply(
        f"✅ Cleaning Completed!\n"
        f"👥 Total Failed Users: <b>{total}</b>\n"
        f"🗑️ Removed: <b>{removed}</b>\n"
        f"⚠️ Errors: <b>{errors}</b>"
    )


# /u movie | /u series command
@Client.on_message(filters.command("u") & filters.user(int(OWNER_ID)))
async def broadcast_latest_content(client: Client, message: Message):
    if len(message.command) < 2 or message.command[1].lower() not in ["movie", "series"]:
        return await message.reply("❌ Usage:\n<u movie>\n<u series>")

    content_type = message.command[1].lower()
    sent_msg = await message.reply(f"⏳ Searching latest Hindi {content_type}...")

    content = None
    page = 1

    try:
        async with httpx.AsyncClient() as http_client:
            while page <= 5:
                res = await http_client.get(
                    f"{SEARCH_API_BASE}/latest/?t={content_type}&page={page}",
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                data = res.json()
                items = data.get("items", [])

                for item in items:
                    langs = item.get("languages", "").lower()
                    tmdb = item.get("tmdb", {})
                    if "hindi" in langs and tmdb and tmdb.get("type", "").lower() == content_type:
                        content = item
                        break
                if content:
                    break
                page += 1
    except Exception as e:
        return await sent_msg.edit(f"❌ Error fetching data: <code>{e}</code>")

    if not content:
        return await sent_msg.edit(f"❌ No suitable Hindi {content_type} found (checked {page - 1} page(s)).")

    tmdb = content["tmdb"]
    title = tmdb.get("title", "No Title")
    genres = tmdb.get("genre") or tmdb.get("genres") or []
    top_genres = genres[:3]
    genres_str = ", ".join(top_genres) if top_genres else "Unknown"
    languages_str = clean_languages(content.get("languages", "N/A"))
    type_ = tmdb.get("type", "N/A").capitalize()
    url_slug = tmdb.get("url", "")
    poster_path = tmdb.get("poster")
    poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
    ep_images = content.get("epimg") or tmdb.get("epimg") or []
    ep_img_url = None
    if ep_images:
        last_img = ep_images[-1].get("img")
        if last_img:
            ep_img_url = f"https://image.tmdb.org/t/p/w500{last_img}"

    # Prepare message content and URL
    if content_type == "series":
        post_id = content.get("_id")
        async with httpx.AsyncClient() as client_:
            try:
                ep_res = await client_.get(
                    f"{SEARCH_API_BASE}/post/id/{post_id}",
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                ep_data = ep_res.json()
                ep_tmdb = ep_data.get("tmdb", {})
                tmdb_id = ep_tmdb.get("url") or ep_tmdb.get("_id") or "1"
                episode = ep_data.get("episode_number") or ep_tmdb.get("total_episodes") or "??"
                episode = str(episode).zfill(2)
            except Exception:
                tmdb_id = "0"
                episode = "??"

        watch_url = f"{MY_ANIME_BASE}/episode/{tmdb_id}x{episode}"
        button_text = f"▶️ Watch Episode {episode}"
        caption = (
            f"<b>{title}</b>\n\n"
            f"🎞️ Episode: <b>{episode}</b>\n"
            f"🎭 Genre: <b>{genres_str}</b>\n"
            f"🌐 Language(s): <b>{languages_str}</b>\n"
            f"📺 Type: <b>{type_}</b>"
        )
    else:
        runtime = tmdb.get("episode_runtime") or tmdb.get("runtime") or "??"
        rating = tmdb.get("rating", "N/A")
        watch_url = f"{MY_ANIME_BASE}/movie/{url_slug}"
        button_text = "▶️ Watch Movie"
        caption = (
            f"<b>{title}</b>\n\n"
            f"🕒 Runtime: <b>{runtime} min</b>\n"
            f"⭐ Rating: <b>{rating}</b>\n"
            f"🎭 Genre: <b>{genres_str}</b>\n"
            f"🌐 Language(s): <b>{languages_str}</b>\n"
            f"📺 Type: <b>{type_}</b>"
        )

    # Send to all users
    buttons = InlineKeyboardMarkup([[InlineKeyboardButton(button_text, url=watch_url)]])
    await sent_msg.edit("📤 Broadcasting to users...")

    total, success, failed = 0, 0, 0

    for user in users_col.find():
        if not isinstance(user, dict) or "_id" not in user:
            continue

        user_id = user["_id"]
        total += 1
        try:
            if ep_img_url:
                await client.send_photo(user_id, ep_img_url, caption=caption, reply_markup=buttons)
            elif poster_url:
                await client.send_photo(user_id, poster_url, caption=caption, reply_markup=buttons)
            else:
                await client.send_message(user_id, caption, reply_markup=buttons)
            success += 1
        except Exception as e:
            failed += 1
            # Log to MongoDB collection `failed_users`
            failed_col.update_one(
                {"_id": user_id},
                {"$set": {"reason": str(e)}},
                upsert=True
            )

    await message.reply(
        f"✅ Broadcast Completed!\n"
        f"👥 Total Users: <b>{total}</b>\n"
        f"📬 Sent: <b>{success}</b>\n"
        f"❌ Failed: <b>{failed}</b>"
    )
