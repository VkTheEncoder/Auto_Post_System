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

async def addpost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # THE FIX: Safely grab the message whether it is new, edited, or a channel post
    message = update.message or update.edited_message or update.channel_post
    
    # If the message is completely invalid, exit safely without crashing
    if not message:
        return

    # Now use our safe 'message' variable instead of 'update.message'
    if not message.photo:
        await message.reply_text("⚠️ Please attach the banner image and put the /addpost command in the caption!")
        return

    caption_html = message.caption_html or message.caption
    
    try:
        parts = caption_html.split('|', 4)
        name = re.sub(r'<[^>]+>', '', parts[1]).strip()
        wp_id = int(re.sub(r'<[^>]+>', '', parts[2]).strip())
        pattern = re.sub(r'<[^>]+>', '', parts[3]).strip()
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

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = update.message.video or update.message.document
    file_name = file.file_name
    
    # EXACT FIX: Automatically format as MB or GB properly!
    raw_mb = file.file_size / (1024 * 1024)
    if raw_mb >= 1024:
        file_size_str = f"{round(raw_mb / 1024, 2)} GB"
    else:
        file_size_str = f"{round(raw_mb, 2)} MB"

    matches = await db.get_post_by_name(file_name)
    
    if len(matches) > 1:
        await update.message.reply_text(f"⚠️ Warning: Multiple posts found for {file_name}.")
        return
    elif len(matches) == 0:
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
    if update.message.from_user.username == config.FILE_BOT_USERNAME:
        msg_text = update.message.text
        
        if "https://t.me/" in msg_text:
            link = re.search(r'(https://t.me/[^\s]+)', msg_text).group(1)
            
            for fname, data in list(pending_files.items()):
                ep_match = re.search(r'[Ee]p?-?(\d+)', fname)
                ep_num = ep_match.group(1) if ep_match else "Unknown"
                is_4k = "4k" in fname.lower()
                
                await wp.add_episode_to_wp(
                    post_id=data['post_data']['wp_post_id'], 
                    pattern=data['post_data']['pattern'], 
                    episode_num=ep_num, 
                    link=link, 
                    is_4k=is_4k
                )
                
                if is_4k and data['post_data']['pattern'] == "D1":
                    # THE FIX IS APPLIED HERE:
                    tg_msg = TELEGRAM_4K_MSG.format(
                        DONGHUA_NAME=data['post_data']['name'].title(),
                        FILE_SIZE=data['size_str']
                    )
                    await context.bot.send_message(chat_id=config.CHANNEL_USERNAME, text=tg_msg, parse_mode='HTML')
                elif not is_4k:
                    tg_msg = data['post_data']['tg_template'].replace("{EPISODE_NUM}", ep_num).replace("{LINK}", link)
                    image_id = data['post_data'].get('image_file_id')
                    
                    if image_id:
                        await context.bot.send_photo(chat_id=config.CHANNEL_USERNAME, photo=image_id, caption=tg_msg, parse_mode='HTML')
                    else:
                        await context.bot.send_message(chat_id=config.CHANNEL_USERNAME, text=tg_msg, parse_mode='HTML')
                
                await context.bot.send_message(chat_id=data['user_chat_id'], text=f"✅ Automation complete for {fname}!")
                del pending_files[fname]
                break
