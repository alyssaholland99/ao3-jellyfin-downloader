import os
import time
import queue
import threading
import subprocess
import requests
from flask import Flask, render_template, request, jsonify
from bs4 import BeautifulSoup

app = Flask(__name__)

# --- CONFIGURATION ---
SAVE_FOLDER = os.environ.get("SAVE_FOLDER", "/app/books")
JELLYFIN_URL = os.environ.get("JELLYFIN_URL", "http://localhost:8096")
JELLYFIN_API_KEY = os.environ.get("JELLYFIN_API_KEY", "YOUR_JELLYFIN_API_KEY")
WIFI_SSID = os.environ.get("WIFI_SSID", "Holland WiFi")
# ---------------------

download_queue = queue.Queue()
queue_status = [] 
status_lock = threading.Lock()

def ensure_network():
    """Checks 1.1.1.1 and falls back to Holland WiFi with a 30s timeout."""
    print("[Network] Checking connection to 1.1.1.1...")
    try:
        requests.get("https://1.1.1.1", timeout=3)
        print("[Network] Connected to 1.1.1.1 successfully.")
        return
    except requests.RequestException:
        print(f"[Network] Cannot reach 1.1.1.1. Attempting to connect to '{WIFI_SSID}'...")

    try:
        # Run nmcli with a strict 30 second timeout constraint
        subprocess.run(
            ["nmcli", "device", "wifi", "connect", WIFI_SSID],
            timeout=30,
            check=True,
            capture_output=True
        )
        print(f"[Network] Successfully connected to '{WIFI_SSID}'.")
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"ERROR: Failed to connect to '{WIFI_SSID}' within 30 seconds.")
    except subprocess.CalledProcessError as e:
        raise ConnectionError(f"ERROR: Could not connect to '{WIFI_SSID}'. Details: {e.stderr.decode().strip()}")

def get_epub_info(ao3_url):
    """Scrapes AO3 to get the direct EPUB link and work title."""
    if "/works/" not in ao3_url:
        raise ValueError("Invalid AO3 Work URL.")
    
    # Strip chapters/query params to get the base work URL
    work_id = ao3_url.split("/works/")[1].split("/")[0].split("?")[0]
    base_url = f"https://archiveofourown.org/works/{work_id}?view_adult=true"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    # Attempt the connection up to 3 times with a generous 60-second timeout
    for attempt in range(3):
        try:
            resp = requests.get(base_url, headers=headers, timeout=60)
            resp.raise_for_status()
            break # Exit the loop if successful
        except requests.RequestException as e:
            if attempt == 2: # If it fails on the 3rd try, raise the error to the UI
                raise Exception(f"Network error after 3 attempts: {e}")
            time.sleep(3) # Wait 3 seconds before trying again
        
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    download_li = soup.find("li", class_="download")
    if not download_li:
        raise Exception("Could not find download options.")
        
    epub_link = None
    # Search the download menu for the EPUB button
    for a in download_li.find_all("a", href=True):
        # Look for '.epub' anywhere in the URL, or the exact button text
        if '.epub' in a['href'].lower() or a.text.strip().upper() == 'EPUB':
            epub_link = f"https://archiveofourown.org{a['href']}"
            break
            
    if not epub_link:
        raise Exception("EPUB format not available.")
        
    title = soup.find("h2", class_="title").text.strip()
    return epub_link, title

def notify_jellyfin():
    """Tells Jellyfin to rescan the library."""
    try:
        url = f"{JELLYFIN_URL}/Library/Refresh"
        
        # Use the official Jellyfin Authorization header
        headers = {"Authorization": f'MediaBrowser Token="{JELLYFIN_API_KEY}"'}
        
        resp = requests.post(url, headers=headers, timeout=10)
        
        # Force Python to throw an error if Jellyfin returns a 401 (Unauthorized), 404, etc.
        resp.raise_for_status() 
        
        print("[Jellyfin] Library refresh triggered successfully.")
    except Exception as e:
        print(f"[Jellyfin] API error: {e}")

def worker():
    """Background daemon processing the download queue."""
    while True:
        task = download_queue.get()
        task_id = task['id']
        url = task['url']
        
        with status_lock:
            for item in queue_status:
                if item['id'] == task_id:
                    item['status'] = 'Downloading...'
                    
        try:
            os.makedirs(SAVE_FOLDER, exist_ok=True)
            download_url, title = get_epub_info(url)
            
            # Create a safe filename
            safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '_', '-')]).strip()
            filepath = os.path.join(SAVE_FOLDER, f"{safe_title}.epub")
            
            # Download file
            headers = {"User-Agent": "Mozilla/5.0"}
            r = requests.get(download_url, headers=headers, stream=True, timeout=30)
            r.raise_for_status()
            
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                    
            # Calculate the file size
            size_bytes = os.path.getsize(filepath)
            if size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
                    
            notify_jellyfin()
            
            with status_lock:
                for item in queue_status:
                    if item['id'] == task_id:
                        # Append the size to the status badge
                        item['status'] = f'Completed ({size_str})' 
                        item['title'] = title
        except Exception as e:
            with status_lock:
                for item in queue_status:
                    if item['id'] == task_id:
                        item['status'] = f'Failed: {str(e)}'
        
        download_queue.task_done()

# Start background thread
threading.Thread(target=worker, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/enqueue', methods=['POST'])
def enqueue():
    urls = request.json.get('urls', [])
    with status_lock:
        for url in urls:
            if url.strip():
                task_id = str(time.time() + len(queue_status))
                queue_status.append({
                    'id': task_id,
                    'url': url.strip(),
                    'title': 'Processing...',
                    'status': 'Queued'
                })
                download_queue.put({'id': task_id, 'url': url.strip()})
    return jsonify({"success": True})

@app.route('/status', methods=['GET'])
def status():
    with status_lock:
        return jsonify(queue_status)

if __name__ == '__main__':
    try:
        ensure_network()
    except Exception as err:
        print(f"\n[FATAL STARTUP ERROR] {err}")
        exit(1)
        
    app.run(host='0.0.0.0', port=5000, debug=False)