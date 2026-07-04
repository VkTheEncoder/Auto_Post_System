import aiohttp
import config
import re
from templates import D1_BLOCK, D2_BLOCK
from datetime import datetime
from zoneinfo import ZoneInfo


def wp_base_url():
    return str(config.WP_URL).rstrip("/")


def wp_auth():
    username = str(config.WP_USER).strip()

    # WordPress app passwords are shown with spaces.
    # Removing spaces is safe and avoids Render/env copy issues.
    password = str(config.WP_APP_PASS).replace(" ", "").strip()

    return aiohttp.BasicAuth(username, password)


def wp_headers():
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "AutoPostBot/1.0"
    }


async def get_wp_post(post_id):
    url = f"{wp_base_url()}/posts/{post_id}?context=edit"

    async with aiohttp.ClientSession(headers=wp_headers()) as session:
        async with session.get(
            url,
            auth=wp_auth(),
            allow_redirects=False
        ) as resp:

            text = await resp.text()

            if resp.status in [301, 302, 307, 308]:
                return False, f"Redirect error {resp.status}. Check WP_URL. URL used: {url}"

            if resp.status != 200:
                return False, f"GET {resp.status}: {text[:500]}"

            try:
                data = await resp.json(content_type=None)
            except Exception:
                return False, f"GET returned non-JSON response: {text[:500]}"

            content = data.get("content", {})

            if "raw" not in content:
                return False, (
                    "Missing content.raw from WordPress API. "
                    "This means WordPress did not treat this request as an authenticated editor/admin request. "
                    "Check Render WP_USER/WP_APP_PASS, user role, and Authorization header."
                )

            return True, data


async def update_wp_post(post_id, new_content):
    url = f"{wp_base_url()}/posts/{post_id}"

    current_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%dT%H:%M:%S")

    data = {
        "content": new_content,
        "status": "publish",
        "date": current_time
    }

    async with aiohttp.ClientSession(headers=wp_headers()) as session:
        async with session.post(
            url,
            json=data,
            auth=wp_auth(),
            allow_redirects=False
        ) as resp:

            text = await resp.text()

            if resp.status in [301, 302, 307, 308]:
                return False, f"Redirect error {resp.status}. Check WP_URL. URL used: {url}"

            if resp.status not in [200, 201]:
                return False, f"POST {resp.status}: {text[:500]}"

            return True, "Success"


async def add_episode_to_wp(post_id, pattern, episode_num, link, is_4k=False):
    success, post_data = await get_wp_post(post_id)

    if not success:
        return False, post_data

    content = post_data.get("content", {}).get("raw", "")

    if not content:
        return False, "Post content.raw is empty."

    pattern = (pattern or "").strip().upper()
    episode_num = str(episode_num).strip()

    if is_4k:
        if pattern != "D1":
            return False, "Error: 4K update is only supported for D1 pattern."

        block_position = find_episode_block(content, episode_num)

        if not block_position:
            return False, f"Error: Episode {episode_num} block not found."

        start, end = block_position
        old_block = content[start:end]

        updated_block, count = update_4k_button_in_block(old_block, link)

        if count == 0:
            return False, f"Error: 4K Download button not found inside Episode {episode_num} block."

        content = content[:start] + updated_block + content[end:]

    else:
        if pattern == "D2":
            new_block = D2_BLOCK.replace("{EPISODE_NUM}", episode_num).replace("{LINK_1080}", link)
            content = content.rstrip() + "\n\n" + new_block + "\n\n"

        elif pattern == "D1":
            new_block = D1_BLOCK.replace("{EPISODE_NUM}", episode_num).replace("{LINK_1080}", link)
            content = content.rstrip() + "\n\n" + new_block + "\n\n"

        else:
            return False, f"Error: Unknown pattern '{pattern}'. Use D1 or D2."

    success, update_msg = await update_wp_post(post_id, content)

    if not success:
        return False, update_msg

    return True, "Success"


def find_episode_block(content, episode_num):
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
