import requests
import time
import json
import os


# Filenames used by the script:
THREADS_JSON = "threads.json"      # Previously retrieved thread main messages
REPLIES_JSON = "replies.json"      # Where the replies will be accumulated
PROGRESS_FILE = "progress.json"    # Track progress (index) so the process can resume later


def load_config(config_path='config.json'):
    """
    Load SLACK_TOKEN, SLACK_COOKIE, and CHANNEL_ID from a config.json file.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"{config_path} not found. Please create a config.json with token, cookie, and channel information."
        )

    with open(config_path, 'r', encoding='utf-8') as file:
        config = json.load(file)
    return config


def main():
    print("Starting the reply-fetching script...")

    # 1) Load configuration
    config = load_config()
    TOKEN = config.get("SLACK_TOKEN")
    COOKIE = config.get("SLACK_COOKIE", "")
    CHANNEL = config.get("CHANNEL_ID")

    if not TOKEN or not CHANNEL:
        raise ValueError("SLACK_TOKEN or CHANNEL_ID not found in config.json.")

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Cookie": COOKIE
    }

    # 2) Read threads.json and gather 'ts' values
    if not os.path.exists(THREADS_JSON):
        raise FileNotFoundError(
            f"{THREADS_JSON} not found. Please run the code that exports main thread messages first."
        )

    thread_ts_list = []
    with open(THREADS_JSON, "r", encoding="utf-8") as file:
        threads_data = json.load(file)
        for thread in threads_data:
            thread_ts = thread.get("ts")
            if thread_ts:
                thread_ts_list.append(thread_ts)

    # 3) If progress.json exists, resume from the last processed index
    start_index = 0
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as progress_file:
            try:
                progress_data = json.load(progress_file)
                start_index = progress_data.get("last_processed_index", 0)
            except json.JSONDecodeError:
                pass

    # 4) Read replies.json if it exists; otherwise start with an empty list
    if os.path.exists(REPLIES_JSON):
        with open(REPLIES_JSON, "r", encoding="utf-8") as rfile:
            try:
                replies_data = json.load(rfile)
            except json.JSONDecodeError:
                replies_data = []
    else:
        replies_data = []

    total_threads = len(thread_ts_list)
    print(f"Total threads to process: {total_threads}")

    # 5) Iterate over thread_ts_list and fetch replies
    for i, t_ts in enumerate(thread_ts_list[start_index:], start=start_index):

        # Print progress info every 1000 threads
        if i > 0 and i % 1000 == 0:
            print(f"{i} threads processed so far...")

        url = "https://slack.com/api/conversations.replies"
        limit = 1000
        cursor = None

        while True:
            data = {
                "channel": CHANNEL,
                "ts": t_ts,
                "limit": limit
            }
            if cursor:
                data["cursor"] = cursor

            response = requests.post(url, headers=headers, data=data)

            # Handle rate limiting (HTTP 429)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    wait_time = int(retry_after)
                    print(f"Rate limit exceeded. Waiting for {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue

            result = response.json()

            # Check for any errors in the API response
            if not result.get("ok"):
                if result.get('error') == 'ratelimited':
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        wait_time = int(retry_after)
                        print(f"Rate limit exceeded. Waiting for {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print("Rate limit exceeded, but no Retry-After header found. Please wait manually.")
                        break
                else:
                    print("Error encountered:", result)
                    break

            # The first message is usually the main thread message, so skip it
            messages = result.get("messages", [])
            replies = [
                m for m in messages
                if m.get("thread_ts") and m.get("ts") != m.get("thread_ts")
            ]

            # Accumulate replies
            replies_data.extend(replies)

            # Check if there is more data to fetch
            next_cursor = result.get("response_metadata", {}).get("next_cursor")
            if not next_cursor:
                break
            cursor = next_cursor

        # Save progress after processing each thread
        with open(PROGRESS_FILE, "w", encoding="utf-8") as pf:
            json.dump({"last_processed_index": i + 1}, pf, ensure_ascii=False, indent=4)
        print(f"Thread {i+1}/{total_threads} processed. Progress saved.")

        # Update replies.json (alternatively, you could do this in larger batches)
        with open(REPLIES_JSON, "w", encoding="utf-8") as wfile:
            json.dump(replies_data, wfile, ensure_ascii=False, indent=4)

    print("All replies have been successfully fetched and saved to the JSON file!")

    # 6) Reset progress.json to 0 so it won't interfere with future channel exports
    with open(PROGRESS_FILE, "w", encoding="utf-8") as pf:
        json.dump({"last_processed_index": 0}, pf, ensure_ascii=False, indent=4)
    print("Progress has been reset to 0 in progress.json. You can safely export another channel now.")


if __name__ == "__main__":
    main()
