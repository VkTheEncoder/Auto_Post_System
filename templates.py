# These are simplified Gutenberg HTML blocks. You may need to copy the exact HTML 
# from your WordPress text editor for your specific button styling.
D1_BLOCK = """
<div class="wp-block-group">
    <p><strong>EPISODE {EPISODE_NUM}</strong></p>
    <div class="wp-block-buttons">
        <div class="wp-block-button"><a class="wp-block-button__link" href="{LINK_1080}">1080p Download</a></div>
        <div class="wp-block-button"><a class="wp-block-button__link" href="{LINK_4K}">4K Download</a></div>
    </div>
</div>
"""

D2_BLOCK = """
<div class="wp-block-group">
    <p><strong>EPISODE {EPISODE_NUM}</strong></p>
    <div class="wp-block-buttons">
        <div class="wp-block-button"><a class="wp-block-button__link" href="{LINK_1080}">Download</a></div>
    </div>
</div>
"""

TELEGRAM_4K_MSG = """
{DONGHUA_NAME} 4K (Hardsub) quality Added ✅

Size :- {FILE_SIZE} 💀 

Now Enjoy Highest Quality 😌🔥
"""
