# Google Calendar Setup — Step by Step

This is a **one-time** setup. After it's done, AI-OS will automatically create
Google Calendar events whenever you add tasks with a due date.

Total time: ~10 minutes. You'll only do this once per Google account.

---

## What you're about to do

You're going to tell Google: "this Python script on my laptop is allowed to
add events to my calendar." Google calls this an **OAuth client**. You'll:

1. Create a Google Cloud project (free, no billing needed)
2. Turn on the Calendar API for that project
3. Configure who's allowed to use the app (just you)
4. Download a small JSON file that proves the script is yours
5. Run a one-time command that opens a browser and asks for your permission

That's it.

---

## Part 1 — Create a Google Cloud project

1. Open https://console.cloud.google.com/ and sign in with the Google account
   whose calendar you want to use.
2. At the very top of the page, next to the "Google Cloud" logo, there's a
   **project picker** (it'll say "Select a project" or show an existing project).
   Click it.
3. In the dialog that opens, click **NEW PROJECT** (top-right).
4. Project name: type `AI-OS` (or anything). Leave organization as-is.
   Click **CREATE**.
5. Wait ~10 seconds. A notification will say "Project created."
6. Click the project picker again and **select your new `AI-OS` project**.
   ⚠ If you skip this, the rest of the steps will happen on the wrong project.

---

## Part 2 — Enable the Calendar API

1. In the left sidebar (hamburger menu ☰ if it's collapsed), go to:
   **APIs & Services → Library**
   Or use this direct link: https://console.cloud.google.com/apis/library
2. In the search box, type `Google Calendar API`.
3. Click the result titled **Google Calendar API**.
4. Click the blue **ENABLE** button.
5. Wait a few seconds. The page will reload to a "Google Calendar API" overview.

---

## Part 3 — Configure the OAuth consent screen

Google requires you to describe the app before it'll let it talk to your account.

1. In the left sidebar: **APIs & Services → OAuth consent screen**
   (https://console.cloud.google.com/apis/credentials/consent).
2. If it asks **User Type**, choose **External** → **CREATE**.
   *(External just means "a regular Google account, not a Google Workspace org."
   You're the only user — there's no public app being published.)*
3. **App information** screen:
   - App name: `AI-OS`
   - User support email: your own email (the dropdown only has yours)
   - Developer contact email (at the bottom): your own email again
   - Everything else: leave blank
   - Click **SAVE AND CONTINUE**
4. **Scopes** screen: don't add anything. Click **SAVE AND CONTINUE**.
5. **Test users** screen: click **+ ADD USERS**, type your own Gmail address,
   click **ADD**, then **SAVE AND CONTINUE**.
   ⚠ This step matters. If your email isn't here, Google will block you in Part 5.
6. **Summary** screen: click **BACK TO DASHBOARD**.

You can leave the app in "Testing" mode forever — that's fine for personal use.

---

## Part 4 — Create the OAuth credentials

This is the file the Python script needs.

1. In the left sidebar: **APIs & Services → Credentials**
   (https://console.cloud.google.com/apis/credentials).
2. Click **+ CREATE CREDENTIALS** at the top → **OAuth client ID**.
3. Application type: **Desktop app**.
   ⚠ Must be Desktop app, not Web application. Web won't work for this script.
4. Name: `AI-OS local` (anything is fine).
5. Click **CREATE**.
6. A dialog appears: "OAuth client created." Click **DOWNLOAD JSON**.
   - You'll get a file like `client_secret_1234-abcd.apps.googleusercontent.com.json`.
7. **Rename it to `credentials.json`** and move it to:

   ```
   c:\Users\Manuel\Downloads\workflow-project\ai-os\data\credentials.json
   ```

   The exact path matters. The file must be named `credentials.json` and must
   live in `ai-os/data/`.

8. Verify it's there. In the IDE terminal:

   ```
   ls ai-os/data/credentials.json
   ```

   If that prints the file, you're good.

---

## Part 5 — Run the one-time authorization

Now we tell the script to open a browser, log in, and remember the permission.

1. Open a terminal **inside the `ai-os/` directory**:

   ```
   cd c:\Users\Manuel\Downloads\workflow-project\ai-os
   ```

2. Run:

   ```
   python -c "from tasks.calendar_sync import get_calendar_service; get_calendar_service()"
   ```

3. Your default browser will open to a Google sign-in page.
   - Pick the same Google account you added as a test user in Part 3.

4. **You will see a scary warning:** "Google hasn't verified this app."
   This is normal — your app is in Testing mode and only you use it.
   - Click **Advanced** (small link, bottom-left of the warning).
   - Click **Go to AI-OS (unsafe)**.

5. Google asks for permission to "See, edit, share, and permanently delete all
   the calendars you can access using Google Calendar." Click **Continue**.

6. The browser will show "**The authentication flow has completed.**
   You may close this window."

7. Back in the terminal, the command exits silently (no output = success).

8. Verify the token was saved:

   ```
   ls ai-os/data/google_token.json
   ```

   If that file exists, you're done with setup. From now on the script reuses
   this token automatically — no browser, no prompts.

---

## Part 6 — Test it end-to-end

1. Make sure the API is running (or restart it so it picks up the new column):

   ```
   cd c:\Users\Manuel\Downloads\workflow-project\ai-os
   uvicorn api.main:app --reload --port 8000
   ```

2. In **another terminal**:

   ```
   curl -X POST http://localhost:8000/api/tasks ^
     -H "Content-Type: application/json" ^
     -d "{\"title\":\"Test calendar task\",\"due_date\":\"2026-05-07\",\"source\":\"manual\"}"
   ```

   *(That's the Windows `cmd` form. In bash/PowerShell use `\` line breaks
   and single-quoted JSON instead.)*

3. The response should include a non-null `"calendar_event_id"`:

   ```json
   {"id": 42, "title": "Test calendar task", "due_date": "2026-05-07",
    "calendar_event_id": "abc123xyz...", ...}
   ```

4. Open https://calendar.google.com/ → jump to **May 7, 2026**.
   You should see an all-day event titled **"Test calendar task"**.

---

## What to do if something breaks

| Symptom | Likely cause | Fix |
|---|---|---|
| `calendar_event_id` is `null` in the curl response | Calendar sync silently failed | Check uvicorn's terminal — it logs `Calendar sync failed: <reason>` |
| `FileNotFoundError: ...credentials.json` | File not in the right place or wrong name | Re-do Part 4 step 7. Path must be `ai-os/data/credentials.json` |
| Browser says "Access blocked: AI-OS has not completed verification" | You skipped the test-user step | Part 3 step 5 — add your email under Test users |
| Browser says "Error 400: redirect_uri_mismatch" | Created a "Web application" instead of "Desktop app" | Part 4 step 3 — delete that credential and re-create as Desktop app |
| Token expired weeks later | Refresh token revoked | Delete `data/google_token.json` and re-run Part 5 |

If you see something else, paste the error and I'll diagnose.

---

## How it behaves once set up

- **Task created with a due_date** → all-day event on that date.
- **Task marked `done`** → event title gets a `✓ ` prefix.
- **Task marked `skipped`** → event title gets a `→ ` prefix and moves to the next day.
- **Task with no due_date** → no calendar event (nothing to mirror).

The task database is the source of truth. The calendar event is just a mirror —
if Google is unreachable, task creation still succeeds and you'll see a
`Calendar sync failed:` warning in the API logs.
