import re
import os
import time
import asyncio
from html import escape
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import ContextTypes, ApplicationHandlerStop

import config
import database as db
import wordpress as wp
from templates import TELEGRAM_4K_MSG

pending_files = {}


BOT_STARTED_AT = datetime.now(ZoneInfo("Asia/Kolkata"))

def remove_video_extension(file_name):
    return re.sub(r'\.(mp4|mkv|avi|mov)$', '', str(file_name), flags=re.IGNORECASE).strip()

def normalize_username(username):
    return (username or "").replace("@", "").strip().lower()

def is_allowed_user(update: Update):
    user = update.effective_user

    if not user:
        return False

    admin_ids = set(int(x) for x in getattr(config, "ADMIN_IDS", []))

    # Allow admin users
    if user.id in admin_ids:
        return True

    # Allow file sharing bot reply
    file_bot_username = normalize_username(getattr(config, "FILE_BOT_USERNAME", ""))
    current_username = normalize_username(user.username)

    if file_bot_username and current_username == file_bot_username:
        return True

    return False


async def authorization_gate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message

    if not message:
        raise ApplicationHandlerStop

    chat = update.effective_chat

    # Allow only your file sharing log channel silently
    if chat and chat.type != "private":
        if is_file_log_chat(update):
            return

        raise ApplicationHandlerStop

    # Private chat allowed users
    if is_allowed_user(update):
        return

    contact_username = getattr(config, "CONTACT_USERNAME", "@The_vK_3")

    await message.reply_text(
        f"🚫 <b>Access Denied!</b>\n"
        f"You are not authorized to use this bot.\n\n"
        f"📩 Contact {contact_username} for access!",
        parse_mode="HTML"
    )

    raise ApplicationHandlerStop

def get_file_bot_username():
    return normalize_username(config.FILE_BOT_USERNAME)

def is_file_log_chat(update: Update):
    chat = update.effective_chat

    if not chat:
        return False

    allowed_ids = set(int(x) for x in getattr(config, "FILE_LOG_CHAT_IDS", []))

    if chat.id in allowed_ids:
        return True

    allowed_username = normalize_username(getattr(config, "FILE_LOG_CHANNEL_USERNAME", ""))

    if allowed_username and normalize_username(getattr(chat, "username", "")) == allowed_username:
        return True

    return False

def get_admin_ids():
    return set(int(x) for x in getattr(config, "ADMIN_IDS", []))


def is_admin(update: Update):
    user = update.effective_user
    return bool(user and user.id in get_admin_ids())


async def send_clean(context, chat_id, text):
    return await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
        disable_web_page_preview=True
    )


async def reply_clean(message, text):
    return await message.reply_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

def clean_file_name(name):
    return escape(str(name or "Unknown"))


def format_time_ist():
    return datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y, %I:%M %p")

async def delete_status_messages(context, chat_id, message_ids):
    """
    Deletes temporary bot status messages.
    Final success/error message will stay.
    """

    if not message_ids:
        return

    for message_id in message_ids:
        try:
            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=message_id
            )
        except Exception as e:
            print(f"Could not delete message {message_id}: {e}")


async def expire_pending_file(file_name, context):
    timeout_seconds = int(getattr(config, "PENDING_TIMEOUT_SECONDS", 1800))

    try:
        await asyncio.sleep(timeout_seconds)

        data = pending_files.get(file_name)

        if not data:
            return

        pending_files.pop(file_name, None)

        await send_clean(
            context,
            data["user_chat_id"],
            f"⏳ <b>Link Timeout</b>\n\n"
            f"📄 <b>File:</b> <code>{clean_file_name(file_name)}</code>\n"
            f"⚠️ <b>Status:</b> Sharing bot did not return the link within {timeout_seconds // 60} minutes.\n\n"
            f"Use <code>/status</code> to check active queue or send the file again."
        )
        await delete_status_messages(
            context,
            data["user_chat_id"],
            data.get("status_message_ids", [])
        )

    except asyncio.CancelledError:
        return
    except Exception as e:
        print(f"Timeout task error: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reply_clean(
        update.message,
        "🤖 <b>Auto Post System is Online</b>\n\n"
        "Available commands:\n"
        "• <code>/availablepost</code> — View saved posts\n"
        "• <code>/status</code> — Check active queue\n"
        "• <code>/clearqueue</code> — Clear stuck queue\n"
        "• <code>/restart</code> — Restart bot service\n"
        "• <code>/myid</code> — Get your Telegram ID"
    )

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    await reply_clean(
        update.message,
        f"🆔 <b>Your Telegram ID</b>\n\n"
        f"<code>{user.id}</code>\n\n"
        f"Add this ID in <code>config.py</code> under <code>ADMIN_IDS</code>."
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await reply_clean(
            update.message,
            "⛔ <b>Access Denied</b>\n\nOnly admin can use this command."
        )
        return

    uptime = datetime.now(ZoneInfo("Asia/Kolkata")) - BOT_STARTED_AT
    uptime_minutes = int(uptime.total_seconds() // 60)

    if not pending_files:
        queue_text = "No pending files."
    else:
        lines = []

        for idx, (fname, data) in enumerate(pending_files.items(), start=1):
            created_at = data.get("created_at", time.time())
            waiting_minutes = int((time.time() - created_at) // 60)

            lines.append(
                f"{idx}. <code>{clean_file_name(fname)}</code>\n"
                f"   Waiting: {waiting_minutes} min"
            )

        queue_text = "\n".join(lines)

    await reply_clean(
        update.message,
        f"📊 <b>Bot Status</b>\n\n"
        f"🟢 <b>State:</b> Running\n"
        f"⏱️ <b>Uptime:</b> {uptime_minutes} min\n"
        f"🕒 <b>IST Time:</b> {format_time_ist()}\n"
        f"📦 <b>Pending Queue:</b> {len(pending_files)}\n\n"
        f"{queue_text}"
    )


async def clearqueue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await reply_clean(update.message, "⛔ <b>Access Denied</b>\n\nOnly admin can use this command.")
        return

    for data in pending_files.values():
        task = data.get("timeout_task")
        if task:
            task.cancel()

    total = len(pending_files)
    pending_files.clear()

    await reply_clean(
        update.message,
        f"🧹 <b>Queue Cleared</b>\n\n"
        f"Removed <b>{total}</b> pending file(s).\n"
        f"The bot is ready for fresh uploads."
    )


async def restart_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await reply_clean(
            update.message,
            "⛔ <b>Access Denied</b>\n\nOnly admin can use this command."
        )
        return

    total = len(pending_files)

    for data in pending_files.values():
        task = data.get("timeout_task")
        if task:
            task.cancel()

    pending_files.clear()

    await reply_clean(
        update.message,
        f"🔄 <b>Bot Soft Restarted</b>\n\n"
        f"🧹 <b>Cleared Queue:</b> {total} pending file(s)\n"
        f"🟢 <b>Status:</b> Bot is still running\n"
        f"🕒 <b>Time:</b> {format_time_ist()}\n\n"
        f"You can send a fresh file now."
    )

def extract_episode_number(file_name):
    """
    Detects episode number from filenames like:
    Ep07
    E07
    Episode 07
    against the god s2 7 4k.mp4
    immortality season 5 23.mp4
    """

    name = file_name.lower()
    name = re.sub(r'\.(mp4|mkv|avi|mov)$', '', name, flags=re.IGNORECASE)

    patterns = [
        r'(?:episode|ep|e)\s*[-_. ]*\s*0*(\d{1,4})\b',
        r'\bs\s*\d+\s*[-_. ]+\s*0*(\d{1,4})\b',
        r'\bseason\s*\d+\s*[-_. ]+\s*0*(\d{1,4})\b',
        r'\b0*(\d{1,4})\b(?=[^\d]*(?:4k|1080p|2160p|720p|480p|$))'
    ]

    for pattern in patterns:
        match = re.search(pattern, name, re.IGNORECASE)

        if match:
            number = int(match.group(1))

            if number > 0:
                return str(number).zfill(2) if number < 10 else str(number)

    return None


def is_4k_file(file_name):
    return bool(re.search(r'\b4\s*k\b|2160p', file_name, re.IGNORECASE))


async def addpost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.edited_message or update.channel_post

    if not message:
        return

    if not message.photo:
        await message.reply_text("⚠️ Please attach the banner image and put the /addpost command in the caption!")
        return

    caption_html = message.caption_html or message.caption

    try:
        parts = caption_html.split('|', 4)

        name = re.sub(r'<[^>]+>', '', parts[1]).strip()
        wp_id = int(re.sub(r'<[^>]+>', '', parts[2]).strip())
        pattern = re.sub(r'<[^>]+>', '', parts[3]).strip().upper()
        tg_template = parts[4].strip()

        image_file_id = message.photo[-1].file_id

        await db.add_post(name, wp_id, pattern, tg_template, image_file_id)
        await reply_clean(
            message,
            f"✅ <b>Post Saved Successfully</b>\n\n"
            f"🎬 <b>Name:</b> {escape(name)}\n"
            f"🌐 <b>WordPress ID:</b> <code>{wp_id}</code>\n"
            f"🧩 <b>Pattern:</b> <code>{escape(pattern)}</code>"
        )

    except Exception as e:
        await reply_clean(
            message,
            f"❌ <b>Add Post Format Error</b>\n\n"
            f"<code>{escape(str(e))}</code>\n\n"
            f"Use format:\n"
            f"<code>/addpost | Name | WP_ID | D1 | Telegram Template</code>"
        )


async def availablepost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    posts = await db.get_all_posts()

    if not posts:
        await reply_clean(
            update.message,
            "📭 <b>No Posts Saved</b>\n\nUse <code>/addpost</code> to add your first WordPress post."
        )
        return

    lines = []
    for idx, p in enumerate(posts, start=1):
        lines.append(
            f"{idx}. <b>{escape(p['name'].title())}</b>\n"
            f"   WP ID: <code>{p['wp_post_id']}</code> | Pattern: <code>{escape(p['pattern'])}</code>"
        )

    await reply_clean(
        update.message,
        "📚 <b>Available WordPress Posts</b>\n\n" + "\n\n".join(lines)
    )


async def delpost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.replace("/delpost", "").strip()

    if not name:
        await reply_clean(
            update.message,
            "⚠️ <b>Missing Post Name</b>\n\nUse:\n<code>/delpost post name</code>"
        )
        return

    success = await db.delete_post(name)

    if success:
        await reply_clean(
            update.message,
            f"🗑️ <b>Post Deleted</b>\n\nRemoved: <code>{escape(name)}</code>"
        )
    else:
        await reply_clean(
            update.message,
            f"❌ <b>Post Not Found</b>\n\nName: <code>{escape(name)}</code>"
        )


async def process_final_link(update, context, post_data, file_name, link, file_size_str=None, user_chat_id=None, status_message_ids=None):
    chat_id = user_chat_id or update.effective_chat.id
    status_message_ids = status_message_ids or []
    episode_num = extract_episode_number(file_name)

    if not episode_num:
        await send_clean(
            context,
            chat_id,
            f"❌ <b>Episode Detection Failed</b>\n\n"
            f"📄 <b>File:</b> <code>{clean_file_name(file_name)}</code>\n\n"
            f"Use filename format like:\n"
            f"<code>against the god s2 07 4k.mp4</code>"
        )
        await delete_status_messages(context, chat_id, status_message_ids)
        return False

    file_is_4k = is_4k_file(file_name)
    pattern = str(post_data.get("pattern", "")).strip().upper()

    msg3 = await send_clean(
        context,
        chat_id,
        f"🔧 <b>Updating WordPress</b>\n\n"
        f"🎬 <b>Episode:</b> {escape(episode_num)}\n"
        f"📌 <b>Quality:</b> {'4K' if file_is_4k else '1080p / Main'}\n"
        f"🧩 <b>Pattern:</b> {escape(pattern)}\n"
        f"🌐 <b>Status:</b> Updating post content..."
    )

    status_message_ids.append(msg3.message_id)

    # Update this specific block inside process_final_link
    success, error_reason = await wp.add_episode_to_wp(
        post_id=post_data["wp_post_id"],
        pattern=pattern,
        episode_num=episode_num,
        link=link,
        is_4k=file_is_4k
    )

    if not success:
        await send_clean(
            context,
            chat_id,
            f"❌ <b>WordPress Update Failed</b>\n\n"
            f"🎬 <b>Episode:</b> {escape(episode_num)}\n"
            f"📄 <b>File:</b> <code>{clean_file_name(file_name)}</code>\n\n"
            f"⚠️ <b>Actual API Error:</b>\n"
            f"<code>{escape(error_reason)}</code>"
        )
        await delete_status_messages(context, chat_id, status_message_ids)
        return False

    channel_status = "Not required"

    try:
        if file_is_4k and pattern == "D1":
            tg_msg = TELEGRAM_4K_MSG.format(
                DONGHUA_NAME=post_data["name"].title(),
                FILE_SIZE=file_size_str or "Drive Link"
            )

            await context.bot.send_message(
                chat_id=config.CHANNEL_USERNAME,
                text=tg_msg,
                parse_mode='HTML'
            )

            channel_status = "4K notification sent"

        elif not file_is_4k:
            tg_msg = post_data["tg_template"].replace("{EPISODE_NUM}", episode_num).replace("{LINK}", link)
            image_id = post_data.get("image_file_id")

            if image_id:
                await context.bot.send_photo(
                    chat_id=config.CHANNEL_USERNAME,
                    photo=image_id,
                    caption=tg_msg,
                    parse_mode='HTML'
                )
            else:
                await context.bot.send_message(
                    chat_id=config.CHANNEL_USERNAME,
                    text=tg_msg,
                    parse_mode='HTML'
                )

            channel_status = "Episode post sent"

    except Exception as e:
        await send_clean(
            context,
            chat_id,
            f"⚠️ <b>WordPress Updated, But Channel Post Failed</b>\n\n"
            f"🎬 <b>Episode:</b> {escape(episode_num)}\n"
            f"🌐 <b>WordPress:</b> Updated\n"
            f"📣 <b>Channel:</b> Failed\n"
            f"⚠️ <b>Error:</b> <code>{escape(str(e))}</code>"
        )
        await delete_status_messages(context, chat_id, status_message_ids)
        return False

    await send_clean(
        context,
        chat_id,
        f"✅ <b>Automation Completed</b>\n\n"
        f"🎬 <b>Episode:</b> {escape(episode_num)}\n"
        f"📄 <b>File:</b> <code>{clean_file_name(file_name)}</code>\n"
        f"📌 <b>Quality:</b> {'4K' if file_is_4k else '1080p / Main'}\n"
        f"🌐 <b>WordPress:</b> Updated\n"
        f"📣 <b>Channel:</b> {escape(channel_status)}\n"
        f"🕒 <b>Time:</b> {format_time_ist()}"
    )

    await delete_status_messages(context, chat_id, status_message_ids)

    return True


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if not message:
        return

    sender_username = normalize_username(message.from_user.username if message.from_user else "")

    # If sharing bot sends link inside caption/document message, process it here
    if sender_username == get_file_bot_username():
        text_or_caption = message.text or message.caption or ""

        if re.search(r'((?:https?://)?(?:t\.me|telegram\.me)/[^\s<]+)', text_or_caption):
            await handle_bot_reply(update, context)
            return

    file = message.video or message.document

    if not file:
        return

    file_name = file.file_name or "unknown_file"

    raw_mb = (file.file_size or 0) / (1024 * 1024)

    if raw_mb >= 1024:
        file_size_str = f"{round(raw_mb / 1024, 2)} GB"
    else:
        file_size_str = f"{round(raw_mb, 2)} MB"

    matches = await db.get_post_by_name(file_name)

    if len(matches) > 1:
        await reply_clean(
            message,
            f"⚠️ <b>Multiple Posts Found</b>\n\n"
            f"📄 <b>File:</b> <code>{clean_file_name(file_name)}</code>\n\n"
            f"Please make the file name more specific."
        )
        return

    if len(matches) == 0:
        await reply_clean(
            message,
            f"❌ <b>No Matching Post Found</b>\n\n"
            f"📄 <b>File:</b> <code>{clean_file_name(file_name)}</code>\n\n"
            f"Check the saved post name using <code>/availablepost</code>."
        )
        return

    post_data = matches[0]
    status_message_ids = []

    msg1 = await reply_clean(
        message,
        f"📥 <b>File Received</b>\n\n"
        f"📄 <b>File:</b> <code>{clean_file_name(file_name)}</code>\n"
        f"📦 <b>Size:</b> {escape(file_size_str)}\n"
        f"🎬 <b>Matched Post:</b> {escape(post_data['name'].title())}\n\n"
        f"🔁 <b>Status:</b> Forwarding to sharing bot..."
    )

    status_message_ids.append(msg1.message_id)

    try:
        await message.forward(chat_id=f"@{config.FILE_BOT_USERNAME}")

    except Exception as e:
        await reply_clean(
            message,
            f"❌ <b>Forward Failed</b>\n\n"
            f"📄 <b>File:</b> <code>{clean_file_name(file_name)}</code>\n"
            f"⚠️ <b>Error:</b> <code>{escape(str(e))}</code>"
        )

        await delete_status_messages(context, message.chat_id, status_message_ids)
        return

    pending_files[file_name] = {
        "post_data": post_data,
        "file_name": file_name,
        "size_str": file_size_str,
        "user_chat_id": message.chat_id,
        "created_at": time.time(),
        "status_message_ids": status_message_ids
    }

    pending_files[file_name]["timeout_task"] = asyncio.create_task(
        expire_pending_file(file_name, context)
    )

    msg2 = await reply_clean(
        message,
        f"⏳ <b>Waiting for Download Link</b>\n\n"
        f"📄 <b>File:</b> <code>{clean_file_name(file_name)}</code>\n"
        f"🔗 <b>Status:</b> Sent to sharing bot\n\n"
        f"The WordPress post will update automatically once the link is received."
    )

    pending_files[file_name]["status_message_ids"].append(msg2.message_id)

async def handle_bot_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message

    if not message:
        return

    msg_text = message.text or message.caption or ""

    if not msg_text:
        return

    sender_username = normalize_username(message.from_user.username if message.from_user else "")

    # Case 1: Reply from Telegram file sharing bot
    if sender_username == get_file_bot_username() or is_file_log_chat(update):
        link_match = re.search(r'((?:https?://)?(?:t\.me|telegram\.me)/[^\s<]+)', msg_text)

        if not link_match:
            return

        link = link_match.group(1)

        if not link.startswith("http"):
            link = "https://" + link

        if not pending_files:
            if update.effective_chat and update.effective_chat.type == "private":
                await reply_clean(
                    message,
                    "⚠️ <b>Link Received, But Queue Is Empty</b>\n\n"
                    "No pending file was found. The old queue may have been cleared or the bot was restarted."
                )
            return
        
        selected_fname = None
        lower_text = msg_text.lower()

        for fname, data in pending_files.items():
            clean_fname = remove_video_extension(fname).lower()
            full_fname = fname.lower()
            drive_text = data.get("drive_text", "").lower()

            if clean_fname in lower_text or full_fname in lower_text:
                selected_fname = fname
                break

            if drive_text and clean_fname in drive_text and clean_fname in lower_text:
                selected_fname = fname
                break

        if not selected_fname and len(pending_files) == 1:
            selected_fname = next(iter(pending_files))

        if not selected_fname:
            if update.effective_chat and update.effective_chat.type == "private":
                await reply_clean(
                    message,
                    "⚠️ <b>Could Not Match Link to File</b>\n\n"
                    "Multiple files are pending, and the sharing bot response did not clearly match a filename.\n\n"
                    "Use <code>/status</code> and process one file at a time."
                )
            return

        data = pending_files[selected_fname]

        task = data.get("timeout_task")
        if task:
            task.cancel()

        success = await process_final_link(
            update=update,
            context=context,
            post_data=data["post_data"],
            file_name=data["file_name"],
            link=link,
            file_size_str=data["size_str"],
            user_chat_id=data["user_chat_id"],
            status_message_ids=data.get("status_message_ids", [])
        )

        if success:
            pending_files.pop(selected_fname, None)

        return

    # Case 2: Manual Google Drive link message from you
    # Case 2: Manual Google Drive link message from you
    drive_match = re.search(r'(https?://(?:drive\.google\.com|docs\.google\.com)/[^\s<]+)', msg_text)

    if drive_match:
        drive_link = drive_match.group(1)

        file_name = msg_text.replace(drive_link, "").strip()
        file_name = re.sub(r'^/drive\s*', '', file_name, flags=re.IGNORECASE).strip()
        file_name = file_name.strip(" |-:\n\t")

        if not file_name:
            await reply_clean(
                message,
                "❌ <b>Drive Link Found, But Filename Is Missing</b>\n\n"
                "Send in this format:\n\n"
                "<code>Tales of Herding Gods E83 4K.mkv | https://drive.google.com/file/d/xxxxx/view</code>"
            )
            return

        try:
            matches = await db.get_post_by_name(file_name)
        except Exception as e:
            await reply_clean(
                message,
                f"❌ <b>Database Connection Failed</b>\n\n"
                f"📄 <b>File:</b> <code>{clean_file_name(file_name)}</code>\n\n"
                f"⚠️ <b>Error:</b> <code>{escape(str(e))[:500]}</code>"
            )
            return

        if len(matches) > 1:
            await reply_clean(
                message,
                f"⚠️ <b>Multiple Posts Found</b>\n\n"
                f"📄 <b>File:</b> <code>{clean_file_name(file_name)}</code>\n\n"
                f"Make the filename more specific."
            )
            return

        if len(matches) == 0:
            await reply_clean(
                message,
                f"❌ <b>No Matching Post Found</b>\n\n"
                f"📄 <b>File:</b> <code>{clean_file_name(file_name)}</code>\n\n"
                f"Check saved posts using <code>/availablepost</code>."
            )
            return

        post_data = matches[0]
        clean_name = remove_video_extension(file_name)

        file_sharing_text = f"{clean_name} :- {drive_link}"
    
        status_message_ids = []
        
        msg1 = await reply_clean(
            message,
            f"📨 <b>Drive Link Received</b>\n\n"
            f"📄 <b>File:</b> <code>{clean_file_name(file_name)}</code>\n"
            f"🎬 <b>Matched Post:</b> {escape(post_data['name'].title())}\n\n"
            f"🔁 <b>Status:</b> Sending Drive text to file sharing bot..."
        )

        status_message_ids.append(msg1.message_id)

        try:
            sent_msg = await context.bot.send_message(
                chat_id=f"@{config.FILE_BOT_USERNAME}",
                text=file_sharing_text,
                disable_web_page_preview=True
            )

            await context.bot.send_message(
                chat_id=f"@{config.FILE_BOT_USERNAME}",
                text="/link",
                reply_to_message_id=sent_msg.message_id
            )
    
        except Exception as e:
            await reply_clean(
                message,
                f"❌ <b>File Sharing Bot Request Failed</b>\n\n"
                f"📄 <b>File:</b> <code>{clean_file_name(file_name)}</code>\n"
                f"⚠️ <b>Error:</b> <code>{escape(str(e))}</code>"
            )

            await delete_status_messages(context, message.chat_id, status_message_ids)
            return

        pending_files[file_name] = {
            "post_data": post_data,
            "file_name": file_name,
            "size_str": "Drive Link",
            "user_chat_id": message.chat_id,
            "created_at": time.time(),
            "status_message_ids": status_message_ids,
            "drive_mode": True,
            "drive_text": file_sharing_text
        }

        pending_files[file_name]["timeout_task"] = asyncio.create_task(
            expire_pending_file(file_name, context)
        )

        msg2 = await reply_clean(
            message,
            f"⏳ <b>Waiting for File Sharing Link</b>\n\n"
            f"📄 <b>File:</b> <code>{clean_file_name(file_name)}</code>\n"
            f"🔗 <b>Status:</b> Drive link sent to file sharing bot\n\n"
            f"WordPress will update after the generated file-sharing link is received."
        )

        pending_files[file_name]["status_message_ids"].append(msg2.message_id)

        return


async def wptest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await reply_clean(update.message, "⛔ <b>Access Denied</b>")
        return

    import aiohttp
    import config
    from html import escape

    post_id = context.args[0] if context.args else "7"

    wp_url = str(config.WP_URL).rstrip("/")
    wp_user = str(config.WP_USER).strip()
    wp_pass = "".join(str(config.WP_APP_PASS).split())

    headers = {
        "Accept": "application/json",
        "User-Agent": "AutoPostBot/1.0"
    }

    auth = aiohttp.BasicAuth(wp_user, wp_pass)

    async with aiohttp.ClientSession(headers=headers) as session:
        # 1. Test login
        me_url = f"{wp_url}/users/me?context=edit"
        async with session.get(me_url, auth=auth, allow_redirects=False) as resp:
            me_status = resp.status
            me_text = await resp.text()

            try:
                me_json = await resp.json(content_type=None)
            except Exception:
                me_json = {}

        # 2. Test post raw content
        post_url = f"{wp_url}/posts/{post_id}?context=edit"
        async with session.get(post_url, auth=auth, allow_redirects=False) as resp:
            post_status = resp.status
            post_text = await resp.text()

            try:
                post_json = await resp.json(content_type=None)
            except Exception:
                post_json = {}

    roles = me_json.get("roles", [])
    user_name = me_json.get("name") or me_json.get("slug") or "Unknown"

    has_raw = "raw" in post_json.get("content", {})
    title = post_json.get("title", {}).get("raw") or post_json.get("title", {}).get("rendered") or "No title"

    await reply_clean(
        update.message,
        f"🧪 <b>WordPress Render Test</b>\n\n"
        f"🌐 <b>WP_URL:</b> <code>{escape(wp_url)}</code>\n"
        f"👤 <b>WP_USER:</b> <code>{escape(wp_user)}</code>\n\n"
        f"🔐 <b>Auth Test:</b> <code>{me_status}</code>\n"
        f"👤 <b>Logged User:</b> <code>{escape(str(user_name))}</code>\n"
        f"🛡️ <b>Roles:</b> <code>{escape(str(roles))}</code>\n\n"
        f"📄 <b>Post Test:</b> <code>{post_status}</code>\n"
        f"🆔 <b>Post ID:</b> <code>{escape(str(post_id))}</code>\n"
        f"📝 <b>Title:</b> <code>{escape(str(title))[:150]}</code>\n"
        f"📦 <b>Has content.raw:</b> <code>{has_raw}</code>\n\n"
        f"🧾 <b>Post Response Preview:</b>\n"
        f"<code>{escape(post_text[:500])}</code>"
    )
