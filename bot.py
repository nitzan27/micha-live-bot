import os
import time
import logging
import platform
import subprocess
import google.generativeai as genai
from yt_dlp import YoutubeDL
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()

# SETTINGS
COMMUNITY_ID = "120363422394975601@g.us" # Your Group ID
CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID")
CHECK_INTERVAL = 3600  # Check every 5 minutes (300 seconds)
HISTORY_FILE = "processed_videos.txt"

# Verify keys
if not os.getenv("GEMINI_API_KEY"):
    print("❌ ERROR: Missing GEMINI_API_KEY in .env")
    exit(1)

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# --- STATE MANAGEMENT ---
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return set()
    with open(HISTORY_FILE, "r") as f:
        return set(line.strip() for line in f)

def save_to_history(video_id):
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{video_id}\n")

# --- CORE FUNCTIONS ---

def get_latest_stream_status(channel_id):
    """
    Checks the latest stream. 
    """
    ydl_opts = {
        'cookiefile': 'cookies.txt',
        'quiet': True,
        'extract_flat': True,
        'force_generic_extractor': False,
    }
    streams_url = f"https://www.youtube.com/channel/{channel_id}/streams"
    
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(streams_url, download=False)
            if 'entries' in info and len(info['entries']) > 0:
                return info['entries'][0]
    except Exception as e:
        logging.error(f"Error checking channel: {e}")
    return None

def is_stream_finished(video_id):
    """
    Checks video status. Handles 'Upcoming' streams gracefully 
    by catching the specific yt-dlp error message.
    """
    ydl_opts = {
        'cookiefile': 'cookies.txt',
        'quiet': True,
        'ignore_errors': True,
        'no_warnings': True,
        'ignore_no_formats_error': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web']
            }
        },
        'js_runtimes': {'node': {}},
        'remote_components': ['ejs:github']
    }
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # If standard extraction worked:
            if info:
                if info.get('live_status') == 'is_upcoming':
                    return "UPCOMING"
                if info.get('is_live'):
                    return "LIVE"
                if info.get('was_live') or info.get('duration', 0) > 0:
                    return "FINISHED"
                return "FINISHED"
            
    except Exception as e:
        # yt-dlp throws an error for upcoming streams. We catch it here.
        error_message = str(e).lower()
        if "live event will begin" in error_message or "premiere" in error_message:
            return "UPCOMING"
        
        # If it's a real error, log it
        logging.error(f"Error checking video details: {e}")
        return "ERROR"
    
    return "ERROR"

def download_audio(video_url, video_id):
    output_filename = f"{video_id}.mp3"
    
    if os.path.exists(output_filename):
        os.remove(output_filename)

    ydl_opts = {
        'cookiefile': 'cookies.txt',
        
        'format': 'bestaudio/best', 
        'outtmpl': f'{video_id}.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '64',
        }],
        'quiet': False,
        'no_warnings': True,
        'force_ipv4': True,
        'socket_timeout': 30,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web']
            }
        },
        'js_runtimes': {'node': {}},
        'remote_components': ['ejs:github']
    }
    
    try:
        logging.info(f"⬇️  Downloading audio for {video_id}...")
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        return output_filename
    except Exception as e:
        logging.error(f"Download failed: {e}")
        return None

def summarize_with_gemini(audio_path):
    try:
        logging.info("🧠 Uploading to Gemini...")
        audio_file = genai.upload_file(path=audio_path)
        
        while audio_file.state.name == "PROCESSING":
            print(".", end="", flush=True)
            time.sleep(2)
            audio_file = genai.get_file(audio_file.name)
        print()

        if audio_file.state.name == "FAILED":
            raise ValueError("Gemini failed to process audio.")

        logging.info("🧠 Generating summary in Hebrew...")
        model = genai.GenerativeModel('gemini-flash-latest')
        
        system_prompt = """
        אתה עוזר אנליסט פיננסי מומחה. המשימה שלך היא להאזין ללייב של "מיכה סטוקס" ולסכם אותו בעברית.
        
        מבנה הסיכום:
        📰 **חלק 1: חדשות מאקרו**
        * נקודות עיקריות.

        📈 **חלק 2: ניתוח מניות**
        * עבור כל מניה שנותחה:
        * **$TICKER**: [דעה ורמות טכניות].
        """

        response = model.generate_content([system_prompt, audio_file])
        genai.delete_file(audio_file.name)
        return response.text
    except Exception as e:
        logging.error(f"AI Error: {e}")
        return None

def send_whatsapp_mudslide(message):
    if not COMMUNITY_ID:
        logging.error("❌ No Community ID specified!")
        return False
        
    logging.info(f"🚀 Sending Message to: {COMMUNITY_ID}")

    # Detect OS
    is_windows = platform.system() == "Windows"

    # --- EXECUTION STRATEGY ---
    # Linux: Use local binary to avoid npx overhead/instability
    # Windows: Use npx.cmd
    if is_windows:
        base_cmd = ["npx.cmd", "mudslide"]
    else:
        # On Linux, try to use the local installation first
        local_bin = os.path.join(os.getcwd(), "node_modules", ".bin", "mudslide")
        if os.path.exists(local_bin):
            base_cmd = [local_bin]
        else:
            base_cmd = ["npx", "mudslide"]

    try:
        if is_windows:
            # --- WINDOWS MODE (File Pipe) ---
            # Must use file piping to prevent Hebrew encoding crashes
            temp_file = "temp_message.txt"
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(message)
            
            command = base_cmd + ['send', COMMUNITY_ID, '-']
            
            with open(temp_file, "r", encoding="utf-8") as f_in:
                result = subprocess.run(
                    command,
                    stdin=f_in,
                    capture_output=True,
                    text=True,
                    encoding='utf-8'
                )
            
            if os.path.exists(temp_file):
                os.remove(temp_file)

        else:
            # --- LINUX MODE (Direct Arguments) ---
            # Linux handles Unicode and newlines in arguments perfectly.
            # We pass the message directly to avoid 'nohup' stdin crashes (EBADF).
            command = base_cmd + ['send', COMMUNITY_ID, message]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding='utf-8',
                stdin=subprocess.DEVNULL
            )

        # Check Result
        if result.returncode == 0:
            logging.info(f"   ✅ Sent Successfully!")
            return True
        else:
            logging.error(f"   ❌ Mudslide failed: {result.stderr}")
            return False

    except Exception as e:
        logging.error(f"   ❌ System Error: {e}")
        return False

# --- MAIN AUTOMATION LOOP ---

def run_bot():
    logging.info("🤖 Micha Stocks Automation Bot Started")
    logging.info(f"⏳ Checking every {CHECK_INTERVAL} seconds...")
    
    while True:
        try:
            processed_ids = load_history()
            latest_video = get_latest_stream_status(CHANNEL_ID)
            
            if latest_video:
                v_id = latest_video['id']
                v_title = latest_video['title']
                
                if v_id in processed_ids:
                    # To reduce log spam, we print a dot or nothing, 
                    # but here is a message so you know it's working
                    logging.info(f"💤 Latest stream '{v_title}' already processed.")
                else:
                    logging.info(f"🔎 Found new potential video: {v_title}")
                    
                    status = is_stream_finished(v_id)
                    
                    if status == "FINISHED":
                        logging.info("🎬 Stream confirmed FINISHED. Starting process...")
                        audio_path = download_audio(latest_video['url'], v_id)
                        
                        if audio_path:
                            summary = summarize_with_gemini(audio_path)
                            
                            if summary:
                                full_text = f"*{v_title}*\n{latest_video['url']}\n\n{summary}"
                                success = send_whatsapp_mudslide(full_text)
                                
                                if success:
                                    save_to_history(v_id)
                                    os.remove(audio_path)
                                    logging.info("🎉 Cycle Complete.")
                            else:
                                logging.error("❌ Summary failed.")
                        else:
                            logging.error("❌ Download failed.")
                            
                    elif status == "LIVE":
                        logging.info(f"🔴 Stream '{v_title}' is currently LIVE. Waiting...")
                    elif status == "UPCOMING":
                        logging.info(f"⏰ Stream '{v_title}' is UPCOMING. Waiting...")

            else:
                logging.warning("⚠️ Could not fetch channel info.")

        except Exception as e:
            logging.error(f"🔥 Critical Loop Error: {e}")

        time.sleep(CHECK_INTERVAL)

def run_test():
    logging.info("🚀 STARTING LIVESTREAM SCAN")
    
    # 1. Specifically get the latest LIVESTREAM
    video = get_latest_livestream(CHANNEL_ID)
    
    if not video:
        logging.error("❌ No livestreams found.")
        return

    logging.info(f"📺 Found Livestream: {video['title']}")
    
    # 2. Download
    audio_file = download_audio(video['link'], video['id'])
    
    if audio_file and os.path.exists(audio_file):
        # 3. Summarize
        summary = summarize_with_gemini(audio_file)
        
        if summary:
            # Construct message
            full_text = f"*סיכום לייב חדש: {video['title']}*\n{video['link']}\n\n{summary}"
            
            # 4. Send
            send_whatsapp_mudslide_file(full_text)
        else:
            logging.error("❌ Summary generation failed or returned empty.")
            
        # Cleanup
        try:
            os.remove(audio_file)
        except:
            pass
        logging.info("🧹 Done.")
    else:
        logging.error("❌ Download failed.")

if __name__ == "__main__":
    run_bot()
    # run_test()  # Uncomment this line to run the test function instead of the main bot loop