import asyncio
from playwright.async_api import async_playwright
import aiohttp
from datetime import datetime
from zoneinfo import ZoneInfo
import platform

API_URL = "https://ppv.to/api/streams"

CUSTOM_HEADERS = [
    '#EXTVLCOPT:http-origin=https://ppvs.su',
    '#EXTVLCOPT:http-referrer=https://ppvs.su/',
    '#EXTVLCOPT:http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0'
]

ALLOWED_CATEGORIES = {
    "24/7 Streams", "Wrestling", "Football", "Basketball", "Baseball",
    "Combat Sports", "Motorsports", "Miscellaneous", "Boxing", "Darts",
    "American Football", "Ice Hockey"
}

CATEGORY_LOGOS = {
    "24/7 Streams": "https://github.com/BuddyChewChew/ppv/blob/main/assets/24-7.png?raw=true",
    "Wrestling": "https://github.com/BuddyChewChew/ppv/blob/main/assets/wwe.png?raw=true",
    "Football": "https://github.com/BuddyChewChew/ppv/blob/main/assets/football.png?raw=true",
    "Basketball": "https://github.com/BuddyChewChew/ppv/blob/main/assets/nba.png?raw=true",
    "Baseball": "https://github.com/BuddyChewChew/ppv/blob/main/assets/baseball.png?raw=true",
    "Combat Sports": "https://github.com/BuddyChewChew/ppv/blob/main/assets/mma.png?raw=true",
    "Motorsports": "https://github.com/BuddyChewChew/ppv/blob/main/assets/f1.png?raw=true",
    "Miscellaneous": "https://github.com/BuddyChewChew/ppv/blob/main/assets/24-7.png?raw=true",
    "Boxing": "https://github.com/BuddyChewChew/ppv/blob/main/assets/boxing.png?raw=true",
    "Darts": "https://github.com/BuddyChewChew/ppv/blob/main/assets/darts.png?raw=true",
    "Ice Hockey": "https://github.com/BuddyChewChew/ppv/blob/main/assets/hockey.png?raw=true",
    "American Football": "https://github.com/BuddyChewChew/ppv/blob/main/assets/nfl.png?raw=true"
}

CATEGORY_TVG_IDS = {
    "24/7 Streams": "24.7.Dummy.us",
    "Football": "Soccer.Dummy.us",
    "Wrestling": "PPV.EVENTS.Dummy.us",
    "Combat Sports": "PPV.EVENTS.Dummy.us",
    "Baseball": "MLB.Baseball.Dummy.us",
    "Basketball": "Basketball.Dummy.us",
    "Motorsports": "Racing.Dummy.us",
    "Miscellaneous": "PPV.EVENTS.Dummy.us",
    "Boxing": "PPV.EVENTS.Dummy.us",
    "Ice Hockey": "NHL.Hockey.Dummy.us",
    "Darts": "Darts.Dummy.us",
    "American Football": "NFL.Dummy.us"
}

GROUP_RENAME_MAP = {
    "24/7 Streams": "PPVLand - Live Channels 24/7",
    "Wrestling": "PPVLand - Wrestling Events",
    "Football": "PPVLand - Global Football Streams",
    "Basketball": "PPVLand - Basketball Hub",
    "Baseball": "PPVLand - Baseball Action HD",
    "Combat Sports": "PPVLand - MMA & Fight Nights",
    "Motorsports": "PPVLand - Motorsport Live",
    "Miscellaneous": "PPVLand - Random Events",
    "Boxing": "PPVLand - Boxing",
    "Ice Hockey": "PPVLand - Ice Hockey",
    "Darts": "PPVLand - Darts",
    "American Football": "PPVLand - NFL Action"
}


async def check_m3u8_url(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://ppvs.su",
            "Origin": "https://ppvs.su"
        }
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                return resp.status == 200
    except Exception as e:
        print(f"❌ Error checking {url}: {e}")
        return False


async def get_streams():
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            print(f"🌐 Fetching streams from {API_URL}")
            async with session.get(API_URL) as resp:
                print(f"🔍 Response status: {resp.status}")
                if resp.status != 200:
                    error_text = await resp.text()
                    print(f"❌ API Error Response:\n{error_text[:500]}")
                    return None
                return await resp.json()
    except Exception as e:
        print(f"❌ Error in get_streams: {str(e)}")
        return None


async def grab_m3u8_from_iframe(page, iframe_url):
    found_streams = set()

    def handle_response(response):
        if ".m3u8" in response.url:
            found_streams.add(response.url)

    page.on("response", handle_response)
    print(f"🌐 Navigating to iframe: {iframe_url}")

    try:
        await page.goto(iframe_url, timeout=15000)
    except Exception as e:
        print(f"❌ Failed to load iframe: {e}")
        page.remove_listener("response", handle_response)
        return set()

    await asyncio.sleep(2)

    try:
        box = page.viewport_size or {"width": 1280, "height": 720}
        cx, cy = box["width"] / 2, box["height"] / 2
        for i in range(4):
            if found_streams:
                break
            print(f"🖱️ Click #{i + 1}")
            try:
                await page.mouse.click(cx, cy)
            except Exception:
                pass
            await asyncio.sleep(0.3)
    except Exception as e:
        print(f"❌ Mouse click error: {e}")

    print("⏳ Waiting 5s...")
    await asyncio.sleep(5)
    page.remove_listener("response", handle_response)

    valid_urls = set()
    for url in found_streams:
        if await check_m3u8_url(url):
            valid_urls.add(url)
        else:
            print(f"❌ Rejected URL: {url}")

    return valid_urls


def build_m3u(streams, url_map):
    lines = ['#EXTM3U url-tvg="https://epgshare01.online/epgshare01/epg_ripper_DUMMY_CHANNELS.xml.gz"']
    seen_names = set()

    for s in streams:
        name_lower = s["name"].strip().lower()
        if name_lower in seen_names:
            continue
        seen_names.add(name_lower)

        key = f"{s['name']}::{s['category']}::{s['iframe']}"
        urls = url_map.get(key, [])

        if not urls:
            print(f"⚠️ No playable URL for: {s['name']}")
            continue

        category = s["category"]
        logo = CATEGORY_LOGOS.get(category, "")
        tvg_id = CATEGORY_TVG_IDS.get(category, "Sports.Dummy.us")
        group = GROUP_RENAME_MAP.get(category, category)
        url = next(iter(urls))

        lines.append(f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-logo="{logo}" group-title="{group}",{s["name"]}')
        lines.extend(CUSTOM_HEADERS)
        lines.append(url)

    return "\n".join(lines)


async def main():
    print("🚀 Starting PPV Stream Scraper")
    data = await get_streams()

    if not data or "streams" not in data:
        print("❌ API returned invalid or empty structure")
        if data:
            print(data)
        return

    streams = []

    # FIXED BLOCK ↓↓↓
    for category in data["streams"]:
        cat = category.get("category", "").strip()
        if cat not in ALLOWED_CATEGORIES:
            continue

        for stream in category.get("streams", []):
            name = stream.get("name", "Unnamed Event")

            iframe = (
                stream.get("iframe")
                or stream.get("streamUrl")
                or stream.get("liveUrl")
                or stream.get("embed")
                or stream.get("link")
            )

            if iframe and isinstance(iframe, str) and iframe.startswith("http"):
                streams.append({"name": name, "iframe": iframe, "category": cat})
    # ↑↑↑ FIX STOP HERE

    # Deduplicate
    seen = set()
    streams = [s for s in streams if (s["name"].lower() not in seen and not seen.add(s["name"].lower()))]

    if not streams:
        print("🚫 No usable streams found in API response.")
        return

    print(f"🔍 Found {len(streams)} streams across categories")

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        url_map = {}
        for s in streams:
            print(f"\n🔎 Scraping stream: {s['name']} ({s['category']})")
            urls = await grab_m3u8_from_iframe(page, s["iframe"])
            url_map[f"{s['name']}::{s['category']}::{s['iframe']}"] = urls

        await browser.close()

    print("\n💾 Writing PPVLand.m3u8 ...")
    playlist = build_m3u(streams, url_map)
    with open("PPVLand.m3u8", "w", encoding="utf-8") as f:
        f.write(playlist)

    print(f"✅ Done at {datetime.utcnow()} UTC")


if __name__ == "__main__":
    asyncio.run(main())
