import asyncio
import os
import hashlib
from playwright.async_api import async_playwright
import aiohttp
from datetime import datetime

API_URL = "https://ppv.to/api/streams"

CUSTOM_HEADERS = [
    '#EXTVLCOPT:http-origin=https://ppv.to',
    '#EXTVLCOPT:http-referrer=https://ppv.to/',
    '#EXTVLCOPT:http-user-agent=Mozilla/5.0'
]

CATEGORY_LOGOS = {
    "Wrestling": "https://github.com/BuddyChewChew/ppv/blob/main/assets/wwe.png?raw=true",
    "Football": "https://github.com/BuddyChewChew/ppv/blob/main/assets/football.png?raw=true",
    "Basketball": "https://github.com/BuddyChewChew/ppv/blob/main/assets/nba.png?raw=true",
    "Baseball": "https://github.com/BuddyChewChew/ppv/blob/main/assets/baseball.png?raw=true",
    "Combat Sports": "https://github.com/BuddyChewChew/ppv/blob/main/assets/mma.png?raw=true",
    "Motorsports": "https://github.com/BuddyChewChew/ppv/blob/main/assets/f1.png?raw=true",
    "American Football": "https://github.com/BuddyChewChew/ppv/blob/main/assets/nfl.png?raw=true",
    "24/7 Streams": "https://github.com/BuddyChewChew/ppv/blob/main/assets/24-7.png?raw=true"
}

def hash_file(content: str):
    return hashlib.sha256(content.encode()).hexdigest()

async def fetch_api():
    retries = 3
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as session:
                async with session.get(API_URL) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    print(f"❌ API Error {resp.status}, retrying...")
        except Exception as e:
            print(f"⚠ Error fetching API attempt {attempt+1}: {e}")
        await asyncio.sleep(2)
    return None

async def grab_stream(page, url):
    stream_links = set()

    def handler(resp):
        if ".m3u8" in resp.url:
            stream_links.add(resp.url)

    page.on("response", handler)

    try:
        await page.goto(url, timeout=15000)
    except:
        print(f"❌ Failed load: {url}")
        return set()

    await asyncio.sleep(4)
    page.remove_listener("response", handler)
    return stream_links

def generate_playlist(streams, links):
    lines = ['#EXTM3U']

    for stream in streams:
        key = f"{stream['name']}::{stream['category']}::{stream['iframe']}"
        if key not in links or not links[key]:
            continue

        logo = CATEGORY_LOGOS.get(stream["category"], "")
        url = next(iter(links[key]))

        lines.append(f'#EXTINF:-1 tvg-logo="{logo}" group-title="{stream["category"]}",{stream["name"]}')
        lines.extend(CUSTOM_HEADERS)
        lines.append(url)

    return "\n".join(lines)

async def main():
    print("🔍 Fetching API...")
    data = await fetch_api()

    if not data or "streams" not in data:
        print("❌ API Returned no data.")
        return

    streams = []
    for category in data["streams"]:
        for stream in category.get("streams", []):
            if "iframe" in stream and stream["iframe"]:
                streams.append({
                    "name": stream["name"],
                    "category": category["category"],
                    "iframe": stream["iframe"]
                })

    print(f"📺 Found {len(streams)} streams")

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        page = await browser.new_page()

        links = {}
        for s in streams:
            print(f"➡ Scraping: {s['name']}")
            result = await grab_stream(page, s["iframe"])
            links[f"{s['name']}::{s['category']}::{s['iframe']}"] = result

        await browser.close()

    playlist = generate_playlist(streams, links)

    # detect change
    new_hash = hash_file(playlist)
    old_hash = hash_file(open("PPVLand.m3u8").read()) if os.path.exists("PPVLand.m3u8") else None

    if old_hash == new_hash:
        print("⚡ No changes — Playlist not updated")
        return

    print("💾 Writing updated playlist...")
    with open("PPVLand.m3u8", "w", encoding="utf-8") as f:
        f.write(playlist)

    print("✅ Playlist updated:", datetime.utcnow().isoformat())


if __name__ == "__main__":
    asyncio.run(main())
