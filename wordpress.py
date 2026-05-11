import aiohttp
import config
from templates import D1_BLOCK, D2_BLOCK

async def get_wp_post(post_id):
    auth = aiohttp.BasicAuth(config.WP_USER, config.WP_APP_PASS)
    async with aiohttp.ClientSession() as session:
        # THE FIX: Added ?context=edit to grab RAW Gutenberg blocks
        async with session.get(f"{config.WP_URL}/posts/{post_id}?context=edit", auth=auth) as resp:
            if resp.status != 200:
                print(f"WP GET Error: {resp.status} - {await resp.text()}")
            return await resp.json()

async def update_wp_post(post_id, new_content):
    auth = aiohttp.BasicAuth(config.WP_USER, config.WP_APP_PASS)
    data = {"content": new_content, "status": "publish"}
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{config.WP_URL}/posts/{post_id}", json=data, auth=auth) as resp:
            if resp.status not in [200, 201]:
                print(f"WP POST Error: {resp.status} - {await resp.text()}")
            return await resp.json()

async def add_episode_to_wp(post_id, pattern, episode_num, link, is_4k=False):
    post_data = await get_wp_post(post_id)
    
    # Grab the raw content block
    content = post_data.get("content", {}).get("raw", "") 
    
    if not content:
        print("Error: Could not fetch WP Content. Check your WP_APP_PASS in config.")
        return

    if pattern == "D2":
        new_block = D2_BLOCK.replace("{EPISODE_NUM}", str(episode_num)).replace("{LINK_1080}", link)
        content += "\n" + new_block
    elif pattern == "D1":
        if is_4k:
            target = f"EPISODE {episode_num}"
            if target in content:
                content = content.replace(f"href=\"{{LINK_4K}}\"", f"href=\"{link}\"")
        else:
            new_block = D1_BLOCK.replace("{EPISODE_NUM}", str(episode_num)).replace("{LINK_1080}", link)
            content += "\n" + new_block

    await update_wp_post(post_id, content)
    print(f"✅ Successfully updated WordPress Post {post_id} with Episode {episode_num}")
