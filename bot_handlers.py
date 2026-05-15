import re
from telegram import Update
from telegram.ext import ContextTypes
import config
import database as db
import wordpress as wp
from templates import TELEGRAM_4K_MSG

pending_files = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is alive and ready for automation.")


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
        await message.reply_text(f"✅ Successfully saved {name} (with styling) into the database.")

    except Exception as e:
        await message.reply_text(f"Format error: {e}")


async def availablepost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    posts = await db.get_all_posts()
    msg = "Available Posts:\n" + "\n".join([f"- {p['name']}" for p in posts])
    await update.message.reply_text(msg)


async def delpost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.replace("/delpost", "").strip()
    success = await db.delete_post(name)

    if success:
        await update.message.reply_text(f"Deleted {name}.")
    else:
        await update.message.reply_text("Post not found.")


async def process_final_link(update, context, post_data, file_name, link, file_size_str=None):
    episode_num = extract_episode_number(file_name)

    if not episode_num:
        await update.message.reply_text(
            f"❌ Could not detect episode number from filename:\n{file_name}\n\n"
            f"Use a filename like: against the god s2 07 4k.mp4"
        )
        return False

    file_is_4k = is_4k_file(file_name)
    pattern = str(post_data.get("pattern", "")).strip().upper()

    success = await wp.add_episode_to_wp(
        post_id=post_data["wp_post_id"],
        pattern=pattern,
        episode_num=episode_num,
        link=link,
        is_4k=file_is_4k
    )

    if not success:
        await update.message.reply_text(
            f"❌ WordPress update failed for Episode {episode_num}.\n"
            f"Reason can be:\n"
            f"- Episode block not found\n"
            f"- 4K button not found\n"
            f"- Wrong pattern selected\n"
            f"- WordPress API rejected the update"
        )
        return False

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

    await update.message.reply_text(f"✅ Automation complete for {file_name}!")
    return True


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.video or update.message.document
    file_name = file.file_name or "unknown_file"

    raw_mb = file.file_size / (1024 * 1024)

    if raw_mb >= 1024:
        file_size_str = f"{round(raw_mb / 1024, 2)} GB"
    else:
        file_size_str = f"{round(raw_mb, 2)} MB"

    matches = await db.get_post_by_name(file_name)

    if len(matches) > 1:
        await update.message.reply_text(f"⚠️ Warning: Multiple posts found for {file_name}.")
        return

    if len(matches) == 0:
        await update.message.reply_text("No matching post found in database.")
        return

    post_data = matches[0]

    forwarded_msg = await update.message.forward(chat_id=f"@{config.FILE_BOT_USERNAME}")

    pending_files[file_name] = {
        "post_data": post_data,
        "file_name": file_name,
        "size_str": file_size_str,
        "user_chat_id": update.message.chat_id
    }

    await update.message.reply_text(f"File forwarded to sharing bot. Waiting for link for {file_name}...")


async def handle_bot_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message

    if not message or not message.text:
        return

    msg_text = message.text
    sender_username = message.from_user.username or ""

    # Case 1: Reply from Telegram file sharing bot
    if sender_username == config.FILE_BOT_USERNAME:
        link_match = re.search(r'(https://t\.me/[^\s]+)', msg_text)

        if not link_match:
            return

        link = link_match.group(1)

        if not pending_files:
            await message.reply_text("⚠️ Received a file link, but no pending file was found.")
            return

        selected_fname = None
        lower_text = msg_text.lower()

        for fname in pending_files.keys():
            clean_fname = fname.lower().replace(".mp4", "").replace(".mkv", "").strip()

            if clean_fname in lower_text or fname.lower() in lower_text:
                selected_fname = fname
                break

        if not selected_fname:
            selected_fname = next(iter(pending_files))

        data = pending_files[selected_fname]

        success = await process_final_link(
            update=update,
            context=context,
            post_data=data["post_data"],
            file_name=data["file_name"],
            link=link,
            file_size_str=data["size_str"]
        )

        if success:
            del pending_files[selected_fname]

        return

    # Case 2: Manual Google Drive link message from you
    drive_match = re.search(r'(https?://(?:drive\.google\.com|docs\.google\.com)/[^\s]+)', msg_text)

    if drive_match:
        drive_link = drive_match.group(1)

        file_name = msg_text.replace(drive_link, "").strip()
        file_name = re.sub(r'^/drive\s*', '', file_name, flags=re.IGNORECASE).strip()
        file_name = file_name.strip(" |-:\n\t")

        if not file_name:
            await message.reply_text(
                "❌ Drive link found, but filename is missing.\n\n"
                "Send like this:\n"
                "against the god s2 07 1080p.mp4 | https://drive.google.com/file/d/xxxxx/view\n\n"
                "For 4K:\n"
                "against the god s2 07 4k.mp4 | https://drive.google.com/file/d/xxxxx/view"
            )
            return

        matches = await db.get_post_by_name(file_name)

        if len(matches) > 1:
            await message.reply_text(f"⚠️ Multiple posts found for {file_name}. Make the filename more specific.")
            return

        if len(matches) == 0:
            await message.reply_text(f"❌ No matching post found in database for:\n{file_name}")
            return

        await process_final_link(
            update=update,
            context=context,
            post_data=matches[0],
            file_name=file_name,
            link=drive_link,
            file_size_str="Drive Link"
        )
