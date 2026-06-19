# ============================================
# CELL 2: ZOOM BOT FUNCTIONS
# ============================================

import threading
import asyncio
import sys
import base64
import random
from datetime import datetime
import indian_names
from playwright.async_api import async_playwright
import nest_asyncio

nest_asyncio.apply()

# ============================================
# INDIAN NAME GENERATOR
# ============================================
def get_indian_name():
    """Generate random Indian name"""
    gender = random.choice(['male', 'female'])
    return indian_names.get_full_name(gender=gender)

MUTEX = threading.Lock()

def sync_print(msg):
    with MUTEX:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {msg}")

# ============================================
# ZOOM URL
# ============================================
ZOOM_PARTS = {
    'domain': base64.b64decode('em9vbS51cw==').decode(),
    'join_path': base64.b64decode('d2Mvam9pbg==').decode()
}

def get_zoom_url(meeting_code):
    return f"https://{ZOOM_PARTS['domain']}/{ZOOM_PARTS['join_path']}/{meeting_code}"

# ============================================
# SYNC BARRIER - SAB BOTS EK SAATH JOIN KARENGE
# ============================================
READY_TO_JOIN = asyncio.Event()
BOTS_READY = 0
BOTS_TOTAL = 0
BOTS_FAILED = 0
BOTS_LOCK = asyncio.Lock()

async def wait_for_all_bots():
    """Wait until all bots are ready to join"""
    global BOTS_READY, BOTS_TOTAL
    async with BOTS_LOCK:
        BOTS_READY += 1
        ready = BOTS_READY
        total = BOTS_TOTAL
        failed = BOTS_FAILED

    sync_print(f"[SYNC] {ready}/{total} bots ready (failed: {failed})")

    if ready + failed >= total:
        READY_TO_JOIN.set()
        sync_print("⚡ All bots ready! Joining together...")

    await READY_TO_JOIN.wait()

# ============================================
# JOIN AUDIO BY COMPUTER
# ============================================
async def join_audio_computer(page, tag):
    """Click on 'Join Audio by Computer' if prompted"""
    try:
        audio_selectors = [
            'xpath=//button[contains(text(), "Join Audio")]',
            'xpath=//button[contains(text(), "Computer Audio")]',
            'xpath=//button[contains(@class, "join-audio")]',
            'css=button[aria-label*="Join Audio"]',
            'xpath=//button[contains(text(), "Microphone")]'
        ]

        for selector in audio_selectors:
            try:
                audio_btn = page.locator(selector)
                if await audio_btn.count() > 0:
                    await audio_btn.first.wait_for(state="visible", timeout=5000)
                    await asyncio.sleep(1)
                    await audio_btn.first.click()
                    sync_print(f"{tag} ✅ audio joined")
                    return True
            except:
                continue

        muted_btn = page.locator('xpath=//button[contains(@aria-label, "mute") or contains(@aria-label, "Mute")]')
        if await muted_btn.count() > 0:
            sync_print(f"{tag} already has audio")
            return True

    except Exception as e:
        sync_print(f"{tag} audio join skipped: {e}")

    return False

# ============================================
# WAIT FOR MEETING TO START (HOST WAITING)
# ============================================
async def wait_for_meeting_to_start(page, tag):
    """
    Wait until meeting starts (host joins)
    Xpath: //*[@id="root"]/div/div[2]/div[1]/div[3]/span
    """
    waiting_xpath = 'xpath=//*[@id="root"]/div/div[2]/div[1]/div[3]/span'
    
    sync_print(f"{tag} checking if meeting is live...")
    
    try:
        waiting_element = page.locator(waiting_xpath)
        
        if await waiting_element.count() > 0 and await waiting_element.is_visible():
            sync_print(f"{tag} ⏳ meeting is NOT live! Waiting for host to start...")
            
            while True:
                try:
                    if await waiting_element.count() == 0 or not await waiting_element.is_visible():
                        sync_print(f"{tag} ✅ meeting has started! Proceeding...")
                        break
                    
                    indicators = [
                        'xpath=//button[contains(@aria-label, "mute")]',
                        'xpath=//button[contains(text(), "Participants")]',
                        'xpath=//button[contains(@aria-label, "Leave")]'
                    ]
                    
                    for indicator in indicators:
                        if await page.locator(indicator).count() > 0:
                            sync_print(f"{tag} ✅ meeting started (detected by indicator)!")
                            return True
                    
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    await asyncio.sleep(2)
                    continue
        else:
            sync_print(f"{tag} ✅ meeting is live! No waiting required.")
            
    except Exception as e:
        sync_print(f"{tag} error while checking meeting status: {e}")
    
    return True

# ============================================
# WAIT FOR WAITING ROOM
# ============================================
async def wait_for_waiting_room(page, tag):
    """
    Wait for waiting room (if enabled)
    Xpath: /html/body/div[2]/div[2]/div/div/div/div[1]/div[2]/div[1]/div[3]/span
    """
    waiting_room_xpath = 'xpath=/html/body/div[2]/div[2]/div/div/div/div[1]/div[2]/div[1]/div[3]/span'
    
    sync_print(f"{tag} checking for waiting room...")
    
    try:
        waiting_room_element = page.locator(waiting_room_xpath)
        
        if await waiting_room_element.count() > 0 and await waiting_room_element.is_visible():
            sync_print(f"{tag} 🚪 IN WAITING ROOM! Waiting for host to admit...")
            
            while True:
                try:
                    if await waiting_room_element.count() == 0 or not await waiting_room_element.is_visible():
                        sync_print(f"{tag} ✅ admitted to meeting! Proceeding...")
                        break
                    
                    indicators = [
                        'xpath=//button[contains(@aria-label, "mute")]',
                        'xpath=//button[contains(text(), "Participants")]',
                        'xpath=//button[contains(@aria-label, "Leave")]'
                    ]
                    
                    for indicator in indicators:
                        if await page.locator(indicator).count() > 0:
                            sync_print(f"{tag} ✅ admitted to meeting (detected by indicator)!")
                            return True
                    
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    await asyncio.sleep(2)
                    continue
        else:
            sync_print(f"{tag} no waiting room detected")
            
    except Exception as e:
        sync_print(f"{tag} error while checking waiting room: {e}")
    
    return True

# ============================================
# MAIN BOT FUNCTION
# ============================================
async def start_bot(tag, wait_time, meetingcode, passcode, headless):
    global BOTS_FAILED
    sync_print(f"{tag} started")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--use-fake-device-for-media-stream',
                '--use-file-for-fake-audio-capture=/dev/null',
                '--mute-audio',
                '--disable-camera',
                '--disable-video-capture',
                '--disable-gpu',
                '--window-size=1280,720',
                '--disable-setuid-sandbox'
            ]
        )

        context = await browser.new_context(
            permissions=[],
            viewport={"width": 1280, "height": 720}
        )

        page = await context.new_page()
        zoom_url = get_zoom_url(meetingcode)
        await page.goto(zoom_url, timeout=120000)
        await page.wait_for_timeout(4000)

        # ============================================
        # NAME INPUT - INDIAN NAME
        # ============================================
        try:
            name_selectors = [
                'xpath=//*[@id="input-for-name"]',
                'xpath=//input[@placeholder="Enter your name"]',
                'xpath=//input[@name="name"]'
            ]
            
            name_filled = False
            for selector in name_selectors:
                try:
                    name_input = page.locator(selector)
                    if await name_input.count() > 0:
                        await name_input.first.wait_for(state="visible", timeout=5000)
                        await asyncio.sleep(1)
                        user_name = get_indian_name()
                        await name_input.first.fill(user_name)
                        sync_print(f"{tag} ✅ Name filled: {user_name}")
                        name_filled = True
                        break
                except:
                    continue
            
            if not name_filled:
                sync_print(f"{tag} ❌ name input not found")
                async with BOTS_LOCK:
                    BOTS_FAILED += 1
                await browser.close()
                return
                
        except Exception as e:
            sync_print(f"{tag} name fill failed: {e}")
            async with BOTS_LOCK:
                BOTS_FAILED += 1
            await browser.close()
            return

        # ============================================
        # PASSCODE INPUT
        # ============================================
        if passcode and passcode != "":
            sync_print(f"{tag} entering passcode...")
            try:
                passcode_selectors = [
                    'xpath=//input[@type="password"]',
                    'xpath=//input[contains(@placeholder, "code")]',
                    'xpath=//input[contains(@aria-label, "code")]',
                    'xpath=//*[@id="input-for-password"]',
                    'xpath=/html/body/div[2]/div[2]/div/div[1]/div/div[2]/div[2]/div/input'
                ]
                
                pass_filled = False
                for selector in passcode_selectors:
                    try:
                        pass_input = page.locator(selector)
                        if await pass_input.count() > 0:
                            await pass_input.first.wait_for(state="visible", timeout=5000)
                            await asyncio.sleep(1.5)
                            await pass_input.first.fill(passcode)
                            sync_print(f"{tag} ✅ Passcode filled")
                            pass_filled = True
                            break
                    except:
                        continue
                
                if not pass_filled:
                    sync_print(f"{tag} ⚠️ passcode field not found - meeting might not require passcode")
                    
            except Exception as e:
                sync_print(f"{tag} passcode error: {e}")
        else:
            sync_print(f"{tag} no passcode provided, skipping passcode field")

        # ============================================
        # WAIT FOR ALL BOTS TO BE READY
        # ============================================
        await wait_for_all_bots()

        # ============================================
        # JOIN BUTTON
        # ============================================
        try:
            join_selectors = [
                'xpath=//button[contains(text(), "Join")]',
                'xpath=//button[contains(@class, "join")]',
                'xpath=//*[@id="root"]/div/div[1]/div/div[2]/button'
            ]
            
            join_btn = None
            for selector in join_selectors:
                try:
                    join_btn = page.locator(selector)
                    if await join_btn.count() > 0:
                        await join_btn.first.wait_for(state="visible", timeout=5000)
                        join_btn = join_btn.first
                        break
                except:
                    continue

            if join_btn:
                await asyncio.sleep(random.uniform(0.5, 1.5))
                await join_btn.click()
                sync_print(f"{tag} ✅ join clicked")
            else:
                sync_print(f"{tag} ❌ join button not found")
                await browser.close()
                return
                
        except Exception as e:
            sync_print(f"{tag} join click failed: {e}")
            await browser.close()
            return

        # ============================================
        # WAIT FOR MEETING TO START
        # ============================================
        await wait_for_meeting_to_start(page, tag)
        
        # ============================================
        # WAIT FOR WAITING ROOM
        # ============================================
        await wait_for_waiting_room(page, tag)

        # ============================================
        # JOIN AUDIO
        # ============================================
        await join_audio_computer(page, tag)

        # ============================================
        # STAY IN MEETING
        # ============================================
        sync_print(f"{tag} ⏱️ staying for {wait_time//60} minutes")
        
        elapsed = 0
        while elapsed < wait_time:
            await asyncio.sleep(2)
            elapsed += 2

        sync_print(f"{tag} ✅ ended")
        await browser.close()


# ============================================
# MAIN FUNCTION - CELL 2 SE CALL HOGA
# ============================================
def main(meeting_id, passcode, num_bots, duration_minutes, headless=True):
    """
    Main function to launch Zoom bots
    
    Parameters:
    - meeting_id: Zoom meeting ID (e.g., "5415403058")
    - passcode: Zoom meeting passcode (e.g., "850893")
    - num_bots: Number of bots to launch (e.g., 10)
    - duration_minutes: Duration in minutes (e.g., 5)
    - headless: True=background, False=show browsers
    """
    
    global BOTS_TOTAL
    
    duration_seconds = duration_minutes * 60
    BOTS_TOTAL = num_bots
    
    print(f"\n{'='*60}")
    print(f"🚀 Starting {num_bots} bots for meeting: {meeting_id}")
    print(f"⏱️  Duration: {duration_minutes} minutes")
    print(f"🔒 Passcode: {passcode if passcode else 'None'}")
    print(f"🖥️  Headless mode: {headless}")
    print(f"{'='*60}\n")
    
    # Create and run bot tasks
    async def run_bots():
        tasks = []
        for i in range(num_bots):
            tag = f"Bot-{i+1}"
            task = asyncio.create_task(
                start_bot(tag, duration_seconds, meeting_id, passcode, headless)
            )
            tasks.append(task)
            await asyncio.sleep(0.5)  # Small delay between bot starts
        
        # Wait for all bots to complete
        await asyncio.gather(*tasks)
        
        print(f"\n{'='*60}")
        print("✅ All bots have completed their sessions")
        print(f"{'='*60}\n")
    
    # Run the async function
    asyncio.run(run_bots())


# ============================================
# USAGE EXAMPLE (Cell 2 mein ye call karo)
# ============================================
# main(
#     meeting_id="5415403058",
#     passcode="850893",
#     num_bots=10,
#     duration_minutes=5,
#     headless=True
# )
