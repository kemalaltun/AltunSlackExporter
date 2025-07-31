import csv
import requests
import time
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# takip dosyası
SINCE_TS_FILE = 'since_ts.txt'

def load_config(config_path='config.json'):
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"{config_path} not found. Please create a config.json containing the token, cookie, and channel information."
        )
    with open(config_path, 'r', encoding='utf-8') as file:
        return json.load(file)

def load_since_ts(path=SINCE_TS_FILE):
    """
    Eğer dosya varsa içindeki timestamp'i döner,
    yoksa None.
    """
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            ts = f.read().strip()
            return ts or None
    return None

def save_since_ts(ts, path=SINCE_TS_FILE):
    """
    En son işlenen timestamp'i dosyaya yazar.
    """
    with open(path, 'w', encoding='utf-8') as f:
        f.write(ts)

def fetch_only_thread_messages(token, cookie, channel_id, since_ts=None):
    """
    reply_count > 0 olan mesajları çeker, permalinki paralel getirir,
    ts sırasını bozar ve döner.
    """
    print(f"Fetching threads since ts={since_ts}...")
    BASE = "https://slack.com/api"
    history_url = f"{BASE}/conversations.history"
    params = {'channel': channel_id, 'limit': 1000}
    if since_ts:
        params['oldest'] = since_ts

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Cookie': cookie
    }

    threads = []
    cursor = None
    while True:
        if cursor:
            params['cursor'] = cursor
        resp = requests.get(history_url, headers=headers, params=params)
        if resp.status_code == 429:
            wait = int(resp.headers.get('Retry-After', 10))
            print(f"Rate limit → sleeping {wait}s")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        data = resp.json()
        if not data.get('ok'):
            print("Error:", data.get('error'))
            break

        msgs = data.get('messages', [])
        for m in msgs:
            if m.get('reply_count', 0) > 0:
                threads.append({
                    'ts': m['ts'],
                    'user': m.get('user', 'Unknown'),
                    'text': m.get('text', '').replace('\n', ' '),
                    'thread_ts': m['ts'],
                    'reply_count': m.get('reply_count', 0),
                    'subtype': m.get('subtype', 'normal_message'),
                    'thread_url': None
                })
        cursor = data.get('response_metadata', {}).get('next_cursor')
        if not cursor:
            break
        time.sleep(1)

    # permalinks parallel
    total = len(threads)
    print(f"{total} threads found → fetching permalinks...")
    completed = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        future_to_msg = {
            ex.submit(get_permalink_for_message, token, cookie, channel_id, t['ts']): t
            for t in threads
        }
        for fut in as_completed(future_to_msg):
            msg = future_to_msg[fut]
            try:
                msg['thread_url'] = fut.result()
            except Exception:
                msg['thread_url'] = ''
            # ilerleme güncellemesi
            completed += 1
            percent = completed / total * 100
            print(f"Permalinks: {completed}/{total} ({percent:.1f}%)", end='\r', flush=True)
    print()  # son satırı tamamla

    # ts sırasına göre sırala
    threads.sort(key=lambda x: float(x['ts']))
    return threads

def get_permalink_for_message(token, cookie, channel_id, message_ts):
    BASE = "https://slack.com/api/chat.getPermalink"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Cookie': cookie
    }
    params = {'channel': channel_id, 'message_ts': message_ts}
    while True:
        resp = requests.get(BASE, headers=headers, params=params)
        if resp.status_code == 429:
            wait = int(resp.headers.get('Retry-After', 10))
            time.sleep(wait)
            continue
        resp.raise_for_status()
        data = resp.json()
        return data.get('permalink', '')

def save_threads_to_json(threads, filename='threads.json'):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(threads, f, ensure_ascii=False, indent=4)
    print(f"Saved {len(threads)} threads to {filename}")

def main():
    # config
    cfg = load_config()
    token = cfg.get('SLACK_TOKEN')
    cookie = cfg.get('SLACK_COOKIE', '')
    channel = cfg.get('CHANNEL_ID')
    if not token or not channel:
        raise ValueError("SLACK_TOKEN and CHANNEL_ID must be in config.json")

    # önceki ts
    last_ts = load_since_ts()
    # fetch
    threads = fetch_only_thread_messages(token, cookie, channel, since_ts=last_ts)
    if not threads:
        print("Yeni thread bulunamadı.")
        return

    # kaydet
    save_threads_to_json(threads)
    # en son ts
    newest_ts = threads[-1]['ts']
    save_since_ts(newest_ts)
    print(f"En son ts={newest_ts} olarak kaydedildi → bir sonraki çalıştırmada buradan devam edilecek.")

if __name__ == "__main__":
    main()
