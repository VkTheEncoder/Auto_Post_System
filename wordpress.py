import aiohttp
import config
from templates import D1_BLOCK, D2_BLOCK

async def get_wp_post(post_id):
    auth = aiohttp.BasicAuth(config.WP_USER, config.WP_APP_PASS)
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{config.WP_URL}/posts/{post_id}", auth=auth) as resp:
            return await resp.json()

async def update_wp_post(post_id, new_content):
    auth = aiohttp.BasicAuth(config.WP_USER, config.WP_APP_PASS)
    data = {"content": new_content, "status": "publish"} # "publish" updates the "Now" time implicitly if configured
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{config.WP_URL}/posts/{post_id}", json=data, auth=auth) as resp:
            return await resp.json()

async def add_episode_to_wp(post_id, pattern, episode_num, link, is_4k=False):
    post_data = await get_wp_post(post_id)
    content = post_data.get("content", {}).get("raw", "") or post_data.get("content", {}).get("rendered", "")

    if pattern == "D2":
        new_block = D2_BLOCK.replace("{EPISODE_NUM}", str(episode_num)).replace("{LINK_1080}", link)
        content += "\n" + new_block
    elif pattern == "D1":
        if is_4k:
            # We assume 1080p is already there. Replace the empty 4K link for this specific episode.
            # This is a basic string replace. For production, regex might be safer.
            target = f"EPISODE {episode_num}"
            if target in content:
                content = content.replace(f"href=\"{{LINK_4K}}\"", f"href=\"{link}\"")
        else:
            # First time adding D1 (1080p file)
            new_block = D1_BLOCK.replace("{EPISODE_NUM}", str(episode_num)).replace("{LINK_1080}", link)
            content += "\n" + new_block

    await update_wp_post(post_id, content)
