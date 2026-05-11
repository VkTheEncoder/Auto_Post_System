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
    content = post_data.get("content", {}).get("raw", "") 
    
    if not content:
        print("Error: Could not fetch WP Content.")
        return

    if pattern == "D2":
        new_block = D2_BLOCK.replace("{EPISODE_NUM}", str(episode_num)).replace("{LINK_1080}", link)
        content = content.strip() + "\n\n" + new_block + "\n\n"
        
    elif pattern == "D1":
        if is_4k:
            # Safely find the specific episode and inject the href into the empty 4K button
            ep_marker = f"EPISODE {episode_num}</h3>"
            if ep_marker in content:
                parts = content.split(ep_marker, 1)
                parts[1] = parts[1].replace(
                    '<a class="wp-block-button__link wp-element-button">4K Download</a>',
                    f'<a class="wp-block-button__link wp-element-button" href="{link}">4K Download</a>',
                    1
                )
                content = parts[0] + ep_marker + parts[1]
        else:
            # Initial 1080p post creates the block
            new_block = D1_BLOCK.replace("{EPISODE_NUM}", str(episode_num)).replace("{LINK_1080}", link)
            content = content.strip() + "\n\n" + new_block + "\n\n"

    await update_wp_post(post_id, content)
    print(f"✅ Successfully updated WordPress Post {post_id} with Episode {episode_num}")
