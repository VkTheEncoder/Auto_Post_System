from motor.motor_asyncio import AsyncIOMotorClient
import config

client = AsyncIOMotorClient(config.MONGO_URI)
db = client['auto_post_system_db']
posts_col = db['posts']

async def add_post(name, wp_post_id, pattern, tg_template):
    await posts_col.insert_one({
        "name": name.lower(),
        "wp_post_id": wp_post_id,
        "pattern": pattern,
        "tg_template": tg_template
    })

async def get_post_by_name(filename):
    # Simplistic search: look for the donghua name inside the filename
    # e.g., if filename is "Renegade Immortal Ep 23", it finds "renegade immortal"
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
