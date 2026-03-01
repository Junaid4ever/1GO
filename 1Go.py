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

# INDIAN NAMES USE KARO
def get_indian_name():
    """Generate random Indian name"""
    gender = random.choice(['male', 'female'])
    return indian_names.get_full_name(gender=gender)

MUTEX = threading.Lock()

def sync_print(msg):
    with MUTEX:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {msg}")

# URL encode
ZOOM_PARTS = {
    'domain': base64.b64decode('em9vbS51cw==').decode(),
    'join_path': base64.b64decode('d2Mvam9pbg==').decode()
}

def get_zoom_url(meeting_code):
    return f"https://{ZOOM_PARTS['domain']}/{ZOOM_PARTS['join_path']}/{meeting_code}"

# Global variable for synchronization
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
        sync_print("[SYNC] All bots ready! Joining together...")

    await READY_TO_JOIN.wait()

async def join_audio_computer(page, tag):
    """Click on 'Join Audio by Computer' if prompted"""
    try:
        # Multiple selectors for audio join button
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
                    sync_print(f"{tag} audio joined")
                    return True
            except:
                continue

        # Check if already joined
        muted_btn = page.locator('xpath=//button[contains(@aria-label, "mute") or contains(@aria-label, "Mute")]')
        if await muted_btn.count() > 0:
            sync_print(f"{tag} already has audio")
            return True

    except Exception as e:
        sync_print(f"{tag} audio join skipped: {e}")

    return False

async def wait_for_meeting_to_start(page, tag):
    """
    Yeh function tab tak wait karega jab tak meeting start nahi ho jaati
    Xpath: //*[@id="root"]/div/div[2]/div[1]/div[3]/span
    """
    waiting_xpath = 'xpath=//*[@id="root"]/div/div[2]/div[1]/div[3]/span'
    
    sync_print(f"{tag} checking if meeting is live...")
    
    try:
        # Pehle check karo ki kya yeh element exist karta hai
        waiting_element = page.locator(waiting_xpath)
        
        # Agar element exist karta hai, matlab meeting live nahi hai
        if await waiting_element.count() > 0 and await waiting_element.is_visible():
            sync_print(f"{tag} meeting is NOT live! Waiting for host to start...")
            
            # Tab tak wait karo jab tak yeh element disappear na ho jaye
            # Ya phir koi doosra element na aa jaye jo meeting start hone ka sign ho
            while True:
                try:
                    # Check if waiting message still visible
                    if await waiting_element.count() == 0 or not await waiting_element.is_visible():
                        sync_print(f"{tag} meeting has started! Proceeding...")
                        break
                    
                    # Kuch doosre elements check karo jo meeting start hone ke baad aate hain
                    # Jaise mute button, participants list, etc.
                    meeting_started_indicators = [
                        'xpath=//button[contains(@aria-label, "mute")]',
                        'xpath=//button[contains(text(), "Participants")]',
                        'xpath=//button[contains(@aria-label, "Leave")]'
                    ]
                    
                    for indicator in meeting_started_indicators:
                        if await page.locator(indicator).count() > 0:
                            sync_print(f"{tag} meeting started (detected by indicator)!")
                            return True
                    
                    # Wait for 2 seconds before checking again
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    await asyncio.sleep(2)
                    continue
        else:
            sync_print(f"{tag} meeting is live! No waiting required.")
            
    except Exception as e:
        sync_print(f"{tag} error while checking meeting status: {e}")
    
    return True

async def wait_for_waiting_room(page, tag):
    """
    Yeh function waiting room ke liye wait karega
    Xpath: /html/body/div[2]/div[2]/div/div/div/div[1]/div[2]/div[1]/div[3]/span
    Jab host admit karega, tab yeh element disappear ho jayega
    """
    waiting_room_xpath = 'xpath=/html/body/div[2]/div[2]/div/div/div/div[1]/div[2]/div[1]/div[3]/span'
    
    sync_print(f"{tag} checking for waiting room...")
    
    try:
        waiting_room_element = page.locator(waiting_room_xpath)
        
        # Check if waiting room is active
        if await waiting_room_element.count() > 0 and await waiting_room_element.is_visible():
            sync_print(f"{tag} IN WAITING ROOM! Waiting for host to admit...")
            
            # Tab tak wait karo jab tak waiting room se bahar na aa jaye
            while True:
                try:
                    # Check if still in waiting room
                    if await waiting_room_element.count() == 0 or not await waiting_room_element.is_visible():
                        sync_print(f"{tag} admitted to meeting! Proceeding...")
                        break
                    
                    # Extra indicators check for being admitted
                    meeting_indicators = [
                        'xpath=//button[contains(@aria-label, "mute")]',
                        'xpath=//button[contains(text(), "Participants")]',
                        'xpath=//button[contains(@aria-label, "Leave")]'
                    ]
                    
                    for indicator in meeting_indicators:
                        if await page.locator(indicator).count() > 0:
                            sync_print(f"{tag} admitted to meeting (detected by indicator)!")
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

async def start(tag, wait_time, meetingcode, passcode, headless):
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
        # NAME INPUT - INDIAN NAME GENERATE KARO
        # ============================================
        try:
            name_input = page.locator('xpath=//*[@id="input-for-name"]')
            await name_input.wait_for(state="visible", timeout=30000)
            await asyncio.sleep(1)
            
            # Indian name generate karo
            user_name = get_indian_name()
            await name_input.fill(user_name)
            sync_print(f"{tag} name filled: {user_name}")
        except Exception as e:
            sync_print(f"{tag} name fill failed: {e}")
            async with BOTS_LOCK:
                BOTS_FAILED += 1
            await browser.close()
            return

        # ============================================
        # PASSCODE INPUT - SIRF TAB SKIP KARO JAB PASSCODE EMPTY HO
        # ============================================
        passcode_entered = False
        
        if passcode is not None and passcode != "":
            sync_print(f"{tag} attempting to enter passcode: {passcode}")
            try:
                # Try multiple selectors for passcode input
                passcode_selectors = [
                    'xpath=//input[@type="password"]',
                    'xpath=//input[contains(@placeholder, "code")]',
                    'xpath=//input[contains(@aria-label, "code")]',
                    'xpath=//*[@id="input-for-password"]',
                    'xpath=/html/body/div[2]/div[2]/div/div[1]/div/div[2]/div[2]/div/input'
                ]
                
                pass_input = None
                for selector in passcode_selectors:
                    try:
                        pass_input = page.locator(selector)
                        if await pass_input.count() > 0:
                            await pass_input.first.wait_for(state="visible", timeout=5000)
                            pass_input = pass_input.first
                            break
                    except:
                        continue
                
                if pass_input:
                    await asyncio.sleep(1.5)
                    await pass_input.fill(passcode)
                    sync_print(f"{tag} passcode filled: {passcode}")
                    passcode_entered = True
                else:
                    sync_print(f"{tag} no passcode field found - meeting might not require passcode")
                    
            except Exception as e:
                sync_print(f"{tag} passcode fill error: {e}")
        else:
            sync_print(f"{tag} no passcode provided (empty), skipping passcode field")

        # Wait for all bots to be ready
        await wait_for_all_bots()

        # ============================================
        # JOIN BUTTON CLICK
        # ============================================
        try:
            # Try multiple join button selectors
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
                await asyncio.sleep(random.uniform(0.5, 1.5))  # Small random delay
                await join_btn.click()
                sync_print(f"{tag} join clicked")
            else:
                sync_print(f"{tag} join button not found")
                await browser.close()
                return
                
        except Exception as e:
            sync_print(f"{tag} join click failed: {e}")
            await browser.close()
            return

        # ============================================
        # NEW: WAIT FOR MEETING TO START (AGAR LIVE NAHI HAI TO)
        # ============================================
        await wait_for_meeting_to_start(page, tag)
        
        # ============================================
        # NEW: WAIT FOR WAITING ROOM (AGAR ENABLED HAI TO)
        # ============================================
        await wait_for_waiting_room(page, tag)

        # ============================================
        # FINALLY: JOIN AUDIO BY COMPUTER (JAB MEETING MEIN AA JAYE)
        # ============================================
        await join_audio_computer(page, tag)

        # STAY IN MEETING
        sync_print(f"{tag} now staying for {wait_time//60} minutes")
        await asyncio.sleep(wait_time)

        sync_print(f"{tag} ended")
        await browser.close()
