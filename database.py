import certifi
import re
from motor.motor_asyncio import AsyncIOMotorClient
import config

# Use certifi to provide the required SSL certificates for Linux
client = AsyncIOMotorClient(config.MONGO_URI, tlsCAFile=certifi.where())

db = client['donghua_db']
posts_col = db['posts']

async def add_post(name, wp_post_id, pattern, tg_template, image_file_id):
    await posts_col.insert_one({
        "name": name.lower(),
        "wp_post_id": wp_post_id,
        "pattern": pattern,
        "tg_template": tg_template,
        "image_file_id": image_file_id
    })

async def get_post_by_name(filename):
    # 1. Clean the filename to lowercase and remove extensions
    clean_filename = filename.lower().replace('.mkv', '').replace('.mp4', '')
    
    # 2. Extract ONLY the Donghua Name using Regex
    # This chops off anything after a hyphen, "S5", "Season 5", "Ep", etc.
    parts = re.split(r'\s*-\s*|\s+s\d+|\s+season\s*\d+|\s+ep?-?\d+', clean_filename)
    core_name = parts[0].strip()
    
    cursor = posts_col.find()
    matches = []
    async for post in cursor:
        db_name = post['name']
        
        # 3. Check if the core name ("immortality") is inside the DB name ("immortality season 5")
        # Or check if the DB name is inside the core name (just to be completely safe)
        if core_name in db_name or db_name in core_name:
            matches.append(post)
            
    return matches

async def get_all_posts():
    return await posts_col.find().to_list(length=None)

async def delete_post(name):
    result = await posts_col.delete_one({"name": name.lower()})
    return result.deleted_count > 0
