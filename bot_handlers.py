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
    if not update.message.photo:
        await update.message.reply_text("⚠️ Please attach the banner image and put the /addpost command in the caption!")
        return

    # THE FIX: Grab the HTML formatted text to save your styles!
    caption_html = update.message.caption_html or update.message.caption
    
    try:
        parts = caption_html.split('|', 4)
        
        # Clean HTML tags off the settings, but leave them on the Template!
        name = re.sub(r'<[^>]+>', '', parts[1]).strip()
        wp_id = int(re.sub(r'<[^>]+>', '', parts[2]).strip())
        pattern = re.sub(r'<[^>]+>', '', parts[3]).strip()
        tg_template = parts[4].strip() # Styles kept safely here!
        
        image_file_id = update.message.photo[-1].file_id 
        
        await db.add_post(name, wp_id, pattern, tg_template, image_file_id)
        await update.message.reply_text(f"✅ Successfully saved {name} (with styling) into the database.")
    except Exception as e:
        await update.message.reply_text(f"Format error: {e}")

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
    file_size_mb = round(file.file_size / (1024 * 1024), 2)

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
        "size_mb": file_size_mb,
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
                
                # THE FIX: parse_mode='HTML' added below
                if is_4k and data['post_data']['pattern'] == "D1":
                    tg_msg = TELEGRAM_4K_MSG.format(
                        DONGHUA_NAME=data['post_data']['name'].title(),
                        FILE_SIZE=f"{data['size_mb']} MB"
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
