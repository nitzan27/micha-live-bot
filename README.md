# Micha Stocks Automation Bot

A Python-based automation tool that monitors a financial YouTube channel for live streams, analyzes completed stream audio using Google Gemini, and automatically distributes a structured Hebrew summary to a designated WhatsApp community.

---

## 📋 Features

- **Automated Monitoring:** Periodically scans a target YouTube Channel ID using `yt-dlp` to detect new live streams or uploads.
- **Audio Extraction & Decryption:** Downloads stream audio and processes YouTube's modern signature challenges safely using a local Node.js JavaScript runtime.
- **AI-Powered Summarization:** Uploads the audio file to Google Gemini to produce a structured recap in Hebrew, highlighting macro updates and technical stock levels.
- **WhatsApp Integration:** Dispatches the final message to your target WhatsApp Community/Group ID using the Mudslide CLI tool.
- **Duplicate Prevention:** Tracks processed stream IDs to ensure summaries are only compiled and sent once.

---

## 🛠️ Tech Stack

- **Language:** Python 3.12+
- **AI Analysis:** Google Gemini API (`google-generativeai`)
- **Download Engine:** `yt-dlp` (configured with Node/EJS for signature solving)
- **WhatsApp API Bridge:** Mudslide (Node.js)
- **Deployment:** Standard compatibility for both Windows (PowerShell development) and Linux (Oracle Cloud Ubuntu deployment)

---

## 🍪 Managing YouTube Cookies (Crucial)

To bypass automated scraper blocks ("Sign in to confirm you're not a bot"), the bot uses standard session cookies. To prevent YouTube from immediately invalidating (rotating) these cookies, follow this export method precisely:

1. Close all active private windows, then open a fresh **Chrome Incognito window** (`Ctrl + Shift + N`).
2. Go to YouTube and sign in to your Google account.
3. Open any video and let it play for 5–10 seconds.
4. Click your **"Get cookies.txt LOCALLY"** extension (or a similar cookie exporter) and choose **Export**.
5. **Do not log out of YouTube.** Close the Incognito window immediately. _(This leaves your session active on Google's servers but stops the local browser from actively rotating the keys)._
6. Overwrite your local `cookies.txt` file in the root directory with the copied contents of the downloaded file.

> **Troubleshooting:** If the bot logs a `Sign in to confirm you're not a bot` error, run `./venv/bin/pip install -U "yt-dlp[default]"` inside your virtual environment to update the decryption scripts, then repeat the cookie export steps above.

---

## 🚀 Quick Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/nitzan27/micha-live-bot.git
   cd micha-live-bot

   ```

2. **Set up the virtual environment:**

   python -m venv venv
   source venv/bin/activate # On Windows: .\venv\Scripts\activate
   pip install -r requirements.txt

3. **Install Mudslide (WhatsApp CLI):**

   npm install mudslide

4. **Configure your Environment Variables: Create a .env file in the root directory:**

   GEMINI_API_KEY=your_gemini_api_key_here
   YOUTUBE_CHANNEL_ID=your_youtube_channel_id_here

5. **Scan WhatsApp QR Code:**

   npx mudslide login

6. **Run the Bot (Background Mode):**

   nohup ./venv/bin/python3 bot.py > bot.log 2>&1 &
