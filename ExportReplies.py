import os
import json
import time
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import List

# Sabit dosya adları
THREADS_JSON = "threads.json"
REPLIES_JSON = "replies.json"
PROGRESS_FILE = "progress.json"

def load_config(config_path: str = 'config.json') -> dict:
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"{config_path} bulunamadı. Lütfen token, cookie ve channel bilgilerini içeren bir config.json oluşturun."
        )
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def fetch_replies_for_thread(token: str, cookie: str, channel: str, thread_ts: str, limit: int = 1000) -> List[dict]:
    url = "https://slack.com/api/conversations.replies"
    headers = {
        "Authorization": f"Bearer {token}",
        "Cookie": cookie
    }
    replies = []
    cursor = None

    while True:
        params = {
            "channel": channel,
            "ts": thread_ts,
            "limit": limit
        }
        if cursor:
            params["cursor"] = cursor

        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 1))
            print(f"Rate limit ({thread_ts}). Bekleniyor {retry_after}s...")
            time.sleep(retry_after)
            continue

        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            print(f"Error fetching replies for {thread_ts}: {data.get('error')}")
            break

        msgs = data.get("messages", [])
        batch = [m for m in msgs if m.get("thread_ts") and m["ts"] != m["thread_ts"]]
        replies.extend(batch)

        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    return replies

def save_json(data, filename: str):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def main():
    print("→ Reply-fetcher başlıyor...")
    cfg = load_config()
    token = cfg.get("SLACK_TOKEN")
    cookie = cfg.get("SLACK_COOKIE", "")
    channel = cfg.get("CHANNEL_ID")
    if not token or not channel:
        raise ValueError("SLACK_TOKEN ve CHANNEL_ID config.json içinde olmalı.")

    if not os.path.exists(THREADS_JSON):
        raise FileNotFoundError(f"{THREADS_JSON} bulunamadı. Önce thread export scriptini çalıştırın.")
    with open(THREADS_JSON, "r", encoding="utf-8") as f:
        threads = json.load(f)
    thread_ts_list = [t["ts"] for t in threads if t.get("ts")]

    total = len(thread_ts_list)
    print(f"Toplam işlenecek thread: {total}")

    start_idx = 0
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as pf:
                start_idx = json.load(pf).get("last_processed_index", 0)
        except:
            start_idx = 0

    if os.path.exists(REPLIES_JSON):
        try:
            with open(REPLIES_JSON, "r", encoding="utf-8") as rf:
                replies_data = json.load(rf)
        except:
            replies_data = []
    else:
        replies_data = []

    slice_ts = thread_ts_list[start_idx:]
    with ThreadPoolExecutor(max_workers=5) as executor:
        for offset, replies in enumerate(executor.map(
            lambda ts: fetch_replies_for_thread(token, cookie, channel, ts),
            slice_ts
        )):
            idx = start_idx + offset
            replies_data.extend(replies)

            save_json(replies_data, REPLIES_JSON)
            save_json({"last_processed_index": idx + 1}, PROGRESS_FILE)
            print(f"[{idx+1}/{total}] ts={slice_ts[offset]} → {len(replies)} reply kaydedildi.")

    save_json({"last_processed_index": 0}, PROGRESS_FILE)
    print("Tüm reply’ler çekildi. progress.json sıfırlandı.")

if __name__ == "__main__":
    main()
