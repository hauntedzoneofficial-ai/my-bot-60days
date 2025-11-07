import os
import time
import random
import io
from playwright.sync_api import sync_playwright
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# === CONFIG ===
BASE_DIR = "/app"
URLS_FILE = os.path.join(BASE_DIR, "product_urls.txt")
NUM_GUESTS = 25
PRODUCTS_PER_GUEST = 5
TOTAL_DAYS = 60
START_TIME = time.time()

# ← YAHAN APNA GOOGLE DRIVE FILE ID DAALO
DRIVE_FILE_ID = "19FYL4wY2vN2vwJvPChSaqldElmvDFBgk"  # ← CHANGE THIS!

# === DOWNLOAD LIST FROM GOOGLE DRIVE ===
def download_urls_from_drive():
    print("Google Drive se list download kar raha hun...")
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    creds = None
    token_path = os.path.join(BASE_DIR, 'token.json')
    creds_path = os.path.join(BASE_DIR, 'credentials.json')

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if not os.path.exists(creds_path):
            print("ERROR: credentials.json nahi mila! GitHub pe upload karo.")
            return
        flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    service = build('drive', 'v3', credentials=creds)
    request = service.files().get_media(fileId=DRIVE_FILE_ID)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    with open(URLS_FILE, "wb") as f:
        f.write(fh.read())
    print("List updated from Google Drive!")

# === LOAD URLS ===
def load_urls():
    if not os.path.exists(URLS_FILE):
        download_urls_from_drive()
    try:
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and "etsy.com/listing" in line]
    except:
        return []

# === GUEST FUNCTION ===
def guest_multi_add(guest_id, urls):
    if not urls:
        return
    selected = random.sample(urls, k=min(PRODUCTS_PER_GUEST, len(urls)))
    print(f"\n[GUEST #{guest_id}] {len(selected)} products add kar raha...")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=os.path.join(BASE_DIR, f"guest_{guest_id}"),
            headless=False,
            viewport={"width": 1366, "height": 768},
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        page = context.pages[0] if context.pages else context.new_page()
        try:
            for i, url in enumerate(selected):
                page.goto(url, timeout=90000)
                time.sleep(random.uniform(12, 20))
                page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.7)")
                time.sleep(6)

                add_btn = page.locator('button:has-text("Add to basket"), button:has-text("Add to cart")').first
                add_btn.wait_for(timeout=30000)
                add_btn.click()
                print(f" → Product {i+1} ADD! [{url.split('/')[-2]}]")

                if i < len(selected) - 1:
                    time.sleep(120)
            print(f"GUEST #{guest_id} → DONE!")
        except Exception as e:
            print(f"ERROR (Guest {guest_id}): {e}")
        finally:
            context.close()

# === MAIN LOOP ===
if __name__ == "__main__":
    print(f"60 DAYS ETSY BOT SHURU! → {TOTAL_DAYS} din tak")
    download_urls_from_drive()

    last_update = 0
    while True:
        elapsed_days = (time.time() - START_TIME) / (24 * 3600)
        if elapsed_days >= TOTAL_DAYS:
            print("60 din poore! Band ho raha.")
            break

        # Har 6 ghante update
        if time.time() - last_update > 6 * 3600:
            download_urls_from_drive()
            last_update = time.time()

        urls = load_urls()
        if len(urls) < 2:
            print("URLs nahi! 10 min wait...")
            time.sleep(600)
            continue

        try:
            for i in range(1, NUM_GUESTS + 1):
                guest_multi_add(i, urls)
                wait = random.uniform(1800, 5400)
                print(f"Next guest in {wait/60:.0f} min...")
                time.sleep(wait)
        except Exception as e:
            print(f"Crash! Restart in 60 sec... {e}")
            time.sleep(60)
