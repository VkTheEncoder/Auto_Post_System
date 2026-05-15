import aiohttp
import config
import re
from templates import D1_BLOCK, D2_BLOCK
from datetime import datetime
from zoneinfo import ZoneInfo


async def get_wp_post(post_id):
    auth = aiohttp.BasicAuth(config.WP_USER, config.WP_APP_PASS)

    async with aiohttp.ClientSession() as session:
        async with session.get(f"{config.WP_URL}/posts/{post_id}?context=edit", auth=auth) as resp:
            if resp.status != 200:
                print(f"WP GET Error: {resp.status} - {await resp.text()}")
                return None

            return await resp.json()


async def update_wp_post(post_id, new_content):
    auth = aiohttp.BasicAuth(config.WP_USER, config.WP_APP_PASS)

    current_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%dT%H:%M:%S")

    data = {
        "content": new_content,
        "status": "publish",
        "date": current_time
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{config.WP_URL}/posts/{post_id}", json=data, auth=auth) as resp:
            response_text = await resp.text()

            if resp.status not in [200, 201]:
                print(f"WP POST Error: {resp.status} - {response_text}")
                return False

            return True


def find_episode_block(content, episode_num):
    """
    Finds the full Gutenberg columns block for a specific episode.
    Supports EPISODE 7 and EPISODE 07 both.
    """

    episode_digits = re.sub(r"\D", "", str(episode_num))

    if not episode_digits:
        return None

    episode_number = int(episode_digits)

    heading_regex = re.compile(
        rf"<h[1-6][^>]*>\s*EPISODE\s+0*{episode_number}\s*</h[1-6]>",
        re.IGNORECASE
    )

    heading_match = heading_regex.search(content)

    if not heading_match:
        return None

    block_start = content.rfind("<!-- wp:columns", 0, heading_match.start())

    if block_start == -1:
        block_start = content.rfind('<div class="wp-block-columns"', 0, heading_match.start())

    if block_start == -1:
        block_start = heading_match.start()

    block_end_marker = "<!-- /wp:columns -->"
    block_end = content.find(block_end_marker, heading_match.end())

    if block_end != -1:
        block_end += len(block_end_marker)
    else:
        next_block = content.find("<!-- wp:columns", heading_match.end())
        block_end = next_block if next_block != -1 else len(content)

    return block_start, block_end


def update_4k_button_in_block(block_html, link):
    """
    Updates the 4K Download button even if WordPress added extra attributes.
    Works with:
    <a class="...">4K Download</a>
    <a class="..." href="">4K Download</a>
    <a class="..." rel="nofollow">4K Download</a>
    """

    anchor_regex = re.compile(
        r'<a\b(?P<attrs>[^>]*)>\s*4\s*K\s*Download\s*</a>',
        re.IGNORECASE
    )

    def replace_anchor(match):
        attrs = match.group("attrs")

        if re.search(r'\shref\s*=', attrs, re.IGNORECASE):
            attrs = re.sub(
                r'\shref\s*=\s*(".*?"|\'.*?\'|[^\s>]+)',
                f' href="{link}"',
                attrs,
                count=1,
                flags=re.IGNORECASE
            )
        else:
            attrs += f' href="{link}"'

        if re.search(r'\srel\s*=', attrs, re.IGNORECASE):
            attrs = re.sub(
                r'\srel\s*=\s*(".*?"|\'.*?\'|[^\s>]+)',
                ' rel="nofollow"',
                attrs,
                count=1,
                flags=re.IGNORECASE
            )
        else:
            attrs += ' rel="nofollow"'

        return f'<a{attrs}>4K Download</a>'

    updated_block, count = anchor_regex.subn(replace_anchor, block_html, count=1)

    return updated_block, count


async def add_episode_to_wp(post_id, pattern, episode_num, link, is_4k=False):
    post_data = await get_wp_post(post_id)

    if not post_data:
        print("Error: Could not fetch WP post.")
        return False

    content = post_data.get("content", {}).get("raw", "")

    if not content:
        print("Error: Could not fetch raw Gutenberg content.")
        return False

    pattern = (pattern or "").strip().upper()
    episode_num = str(episode_num).strip()

    if is_4k:
        if pattern != "D1":
            print("Error: 4K update is only supported for D1 pattern.")
            return False

        block_position = find_episode_block(content, episode_num)

        if not block_position:
            print(f"Error: Episode {episode_num} block not found for 4K update.")
            return False

        start, end = block_position
        old_block = content[start:end]

        updated_block, count = update_4k_button_in_block(old_block, link)

        if count == 0:
            print(f"Error: 4K Download button not found inside Episode {episode_num} block.")
            return False

        content = content[:start] + updated_block + content[end:]

    else:
        if pattern == "D2":
            new_block = D2_BLOCK.replace("{EPISODE_NUM}", episode_num).replace("{LINK_1080}", link)
            content = content.rstrip() + "\n\n" + new_block + "\n\n"

        elif pattern == "D1":
            new_block = D1_BLOCK.replace("{EPISODE_NUM}", episode_num).replace("{LINK_1080}", link)
            content = content.rstrip() + "\n\n" + new_block + "\n\n"

        else:
            print(f"Error: Unknown pattern '{pattern}'. Use D1 or D2.")
            return False

    success = await update_wp_post(post_id, content)

    if success:
        print(f"✅ Successfully updated WordPress Post {post_id} with Episode {episode_num}")
        return True

    return False
