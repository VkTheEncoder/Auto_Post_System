import certifi
from motor.motor_asyncio import AsyncIOMotorClient
import config

# Use certifi to provide the required SSL certificates for Linux
client = AsyncIOMotorClient(config.MONGO_URI, tlsCAFile=certifi.where())

db = client['auto_post_system_db']
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
    cursor = posts_col.find()
    matches = []
    async for post in cursor:
        if post['name'] in filename.lower():
            matches.append(post)
    return matches

async def get_all_posts():
    return await posts_col.find().to_list(length=None)

async def delete_post(name):
    result = await posts_col.delete_one({"name": name.lower()})
    return result.deleted_count > 0
