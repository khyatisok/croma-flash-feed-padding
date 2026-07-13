import os
import re
from io import BytesIO

import requests
from PIL import Image
from lxml import etree

# -----------------------
# CONFIG
# -----------------------

CAMPAIGN_URL = "https://www.croma.com/campaign/24hrs-flash-sale-offers/c/7442"
GMC_FEED = "https://www.croma.com/gmcfeed.xml"

# Your GitHub Pages URL
IMAGE_BASE_URL = "https://YOUR_USERNAME.github.io/YOUR_REPO/images"

IMAGE_FOLDER = "images"

# Product size after resize
SCALE = 0.85

# -----------------------

os.makedirs(IMAGE_FOLDER, exist_ok=True)

print("Downloading campaign page...")

html = requests.get(CAMPAIGN_URL).text

skus = set(re.findall(r'"sku"\s*:\s*"(\d+)"', html))

print(f"Found {len(skus)} live SKUs")

print("Downloading GMC feed...")

xml = requests.get(GMC_FEED).content

root = etree.fromstring(xml)

ns = {
    "g": "http://base.google.com/ns/1.0"
}

channel = root.find("channel")

items = channel.findall("item")

removed = 0

for item in list(items):

    sku = item.find("g:id", ns)

    if sku is None:
        continue

    sku = sku.text

    if sku not in skus:
        channel.remove(item)
        removed += 1
        continue

    image_tag = item.find("g:image_link", ns)

    if image_tag is None:
        continue

    image_url = image_tag.text

    print(f"Processing {sku}")

    try:

        response = requests.get(image_url, timeout=30)

        img = Image.open(BytesIO(response.content)).convert("RGBA")

        w, h = img.size

        new_w = int(w * SCALE)
        new_h = int(h * SCALE)

        resized = img.resize((new_w, new_h), Image.LANCZOS)

        canvas = Image.new(
            "RGBA",
            (w, h),
            (255, 255, 255, 255)
        )

        x = (w - new_w) // 2
        y = (h - new_h) // 2

        canvas.paste(resized, (x, y), resized)

        output_path = os.path.join(IMAGE_FOLDER, f"{sku}.png")

        canvas.save(output_path)

        new_url = f"{IMAGE_BASE_URL}/{sku}.png"

        image_tag.text = new_url

        additional = item.find("g:additional_image_link", ns)

        if additional is not None:
            additional.text = new_url

    except Exception as e:
        print(e)

print(f"Removed {removed} products")

tree = etree.ElementTree(root)

tree.write(
    "flash_sale_feed.xml",
    encoding="utf-8",
    xml_declaration=True,
    pretty_print=True
)

print("Done.")
