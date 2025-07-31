Below is a general guide on how to use and run these two scripts, **ExportThreadWithoutReplies.py** and **ExportReplies.py**. Both scripts interact with the Slack API to retrieve data from a specific Slack channel, but each focuses on different parts of the conversation.

---

## 1. Prepare Your `config.json`
Create a `config.json` file **in the same directory** as the scripts with the following format:

```json
{
    "SLACK_TOKEN": "xoxb-1234-...",
    "SLACK_COOKIE": "YourCookieStringHere",
    "CHANNEL_ID": "CXXXXXX"
}
```

### Where to find these values:

1. **Channel ID**  
   - Open Slack (the web version) and navigate to the channel you’re interested in.  
   - Look at the URL in your browser, for example:  
     ```
     https://app.slack.com/client/TXXXXXX/CYYYYYYY
     ```
     The part after `/client/` and `TXXXXXX/` is `CYYYYYYY`. That’s the **Channel ID**.
   - Alternatively, if you see a link in the form `https://slack.com/app_redirect?channel=CYYYYYYY`, then `CYYYYYYY` is the **Channel ID**.
![image](https://github.com/user-attachments/assets/d257daf4-488c-4ed0-9770-97cce492edd8)


2. **Slack Token and Cookie**  
   - Open your **browser’s Developer Tools** → **Network** tab.  
   - Navigate (or refresh) the Slack channel to see all network requests.  
   - Look for a request containing `conversations.history` or any Slack API endpoint.  
   - Right-click on the request → **Copy as cURL**.  
   - Paste the cURL command into Postman or a text editor to inspect its headers.  
   - In the headers, find `Authorization: Bearer xoxb-...` (this is your **Slack Token**).  
   - Find the `Cookie: ...` header value (this is your **Slack Cookie**).  
   - Copy both into your `config.json` as shown above.
![image](https://github.com/user-attachments/assets/daf7e553-7f75-4f46-9a8d-2b415c6f999c)
![image](https://github.com/user-attachments/assets/281149a8-7249-4bea-b91d-bd27568b46d9)


---

## 2. **ExportThreadWithoutReplies.py** – Fetch Main Thread Messages
1. **What does it do?**  
   - This script fetches **main thread messages** (messages with `reply_count > 0`, meaning they have replies) from the given Slack channel.
   - It saves the results in a file named `threads.json`.

2. **How to run it:**
   1. Make sure your `config.json` file is properly filled in (Token, Cookie, Channel ID).
   2. Open a terminal/command prompt in the same directory as `ExportThreadWithoutReplies.py` and run:
      ```bash
      python ExportThreadWithoutReplies.py
      ```
   3. The script will connect to Slack and gather all thread-starting messages.
   4. When finished, you should see a new file called `threads.json` in your directory.

3. **Output Files:**
   - **threads.json**: Contains a list of JSON objects, each representing a main thread message (including `ts`, `text`, `reply_count`, etc.).

---

## 3. **ExportReplies.py** – Fetch Replies to Each Thread
1. **What does it do?**  
   - This script uses the `threads.json` file created by **ExportThreadWithoutReplies.py** to find each thread’s `ts` (timestamp).
   - Then, for each thread, it retrieves **all replies** (the messages inside that thread).
   - It stores those replies in `replies.json` and also keeps track of progress in a file called `progress.json` (so it can resume if interrupted).

2. **How to run it:**
   1. **Run it only after** you have successfully run `ExportThreadWithoutReplies.py` (so you have `threads.json`).
   2. In a terminal/command prompt, run:
      ```bash
      python ExportReplies.py
      ```
   3. The script loads `threads.json`, iterates over each thread, and fetches replies from Slack.
   4. Replies are saved to `replies.json`. Progress is logged in `progress.json`.

3. **Output Files:**
   - **replies.json**: Contains all fetched replies from all threads in the channel.
   - **progress.json**: Tracks the last processed thread index.  
     - If you re-run the script, it checks `progress.json` to skip re-fetching.  
     - At the end of a successful run, it may reset to 0 (depending on the version of the script you have) so you can safely export another channel if needed.

---

## 4. Workflow Summary

1. **Configure**: Ensure `config.json` is filled out correctly with your Slack Token, Cookie, and Channel ID.  
2. **Run ExportThreadWithoutReplies**:  
   ```bash
   python ExportThreadWithoutReplies.py
   ```
   - Wait for it to finish.  
   - Check that `threads.json` has been created and contains your thread data.
3. **Run ExportReplies**:  
   ```bash
   python ExportReplies.py
   ```
   - This will read `threads.json` and fetch all replies (per thread).  
   - Check `replies.json` for the collected reply data.  
   - If you stop it halfway through, re-run to resume from where it left off.
4. **Check your files**:  
   - **threads.json** contains the main threads.  
   - **replies.json** contains all the replies for those threads.

---

## 5. Troubleshooting

- **Authentication Errors**:  
  - If you receive 401/403 errors or Slack says “invalid_auth”, re-check your Slack Token and Cookie in `config.json`.
- **Rate Limits (429)**:  
  - The script automatically handles Slack’s rate limiting by waiting when it detects a 429 error. If Slack does not send a `Retry-After` header, the script will print a message so you can wait manually.
- **Missing Data**:  
  - Make sure your Slack user account has the necessary permissions for reading conversation history in that channel.

By following these steps, you’ll export Slack threads (main messages) and all of their replies into JSON files.


## 🆕 New Features v2.0

### 1. Automatic `since_ts` Tracking
- Reads the last processed message’s `ts` value from `since_ts.txt`.  
- If the file is missing or empty, pulls the entire history on first run.  
- After fetching, writes the highest `ts` back to `since_ts.txt`.  
- Ensures each subsequent run only processes **newer** messages.

### 2. Parallel Permalink & Reply Retrieval
- Uses `concurrent.futures.ThreadPoolExecutor` to fire up to **10** concurrent `chat.getPermalink` calls for thread-starter messages.  
- Replies fetching script uses up to **5** parallel workers against `conversations.replies`.  
- Results are **sorted by `ts`** to preserve chronological order.

### 3. Robust Rate-Limit Handling
- On HTTP 429 (rate-limit), reads `Retry-After` header and **sleeps** before retrying.  
- Applies this logic uniformly across `conversations.history`, `chat.getPermalink` and `conversations.replies` endpoints.  
- Prevents hard failures on large channels or big threads.

### 4. Resume-able Progress Tracking
- Replies script records “last processed index” in `progress.json` after each thread.  
- On restart, resumes from that index—no need to re-fetch already handled threads.  
- Once all threads are done, `progress.json` resets to zero for the next full export.

### 5. File Outputs
- **Threads:**  
  - `threads.json` (full JSON dump)  
  - Optional: `threads.csv` for spreadsheet-friendly output  
- **Replies:**  
  - `replies.json` (accumulated thread replies)  
- **Tracker Files:**  
  - `since_ts.txt` (last `ts` checkpoint)  
  - `progress.json` (reply-fetch index)

---

#### Example Workflow

1. **First Run:**  
   - `since_ts.txt` is empty or missing → fetch all threads via `conversations.history`.  
   - Write the newest `ts` into `since_ts.txt`.

2. **Subsequent Runs:**  
   - Read `since_ts` → fetch only threads newer than that value.  
   - Replies script picks up from its `progress.json` checkpoint.

3. **Inspecting Results:**  
   - Use `threads.json` & `replies.json` to see a fully chronological export of all threads and their replies.  
