import csv
import requests
import time
import json
import os


def load_config(config_path='config.json'):
    """
    Load SLACK_TOKEN, SLACK_COOKIE, and CHANNEL_ID from a config.json file.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"{config_path} not found. Please create a config.json containing the token, cookie, and channel information."
        )

    with open(config_path, 'r', encoding='utf-8') as file:
        config = json.load(file)
    return config


def fetch_only_thread_messages(token, cookie, channel_id):
    """
    Fetch only thread-starting messages (i.e., reply_count > 0) from a Slack channel
    and retrieve their permalink.
    """
    print("Fetching thread-starting messages from the Slack channel...")

    BASE_URL = "https://slack.com/api"
    history_url = f"{BASE_URL}/conversations.history"
    params = {
        'channel': channel_id,
        'limit': 1000
    }
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Cookie': cookie
    }

    all_threads = []
    next_cursor = None
    total_messages = 0

    while True:
        if next_cursor:
            params['cursor'] = next_cursor

        try:
            response = requests.get(history_url, headers=headers, params=params)

            # Handle rate limiting (HTTP 429)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 10))
                print(f"Rate limit reached. Waiting for {retry_after} seconds...")
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            data = response.json()

            if not data.get('ok'):
                print(f"Error: {data.get('error')}")
                break

            messages = data.get('messages', [])
            total_messages += len(messages)

            # Only collect messages with reply_count > 0
            for message in messages:
                if 'reply_count' in message and message['reply_count'] > 0:
                    # Retrieve the permalink for this message
                    thread_permalink = get_permalink_for_message(
                        token, cookie, channel_id, message.get('ts', '')
                    )

                    all_threads.append({
                        'ts': message.get('ts', ''),
                        'user': message.get('user', 'Unknown'),
                        'text': message.get('text', '').replace('\n', ' '),
                        # A thread-starting message's thread_ts is the same as ts
                        'thread_ts': message.get('ts', ''),
                        'reply_count': message.get('reply_count', 0),
                        'subtype': message.get('subtype', 'normal_message'),
                        'thread_url': thread_permalink
                    })

                    preview_text = message.get('text', '').strip()[:50]
                    print(f"Found a thread: {preview_text}... | reply_count: {message.get('reply_count', 0)}")

            # Check for the next cursor
            next_cursor = data.get('response_metadata', {}).get('next_cursor')
            if not next_cursor:
                print("No more messages to fetch.")
                break

            print(f"Continuing... Total messages processed so far: {total_messages}")
            time.sleep(1)

        except requests.exceptions.RequestException as error:
            print(f"Request error: {error}")
            break

    return all_threads


def get_permalink_for_message(token, cookie, channel_id, message_ts):
    """
    Retrieve the permalink (URL) for a given message in a Slack channel.
    """
    BASE_URL = "https://slack.com/api"
    permalink_url = f"{BASE_URL}/chat.getPermalink"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Cookie': cookie
    }
    params = {
        'channel': channel_id,
        'message_ts': message_ts
    }

    while True:
        try:
            response = requests.get(permalink_url, headers=headers, params=params)

            # Handle rate limiting (HTTP 429)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 10))
                print(f"Rate limit reached while fetching permalink. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                continue

            response.raise_for_status()
            data = response.json()

            if data.get('ok'):
                return data.get('permalink', '')
            else:
                print(f"Could not retrieve permalink: {data.get('error')}")
                return ""

        except requests.exceptions.RequestException as error:
            print(f"Error while requesting permalink: {error}")
            return ""


def save_threads_to_csv(threads, filename='threads.csv'):
    """
    Save the collected thread messages to a CSV file (including thread_url).
    """
    with open(filename, mode='w', encoding='utf-8', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(['ts', 'user', 'text', 'thread_ts', 'reply_count', 'subtype', 'thread_url'])

        for thread in threads:
            writer.writerow([
                thread['ts'],
                thread['user'],
                thread['text'],
                thread['thread_ts'],
                thread['reply_count'],
                thread['subtype'],
                thread['thread_url']
            ])

    print(f"Thread messages have been saved to {filename}. Total threads: {len(threads)}")


def save_threads_to_json(threads, filename='threads.json'):
    """
    Save the collected thread messages to a JSON file.
    """
    with open(filename, mode='w', encoding='utf-8') as file:
        json.dump(threads, file, indent=4, ensure_ascii=False)

    print(f"Thread messages have been saved to {filename}. Total threads: {len(threads)}")


def main():
    print("Starting the script...")

    # Load configuration from config.json
    config = load_config()
    token = config.get('SLACK_TOKEN')
    cookie = config.get('SLACK_COOKIE', '')
    channel_id = config.get('CHANNEL_ID')

    if not token or not channel_id:
        raise ValueError("SLACK_TOKEN and CHANNEL_ID not found in config.json.")

    print(f"Fetching thread messages from channel ID: {channel_id}...")
    threads = fetch_only_thread_messages(token, cookie, channel_id)
    print(f"Total thread messages found: {len(threads)}")

    # Save to JSON (you can also call save_threads_to_csv if you need a CSV file)
    save_threads_to_json(threads, filename='threads.json')
    print("Execution completed.")


if __name__ == "__main__":
    main()
