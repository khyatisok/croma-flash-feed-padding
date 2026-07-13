import os
import re
import json
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image
from lxml import etree

# =====================================================
# CONFIG
# =====================================================

CAMPAIGN_URL = "https://www.croma.com/campaign/24hrs-flash-sale-offers/c/7442"
GMC_FEED = "https://www.croma.com/gmcfeed.xml"

IMAGE_FOLDER = "images"
CACHE_FILE = "image_cache.json"

# Change this to your GitHub Pages URL
IMAGE_BASE_URL = "https://khyatisok.github.io/croma-flash-feed-padding/images"

# Resize product to 75% of original size
SCALE = 0.75

MAX_WORKERS = 6

# =====================================================

os.makedirs(IMAGE_FOLDER, exist_ok=True)

session = requests.Session()

print("Downloading campaign page...")

html = session.get(CAMPAIGN_URL, timeout=30).text

skus = set(re.findall(r'"sku"\s*:\s*"(\d+)"', html))

print(f"Found {len(skus)} Flash Sale SKUs")

print("Downloading GMC feed...")

xml = session.get(GMC_FEED, timeout=60).content

root = etree.fromstring(xml)

ns = {
    "g": "http://base.google.com/ns/1.0"
}

channel = root.find("channel")
items = channel.findall("item")

# -----------------------------------------------------
# Load cache
# -----------------------------------------------------

if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        cache = json.load(f)
else:
    cache = {}

new_cache = {}

tasks = []

removed = 0

# -----------------------------------------------------
# Filter products
# -----------------------------------------------------

for item in list(items):

    sku_node = item.find("g:id", ns)

    if sku_node is None:
        continue

    sku = sku_node.text.strip()

    if sku not in skus:
        channel.remove(item)
        removed += 1
        continue

    image_node = item.find("g:image_link", ns)

    if image_node is None:
        continue

    image_url = image_node.text.strip()

    new_cache[sku] = image_url

    new_url = f"{IMAGE_BASE_URL}/{sku}.png"

    image_node.text = new_url

    additional = item.find("g:additional_image_link", ns)

    if additional is not None:
        additional.text = new_url

    # only regenerate if image changed or doesn't exist

    image_path = os.path.join(IMAGE_FOLDER, f"{sku}.png")

    if (
        sku not in cache
        or cache[sku] != image_url
        or not os.path.exists(image_path)
    ):
        tasks.append((sku, image_url))

print(f"Removed {removed} products")

print(f"Images needing regeneration: {len(tasks)}")

# -----------------------------------------------------
# Delete old images
# -----------------------------------------------------

existing = {
    filename[:-4]
    for filename in os.listdir(IMAGE_FOLDER)
    if filename.endswith(".png")
}

for old in existing - skus:

    try:
        os.remove(os.path.join(IMAGE_FOLDER, old + ".png"))
        print(f"Deleted {old}.png")
    except:
        pass

# -----------------------------------------------------
# Image processor
# -----------------------------------------------------

def process_image(task):

    sku, image_url = task

    try:

        print(f"Downloading {sku}")

        response = session.get(image_url, timeout=30)

        response.raise_for_status()

        img = Image.open(BytesIO(response.content)).convert("RGBA")

        w, h = img.size

        new_w = int(w * SCALE)
        new_h = int(h * SCALE)

        resized = img.resize(
            (new_w, new_h),
            Image.LANCZOS
        )

        canvas = Image.new(
            "RGBA",
            (w, h),
            (255, 255, 255, 255)
        )

        x = (w - new_w) // 2
        y = (h - new_h) // 2

        canvas.paste(
            resized,
            (x, y),
            resized
        )

        output = os.path.join(
            IMAGE_FOLDER,
            f"{sku}.png"
        )

        canvas.save(
            output,
            optimize=True
        )

        print(f"Saved {sku}")

    except Exception as e:
        print(f"{sku}: {e}")

# -----------------------------------------------------
# Parallel processing
# -----------------------------------------------------

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    executor.map(process_image, tasks)

# -----------------------------------------------------
# Save XML
# -----------------------------------------------------

tree = etree.ElementTree(root)

tree.write(
    "flash_sale_feed_padding.xml",
    encoding="utf-8",
    xml_declaration=True,
    pretty_print=True
)

# -----------------------------------------------------
# Save cache
# -----------------------------------------------------

with open(CACHE_FILE, "w") as f:
    json.dump(
        new_cache,
        f,
        indent=2
    )

print("Saved image cache")

print("flash_sale_feed.xml generated successfully")

print("Done.")
