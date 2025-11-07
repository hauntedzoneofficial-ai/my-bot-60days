import os
import time
import random
import json
import threading
import requests
from pyngrok import ngrok
from flask import Flask, request
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from playwright.sync_api import sync_playwright

# ================================
# CONFIGURATION
# ================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
DRIVE_FILE_ID = '19FYL4wY2vN2vwJvPChSaqldElmvDFBgk'  # ← YAHAN APNA DRIVE FILE ID DAAL DO
GUEST_DELAY_MIN = 120  # 2 min
GUEST_DELAY_MAX = 180  # 3 min
HEADLESS = False  # ← Real browser (tumhara original)

# ================================
# FLASK + NGROK FOR OAUTH CALLBACK
# ================================
app = Flask(__name__)
auth_code = None

@app.route('/oauth2callback')
def oauth2callback():
    global auth_code
    code = request.args.get('code')
    if code:
        auth_code = code
        return """
        <h1>Authorization Successful!</h1>
        <p>Token received. You can close this tab.</p>
        <script>window.close();</script>
        """
    return "Error: No code received."

def start_ngrok_and_server():
    # Start Flask in background
    flask_thread = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=8080, use_reloader=False, debug=False)
    )
    flask_thread.daemon = True
    flask_thread.start()
    
    # Start ngrok
    public_url = ngrok.connect(8080, bind_tls=True)
    print(f"\nNGROK PUBLIC URL: {public_url}")
    print(f"OAuth Redirect: {public_url}/oauth2callback\n")
    return str(public_url)

# ================================
# GOOGLE DRIVE LIST DOWNLOADER (DYNAMIC REDIRECT)
# ================================
def download_urls_from_drive():
    global auth_code
    auth_code = None  # Reset
    print("Google Drive se list download kar raha hun...")
    
    creds = None
    token_path = os.path.join(BASE_DIR, 'token.json')
    creds_path = os.path.join(BASE_DIR, 'credentials.json')

    # Start ngrok + Flask
    ngrok_url = start_ngrok_and_server()
    
    # Load existing token
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    # Refresh or new auth
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except:
                creds = None

        if not creds:
            if not os.path.exists(creds_path):
                print("ERROR: credentials.json upload karo!")
                return None
            
            # Load client config
            with open(creds_path) as f:
                client_config = json.load(f)['web']  # Web app type

            # Build auth URL with dynamic redirect
            redirect_uri = f"{ngrok_url}/oauth2callback"
            auth_url = (
                f"https://accounts.google.com/o/oauth2/auth?"
                f"client_id={client_config['client_id']}&"
                f"redirect_uri={redirect_uri}&"
                f"response_type=code&"
                f"scope={' '.join(SCOPES)}&"
                f"access_type=offline&prompt=consent"
            )
            
            print(f"1. Visit: {auth_url}")
            print("2. Allow access → Redirect hoga")
            print("3. Wait 15 sec...\n")

            # Wait for code
            for _ in range(120):
                if auth_code:
                    break
                time.sleep(1)
            else:
                print("ERROR: Authorization timeout!")
                return None

            # Exchange code for token
            token_response = requests.post(
                'https://oauth2.googleapis.com/token',
                data={
                    'code': auth_code,
                    'client_id': client_config['client_id'],
                    'client_secret': client_config['client_secret'],
                    'redirect_uri': redirect_uri,
                    'grant_type': 'authorization_code'
                }
            ).json()

            if 'error' in token_response:
                print(f"Token error: {token_response}")
                return None

            creds = Credentials(
                token=token_response.get('access_token'),
                refresh_token=token_response.get('refresh_token'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=client_config['client_id'],
                client_secret=client_config['client_secret'],
                scopes=SCOPES
            )

        # Save token
        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    # Download file
    service = build('drive', 'v3', credentials=creds)
    try:
        results = service.files().get_media(fileId=DRIVE_FILE_ID).execute()
        content = results.decode('utf-8').strip().split('\n')
        urls = [line.strip() for line in content if line.strip() and 'etsy.com' in line]
        print(f"{len(urls)} URLs loaded from Drive!")
        return urls
    except Exception as e:
        print(f"Drive error: {e}")
        return None

# ================================
# ETSY BOT CORE
# ================================
def run_etsy_bot(urls):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = context.new_page()

        for idx, url in enumerate(urls):
            try:
                print(f"\n[GUEST #{idx+1}] Processing: {url}")
                page.goto(url, timeout=90000)
                time.sleep(5)

                # Example: Add to cart (adjust selector)
                if page.locator("button[data-add-to-cart]").count() > 0:
                    page.click("button[data-add-to-cart]")
                    time.sleep(2)
                    print("→ Product ADD ho gaya!")
                else:
                    print("→ Add button nahi mila")

                delay = random.randint(GUEST_DELAY_MIN, GUEST_DELAY_MAX)
                print(f"→ Waiting {delay//60} min...")
                time.sleep(delay)

            except Exception as e:
                print(f"Error: {e}")
                time.sleep(10)

        browser.close()
        print("All guests done!")

# ================================
# MAIN LOOP (60 DAYS)
# ================================
def main():
    print("60 DAYS ETSY BOT SHURU! → 60 din tak")
    
    while True:
        urls = download_urls_from_drive()
        if urls:
            run_etsy_bot(urls)
        else:
            print("No URLs – retry in 1 hour...")
        
        print("6 ghante baad dobara...")
        time.sleep(6 * 60 * 60)  # 6 hours

if __name__ == "__main__":
    main()
