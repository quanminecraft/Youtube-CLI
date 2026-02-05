import os
import sys
import subprocess
import time
import json
import isodate
import re
import signal
import datetime
import uuid # For unique IPC pipe names
import yt_dlp # For downloading video/audio
import imageio_ffmpeg # For bundling ffmpeg binary automatically
from pyfiglet import Figlet # For ASCII Art Banner
from mutagen import File as MutagenFile # For Metadata
import json # For IPC communication
import video_player # Separate video handling
import speed_test # Internet Speed Test


try:
    import numpy as np
    import pyaudio
    HAVE_REAL_VIZ = True
except ImportError:
    HAVE_REAL_VIZ = False

# Cross-platform input handling
if os.name == 'nt':
    import msvcrt
else:
    import sys
    import tty
    import termios
    import select

class AudioAnalyzer:
    def __init__(self):
        self.chunk = 1024
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 44100
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.data_buffer = np.zeros(self.chunk, dtype=np.int16)
        
        # Try to open default input
        try:
            self.stream = self.p.open(format=self.format,
                                      channels=self.channels,
                                      rate=self.rate,
                                      input=True,
                                      frames_per_buffer=self.chunk)
        except Exception:
            self.stream = None

    def get_levels(self, num_bars):
        if not self.stream: return [0.0] * num_bars
        
        try:
            # Non-blocking read (throw away overflow to stay real-time)
            if self.stream.get_read_available() > self.chunk:
                 data = self.stream.read(self.chunk, exception_on_overflow=False)
                 indata = np.frombuffer(data, dtype=np.int16)
                 
                 # FFT
                 fft_data = np.abs(np.fft.rfft(indata))
                 fft_data = fft_data[:len(fft_data)//2] # Lower half frequency
                 
                 # Logarithmic scaling for audio feeling
                 # Split fft_data into 'num_bars' chunks
                 chunk_size = len(fft_data) // num_bars
                 levels = []
                 for i in range(num_bars):
                     start = i * chunk_size
                     end = start + chunk_size
                     avg = np.mean(fft_data[start:end])
                     # Normalize (heuristic value 5000000 depends on input gain)
                     # Apply log scalling: log10(val) typically 0-5
                     val = 0
                     if avg > 0:
                         val = np.log10(avg) / 5.0 
                     levels.append(min(1.0, max(0.0, val)))
                 return levels
        except: pass
        return [0.0] * num_bars

    def close(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()

class InputHandler:
    @staticmethod
    def kbhit():
        if os.name == 'nt':
            return msvcrt.kbhit()
        else:
            dr, dw, de = select.select([sys.stdin], [], [], 0)
            return dr != []

    @staticmethod
    def getch():
        if os.name == 'nt':
            try:
                ch = msvcrt.getch()
                if ch in (b'\x00', b'\xe0'): # Arrow keys prefix
                    ch2 = msvcrt.getch()
                    if ch2 == b'H': return 'UP'
                    if ch2 == b'P': return 'DOWN'
                    if ch2 == b'K': return 'LEFT'
                    if ch2 == b'M': return 'RIGHT'
                    return '' # Unknown special key
                
                # Standard keys
                if ch == b'\r': return 'ENTER'
                if ch == b'\x08': return 'BACKSPACE'
                return ch.decode('utf-8').lower()
            except UnicodeDecodeError:
                return ''
        else:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
                if ch == '\x1b': # Escape sequence
                    seq = sys.stdin.read(2)
                    if seq == '[A': return 'UP'
                    if seq == '[B': return 'DOWN'
                    if seq == '[C': return 'RIGHT'
                    if seq == '[D': return 'LEFT'
                    return 'ESC'
                if ch == '\r' or ch == '\n': return 'ENTER'
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            return ch.lower()
    
    @staticmethod
    def flush():
        if os.name == 'nt':
            while msvcrt.kbhit():
                msvcrt.getch()
        else:
            while InputHandler.kbhit():
                sys.stdin.read(1)

from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.align import Align
from rich.text import Text
from rich import box
from rich.live import Live
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
from googleapiclient.discovery import build
from rich import box
from rich.live import Live
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
from googleapiclient.discovery import build
from Mode.Interactive import InteractiveMode
from Mode.Classic import ClassicMode
from Function import Search, History, Saved, Offline, Settings, PlayLink, Comments

# Initialize Rich Console
# Force UTF-8 on Windows for Unicode support (Emojis)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

console = Console()

def get_base_path():
    """
    Returns the directory of the executable (if frozen) or the script.
    Ensures data files are always stored next to the app.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_path()

# Constants
KEY_FILE = os.path.join(BASE_DIR, "key.txt")
HISTORY_FILE = os.path.join(BASE_DIR, "history.json")
SAVED_FILE = os.path.join(BASE_DIR, "saved.json")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloaded")
DEFAULT_KEY = "Insert your key here" 

class YouTubeCLI:
    def __init__(self, console, autoplay=True):
        self.console = console
        self.api_key = self.load_api_key()
        self.youtube = None
        self.history = self.load_history()
        self.saved_songs = self.load_saved_songs()
        self.current_video_id = None
        self.autoplay = autoplay
        self.audio_analyzer = None
        
        # Load Config
        config = self.load_config()
        self.volume = config.get("volume", 100)
        self.volume = config.get("volume", 100)
        self.gui_style = config.get("gui_style", "choice") # 'choice' or 'arrow'
        self.main_menu_idx = 0 # Persistent cursor for Main Menu
        
        self.DOWNLOAD_DIR = DOWNLOAD_DIR
        self.input_handler = InputHandler
        self.interactive_ui = InteractiveMode(self, InputHandler)
        self.classic_ui = ClassicMode(self)
        
        self.init_youtube_client()

    # --- Config Management ---
    CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

    def load_config(self):
        defaults = {"gui_style": "choice", "volume": 100}
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    defaults.update(data)
            except:
                pass
        return defaults

    def save_config(self):
        config = {
            "gui_style": self.gui_style,
            "volume": self.volume
        }
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)

    def load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r") as f:
                    return json.load(f)
            except:
                pass
        return []

    def save_history(self):
        with open(HISTORY_FILE, "w") as f:
            json.dump(self.history, f, indent=2)

    def add_to_history(self, video_id, title):
        # Remove if exists to push to top/end (most recent)
        self.history = [h for h in self.history if h['id'] != video_id]
        self.history.append({"id": video_id, "title": title})
        # Keep last 50
        if len(self.history) > 100:
            self.history.pop(0)
        self.save_history()

    def load_saved_songs(self):
        if os.path.exists(SAVED_FILE):
            try:
                with open(SAVED_FILE, "r") as f:
                    return json.load(f)
            except:
                pass
        return []

    def save_saved_songs(self):
        with open(SAVED_FILE, "w") as f:
            json.dump(self.saved_songs, f, indent=2)

    def add_to_saved(self, video_id, title):
        # Check if already exists
        for song in self.saved_songs:
            if song['id'] == video_id:
                console.print("[yellow]Song already saved![/yellow]")
                time.sleep(1)
                return
        
        self.saved_songs.append({"id": video_id, "title": title})
        self.save_saved_songs()
        console.print("[green]Song saved for later![/green]")
        time.sleep(1)

    def load_api_key(self):
        if os.path.exists(KEY_FILE):
            with open(KEY_FILE, "r") as f:
                key = f.read().strip()
                if key:
                    return key
        return DEFAULT_KEY

    def save_api_key(self, key):
        with open(KEY_FILE, "w") as f:
            f.write(key)
        self.api_key = key
        self.init_youtube_client()
        console.print("[green]API Key saved![/green]")

    def init_youtube_client(self):
        try:
            self.youtube = build("youtube", "v3", developerKey=self.api_key)
        except Exception as e:
            console.print(f"[red]Error initializing YouTube API: {e}[/red]")
            self.youtube = None

    def get_video_details(self, video_ids):
        """
        Fetches details (title, duration) for a list of video IDs.
        Returns a dictionary mapping video_id -> {'title': str, 'duration': str}
        """
        if not video_ids:
            return {}
        
        try:
            # Join IDs with comma
            ids_str = ",".join(video_ids)
            request = self.youtube.videos().list(
                part="snippet,contentDetails",
                id=ids_str
            )
            response = request.execute()
            
            details = {}
            for item in response.get("items", []):
                vid_id = item["id"]
                title = item["snippet"]["title"]
                
                # Parse duration
                iso_dur = item["contentDetails"]["duration"]
                dur = isodate.parse_duration(iso_dur)
                
                # Format duration (e.g., 0:04:13 -> 4:13)
                total_seconds = int(dur.total_seconds())
                minutes = total_seconds // 60
                seconds = total_seconds % 60
                formatted_dur = f"{minutes}:{seconds:02d}"
                if minutes >= 60:
                   hours = minutes // 60
                   minutes = minutes % 60
                   formatted_dur = f"{hours}:{minutes:02d}:{seconds:02d}"

                details[vid_id] = {
                    "title": title,
                    "duration": formatted_dur
                }
            return details
        except Exception as e:
            console.print(f"[red]Error fetching details: {e}[/red]")
            return {}

    def sanitize_text(self, text):
        """
        Removes characters that might break CLI table layout.
        Uses wcwidth (if available) to strip non-printable characters.
        Normalizes Unicode to NFKC.
        """
        if not text:
            return ""
            
        import unicodedata
        # 0. Basic Cleanup
        text = text.replace('\t', ' ').replace('\r', '')
        
        # 1. Unicode Normalization
        text = unicodedata.normalize('NFKC', text)

        # 2. wcwidth Filtering (The best way to ensure alignment)
        try:
            from wcwidth import wcwidth
            # Keep only characters with valid width (>= 0)
            # width -1 = non-printable/control
            text = "".join(c for c in text if wcwidth(c) >= 0)
        except ImportError:
            # Fallback: Strip non-BMP if wcwidth missing
            text = "".join(c for c in text if ord(c) <= 0xFFFF)
        
        # 3. Remove Variation Selector-16 and ZWJ (Extra safety)
        text = re.sub(r'[\ufe0f\u200d]', '', text)
        
        return text

    def get_banner_renderable(self):
        f = Figlet(font='ansi_shadow', width=200)
        ascii_art = f.renderText("YOUTUBE CLI")
        text = Text(ascii_art, style="bold #e6a4eb", no_wrap=True, overflow="crop")
        return Group(Align.center(text), Align.center(Text("Youtube Command-Line Player", style="dim white", justify="center")), Text("\n"))

    def print_banner(self):
        console.clear()
        console.print(self.get_banner_renderable())

    def render_interactive_menu(self, title, options, columns, selected_idx, allow_back=True, back_key='BACKSPACE', allow_pagination=True, show_banner=False):
        return self.interactive_ui.render_interactive_menu(title, options, columns, selected_idx, allow_back, back_key, allow_pagination, show_banner)

    def main_menu_interactive(self):
        # Deprecated, redirect to interactive_ui.main_menu if needed, 
        # but main_menu below calls main_menu() directly.
        pass

    def main_menu(self):
        while True:
            if self.gui_style == "arrow":
                choice = self.interactive_ui.main_menu()
            else:
                choice = self.classic_ui.main_menu()
            
            if choice == "1":
                Search.search_ui(self)
            elif choice == "2":
                PlayLink.play_link_ui(self)
            elif choice == "3":
                Saved.saved_songs_ui(self)
            elif choice == "4":
                History.history_ui(self)
            elif choice == "5":
                Settings.settings_ui(self)
            elif choice == "6":
                Offline.offline_mode_ui(self)
            elif choice == "7":
                speed_test.run_test(self.console, self.gui_style, InputHandler)
            elif choice == "0":
                self.console.clear()
                self.kill_proc(None)
                sys.exit(0)

    # Delegates to Function Modules (kept for compatibility or internal calls)
    def saved_songs_ui(self):
        Saved.saved_songs_ui(self)

    def play_history_ui(self):
        History.history_ui(self)

    def settings_ui(self):
        Settings.settings_ui(self)

    def offline_mode_ui(self):
        Offline.offline_mode_ui(self)

    def search_ui(self):
        Search.search_ui(self)

    def play_link_ui(self):
        PlayLink.play_link_ui(self)
    def update_api_key_ui(self):
        console.print(f"Current Key: [dim]{self.api_key}[/dim]")
        new_key = Prompt.ask("Enter new API Key (leave empty to cancel)")
        if new_key:
            self.save_api_key(new_key)

    def remove_from_saved(self, video_id):
        initial_len = len(self.saved_songs)
        self.saved_songs = [s for s in self.saved_songs if s['id'] != video_id]
        if len(self.saved_songs) < initial_len:
            self.save_saved_songs()
            console.print("[green]Song removed from saved![/green]")
        else:
            console.print("[yellow]Song was not in saved list.[/yellow]")
        time.sleep(1)

    def is_saved(self, video_id):
        return any(s['id'] == video_id for s in self.saved_songs)

    def download_video(self, video_id, title):
        if not os.path.exists(DOWNLOAD_DIR):
            os.makedirs(DOWNLOAD_DIR)
            
        # Check if file already exists (Basic sanitization for Windows check)
        # Remove invalid chars for Windows filenames < > : " / \ | ? *
        clean_title = re.sub(r'[<>:"/\\|?*]', '', title)
        target_file = os.path.join(DOWNLOAD_DIR, f"{clean_title}.mp3")
        
        if os.path.exists(target_file):
             console.print(f"\n[yellow]File '{clean_title}.mp3' already exists![/yellow]")
             
             overwrite = "n"
             if self.gui_style == "arrow":
                 options = [
                     {"key": "n", "desc": "NO (Cancel Download)", "style_active": "reverse green"},
                     {"key": "y", "desc": "YES (Overwrite File)", "style_active": "reverse red"}
                 ]
                 # Reuse generic menu logic but simplify columns
                 # We can pass a blank title to skip banner re-printing if we want, but render_interactive_menu clears screen.
                 # Let's let it clear screen, it's cleaner.
                 # Banner is printed inside render_interactive_menu.
                 
                 cols = [("Confirmation", "desc", 40, "center")]
                 # Pass the warning in the title so it persists after clear
                 menu_title = f"[yellow]⚠️ FILE ALREADY EXISTS:[/yellow] {clean_title}\n\nDo you want to download and overwrite it?"
                 selected, _ = self.render_interactive_menu(menu_title, options, cols, 0)
                 if selected:
                     overwrite = selected["key"]
             else:
                 overwrite = Prompt.ask("Download again?", choices=["y", "n"], default="n")
             
             if overwrite == "n":
                 return

        console.print(f"\n[bold green]Download '{title}'[/bold green]")
        
        choice = "0"
        if self.gui_style == "arrow":
            options = [
                {"key": "1", "desc": "Best Audio (MP3 320k) - Larger file"},
                {"key": "2", "desc": "Good Audio (MP3 128k) - Smaller file"},
                {"key": "0", "desc": "Cancel"}
            ]
            cols = [("Quality Option", "desc", 50, "left")]
            
            selected, _ = self.render_interactive_menu(f"Select Quality for: {title}", options, cols, 0)
            if selected:
                choice = selected["key"]
        else:
            console.print("Select Quality:")
            console.print("[1] Best Audio (MP3 320k) - Larger file")
            console.print("[2] Good Audio (MP3 128k) - Smaller file")
            console.print("[0] Cancel")
            choice = Prompt.ask("Select", choices=["1", "2", "0"], default="1")
        
        if choice == "0":
            return
            
        audio_quality = '320' if choice == '1' else '128'
        
        # Get path to bundled ffmpeg binary
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
            'ffmpeg_location': ffmpeg_path, # Explicitly tell yt-dlp where ffmpeg is
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': audio_quality,
            }],
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
                BarColumn(bar_width=None),
                "[progress.percentage]{task.percentage:>3.1f}%",
                "•",
                DownloadColumn(),
                "•",
                TransferSpeedColumn(),
                "•",
                TimeRemainingColumn(),
                console=console
            ) as progress:
                task_id = progress.add_task("Downloading...", filename=title, start=False)
                
                def progress_hook(d):
                    if d['status'] == 'downloading':
                        total = d.get('total_bytes') or d.get('total_bytes_estimate')
                        downloaded = d.get('downloaded_bytes', 0)
                        if total:
                            progress.update(task_id, total=total, completed=downloaded)
                            progress.start_task(task_id)
                    elif d['status'] == 'finished':
                         progress.update(task_id, description="[green]Converting...[/green]", completed=None)

                ydl_opts['progress_hooks'] = [progress_hook]

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
            
            console.print(f"[bold green]Download Complete![/bold green]")
            console.print(f"Saved to: [underline]{DOWNLOAD_DIR}[/underline]")
            time.sleep(2)
        except Exception as e:
            console.print(f"[bold red]Download Failed: {e}[/bold red]")
            console.print("[dim]Make sure ffmpeg is installed/recognized if converting to mp3[/dim]")
            time.sleep(3)

    def show_action_menu(self, selected_video, playlist=None, playlist_index=0):
        """
        Shows action menu for a selected video and handles choice.
        If playlist is provided, plays the entire list instead of just one video.
        """
        video_id = selected_video["id"]
        title = selected_video["title"]
        current_idx = 0
        
        while True:
            # Re-check saved status on every loop to reflect toggles
            is_saved = self.is_saved(video_id)
            save_option_text = "Remove from saved" if is_saved else "Save for later"
            
            if self.gui_style == "arrow":
                options = [
                    {"key": "1", "action": "Play Audio 🎵"},
                    {"key": "V", "action": "Watch Video (MP4) 📺"},
                    {"key": "C", "action": "Read Comments 💬"},
                    {"key": "2", "action": save_option_text},
                    {"key": "3", "action": "Download MP3 ⬇️"},
                    {"key": "4", "action": "Download Video (MP4) 🎞️"},
                    {"key": "0", "action": "Cancel"}
                ]
                
                cols = [("Action", "action", 30, "left")]
                
                if current_idx >= len(options): current_idx = len(options) - 1
                choice_item, current_idx = self.render_interactive_menu(f"Selected: {title}", options, cols, current_idx)
                if not choice_item: return
                
                action = choice_item["key"]
            
            else:
                console.print(f"Selected: [bold]{title}[/bold]")
                console.print(f"Actions:\n[1] Play Audio 🎵\n[V] Watch Video (MP4) 📺\n[C] Read Comments 💬\n[2] {save_option_text}\n[3] Download MP3\n[4] Download MP4\n[0] Cancel")
                action = Prompt.ask("Select action", choices=["1", "V", "v", "C", "c", "2", "3", "4", "0"], default="1")
                action = action.upper()
            
            if action == "1":
                if playlist:
                    # Queue Mode: Play the provided playlist starting from selection, Autoplay OFF
                    self.play_queue(playlist, start_index=playlist_index, enable_autoplay=False)
                else:
                    # Single Mode: Play one video, Autoplay ON (User default)
                    self.play_queue([selected_video], start_index=0, enable_autoplay=self.autoplay)
                continue
            elif action == "V":
                # Video Mode
                # Check for local MP4 first
                clean_title = re.sub(r'[<>:"/\\|?*]', '', title).strip()
                local_mp4 = os.path.join(DOWNLOAD_DIR, f"{clean_title}.mp4")
                
                if os.path.exists(local_mp4):
                    url = local_mp4
                    source_type = "cis_local"
                else:
                    url = f"https://www.youtube.com/watch?v={video_id}"
                    source_type = "cis_net"
                    
                console.print("[dim]Stopping background audio utils...[/dim]")
                if HAVE_REAL_VIZ and hasattr(self, 'audio_analyzer') and self.audio_analyzer:
                     try:
                         self.audio_analyzer.close()
                         self.audio_analyzer = None
                     except: pass
                
                video_player.play_video(url, title, self.console)
                continue
            elif action == "C":
                Comments.show_comments(self, video_id, title)
                continue
            elif action == "2":
                if is_saved:
                    self.remove_from_saved(video_id)
                else:
                    self.add_to_saved(video_id, title)
                continue
            elif action == "3":
                self.download_content(video_id, title, "mp3")
                continue
            elif action == "4":
                self.download_content(video_id, title, "mp4")
                continue
            elif action == "0":
                return

    def offline_mode_ui(self):
        if self.gui_style == "arrow":
            self.interactive_ui.offline_mode_ui()
        else:
            self.classic_ui.offline_mode_ui()

    # Redundant methods moved to Mode modules. 
    # Left as stubs/redirects in case of unforeseen calls, though mostly unused now.
    def offline_all_songs(self, filter_mode="all"):
        # This logic is now handled inside interactive_ui or classic_ui
        pass
        
    def handle_offline_selection(self, item, filter_mode="all"):
        # This logic is now handled inside interactive_ui or classic_ui
        pass

    def extract_video_id(self, url):
        """
        Extracts 11-character YouTube video ID from URL using Regex.
        Matches: youtube.com/watch?v=ID, youtu.be/ID, shorts/ID, embed/ID
        """
        # Regex covering most YouTube URL formats
        regex = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
        match = re.search(regex, url)
        if match:
            return match.group(1)
        return None





    def get_downloaded_path(self, title):
        """
        Checks if a song with the given title exists in the download directory.
        Returns absolute path if found, else None.
        """
        if not title: return None
        # Same sanitization as download_video
        clean_title = re.sub(r'[<>:"/\\|?*]', '', title).strip()
        
        mp3_path = os.path.join(DOWNLOAD_DIR, f"{clean_title}.mp3")
        if os.path.exists(mp3_path):
            return mp3_path
            
        mp4_path = os.path.join(DOWNLOAD_DIR, f"{clean_title}.mp4")
        if os.path.exists(mp4_path):
            return mp4_path
            
        return None

    def get_download_status(self, title):
        """Returns dict indicating presence of mp3 and mp4."""
        if not title: return {"mp3": False, "mp4": False}
        clean_title = re.sub(r'[<>:"/\\|?*]', '', title).strip()
        
        mp3_path = os.path.join(DOWNLOAD_DIR, f"{clean_title}.mp3")
        mp4_path = os.path.join(DOWNLOAD_DIR, f"{clean_title}.mp4")
        
        return {
            "mp3": os.path.exists(mp3_path),
            "mp4": os.path.exists(mp4_path)
        }

    def download_content(self, video_id, title, format_type='mp3'):
        """
        Downloads content in specified format (mp3 or mp4).
        fetches available qualities for MP4.
        """
        if not os.path.exists(DOWNLOAD_DIR):
            os.makedirs(DOWNLOAD_DIR)
            
        clean_title = re.sub(r'[<>:"/\\|?*]', '', title).strip()
        output_template = os.path.join(DOWNLOAD_DIR, f"{clean_title}.%(ext)s")
        
        # Check existence
        ext = "mp3" if format_type == "mp3" else "mp4"
        final_path = os.path.join(DOWNLOAD_DIR, f"{clean_title}.{ext}")
        if os.path.exists(final_path):
            console.print(f"[yellow]File already exists: {final_path}[/yellow]")
            time.sleep(1.5)
            return

        # Common Options
        ydl_opts = {
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': imageio_ffmpeg.get_ffmpeg_exe()
        }
        
        msg = f"Downloading {format_type.upper()}..."

        # MP3 Quality Selection
        if format_type == "mp3":
            qualities = [
                {"key": "1", "label": "320 kbps (High Quality)", "val": "320"},
                {"key": "2", "label": "256 kbps", "val": "256"},
                {"key": "3", "label": "192 kbps (Standard)", "val": "192"},
                {"key": "4", "label": "128 kbps", "val": "128"},
                {"key": "0", "label": "Cancel", "val": "0"}
            ]
            
            selected_kbps = "192"
            
            if self.gui_style == "arrow":
                opts = [{"key": q["key"], "desc": q["label"]} for q in qualities]
                sel, _ = self.render_interactive_menu("Select Audio Quality", opts, [("Option", "desc", 30, "left")], 0)
                if not sel: return
                choice = sel["key"]
            else:
                console.print("[bold cyan]Select Audio Quality:[/bold cyan]")
                for q in qualities:
                    console.print(f"[{q['key']}] {q['label']}")
                choice = Prompt.ask("Select", choices=[q["key"] for q in qualities], default="3")

            if choice == "0": return
            
            for q in qualities:
                if q["key"] == choice:
                    selected_kbps = q["val"]
                    break
            
            msg = f"Downloading MP3 ({selected_kbps} kbps)..."
            
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': selected_kbps,
                }],
            })
            
        else: # This is the MP4 logic
            # Video (MP4) - Fetch Formats First
            try:
                with console.status("[bold blue]Checking available qualities...[/bold blue]"):
                    with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                        info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                        
                formats = info.get('formats', [])
                available_heights = set()
                
                for f in formats:
                    # Filter for video streams with valid height
                    if f.get('vcodec') != 'none' and f.get('height'):
                        available_heights.add(f['height'])
                
                # Sort descending (Reset to list)
                sorted_heights = sorted(list(available_heights), reverse=True)
                
                if not sorted_heights:
                    console.print("[yellow]Could not detect video qualities. Defaulting to Best.[/yellow]")
                    sorted_heights = [] # Will trigger fallback

                # Build Menu
                qualities = []
                for i, h in enumerate(sorted_heights, 1):
                    qualities.append({"key": str(i), "label": f"{h}p", "height": h})
                
                # Add "Best" fallback if empty (unlikely) or as top option? 
                # User asked for SPECIFIC options only.
                
                selected_height = None
                choice = "0"
                
                if not qualities:
                     # Fallback to auto
                     choice = "1" 
                     qualities.append({"key": "1", "label": "Best Available", "height": None})
                
                if self.gui_style == "arrow":
                    opts = [{"key": q["key"], "desc": q["label"]} for q in qualities]
                     # Add Cancel
                    opts.append({"key": "0", "desc": "Cancel"})
                    
                    sel, _ = self.render_interactive_menu("Select Resolution", opts, [("Quality", "desc", 20, "left")], 0)
                    if not sel: return
                    choice = sel["key"]
                else:
                    console.print("[bold cyan]Available Resolutions:[/bold cyan]")
                    for q in qualities:
                        console.print(f"[{q['key']}] {q['label']}")
                    choice = Prompt.ask("Select", choices=[q["key"] for q in qualities] + ["0"], default="1")
                
                if choice == "0": return
                
                # Find height
                for q in qualities:
                    if q["key"] == choice:
                        selected_height = q["height"]
                        break
                
                if selected_height:
                    # Specific height
                    fmt = f'bestvideo[height={selected_height}][ext=mp4]+bestaudio[ext=m4a]/best[height={selected_height}][ext=mp4]/best[height={selected_height}]'
                    msg = f"Downloading Video ({selected_height}p)..."
                else:
                    # Fallback
                    fmt = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                    msg = "Downloading Video (Best)..."

                ydl_opts.update({
                    'format': fmt,
                    'merge_output_format': 'mp4',
                })

            except Exception as e:
                console.print(f"[red]Error fetching formats: {e}[/red]")
                # Fallback to generic best
                ydl_opts.update({
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    'merge_output_format': 'mp4',
                })
                msg = "Downloading Video (Best - Fallback)..."


        try:
            # Progress Hook Logic
            # We need to define it here to capture the 'progress' object scope or use a class attribute
            # But simpler: use a context manager and a local hook
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.fields[desc]}", justify="right"),
                BarColumn(bar_width=None),
                "[progress.percentage]{task.percentage:>3.1f}%",
                "•",
                DownloadColumn(),
                "•",
                TransferSpeedColumn(),
                "•",
                TimeRemainingColumn(),
                console=console
            ) as progress:
                
                task_id = progress.add_task("Starting...", total=None, desc=msg)
                
                def progress_hook(d):
                    if d['status'] == 'downloading':
                        try:
                            total = d.get('total_bytes') or d.get('total_bytes_estimate')
                            downloaded = d.get('downloaded_bytes', 0)
                            
                            progress.update(task_id, total=total, completed=downloaded, desc=msg)
                        except: pass
                        
                    elif d['status'] == 'finished':
                        progress.update(task_id, total=None, completed=None, desc="Processing...")

                ydl_opts['progress_hooks'] = [progress_hook]
                # Ensure quiet is True so we don't conflict, but we removed console.status wrapper
                ydl_opts['quiet'] = True
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
            
            console.print(f"[bold green]Download Complete ({format_type.upper()})![/bold green]")
            time.sleep(1.5)
        except Exception as e:
            console.print(f"[bold red]Download Error:[/bold red] {e}")
            time.sleep(3)


    def get_track_duration(self, path):
        """Get duration using mutagen (local) or mpv (remote)."""
        if not path:
            return 0
            
        # 1. Local File: Use Mutagen (Fast & Accurate)
        if os.path.exists(path):
            try:
                audio = MutagenFile(path)
                if audio and audio.info:
                    return audio.info.length
            except:
                pass
        
        # 2. Remote URL: Use MPV --identify (Fallback)
        if path.startswith("http"):
            try:
                # Capture both stdout and stderr
                cmd = ["mpv", "--identify", "--frames=0", "--no-audio", "--no-video", path]
                
                flags = 0
                if os.name == 'nt':
                     flags = subprocess.CREATE_NO_WINDOW
                
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                      text=True, encoding='utf-8', errors='replace', creationflags=flags)
                
                output = result.stdout
                
                # Check for ID_LENGTH=123.45
                match = re.search(r"ID_LENGTH=([\d\.]+)", output)
                if match:
                    return float(match.group(1))
                
                # Fallback: Check for "Duration: 00:03:45"
                match_dur = re.search(r"Duration:\s*(\d+):(\d+):(\d+)", output)
                if match_dur:
                    h, m, s = map(int, match_dur.groups())
                    return h * 3600 + m * 60 + s
                    
            except Exception as e:
                # console.print(f"[debug] Duration fetch error: {e}")
                pass
                
        return 0

    def send_ipc_command(self, ipc_path, command):
        """Send JSON command to MPV IPC socket and return result."""
        try:
            payload = json.dumps(command) + "\n"
            
            # Windows Named Pipe Handling
            if os.name == 'nt':
                # Open for read/write
                with open(ipc_path, "r+b", buffering=0) as f:
                    f.write(payload.encode("utf-8"))
                    f.flush()
                    
                    # Read response (simple blocking read for one line)
                    # MPV IPC sends one JSON object per line
                    response_line = f.readline().decode("utf-8").strip()
                    if response_line:
                        return json.loads(response_line)
            else:
                # Unix Domain Socket
                import socket
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                    sock.connect(ipc_path)
                    sock.sendall(payload.encode("utf-8"))
                    
                    # Read response
                    response_line = sock.recv(4096).decode("utf-8").strip()
                    if response_line:
                         # MPV might return multiple JSONs, we take the first line/object
                         return json.loads(response_line.split('\n')[0])
                
        except Exception:
            return None
        return None

    def kill_proc(self, proc):
        if not proc: return
        try:
            if os.name == 'nt':
                subprocess.run(f"taskkill /F /PID {proc.pid} /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                os.kill(proc.pid, signal.SIGKILL)
        except:
            pass
        if proc.poll() is None:
            try:
                proc.terminate()
            except: pass

    def generate_visualizer(self, width=50, is_paused=False, state=None):
        """
        Generates visualizer using Real FFT if available, else Physics Simulation.
        """
        import random
        import math
        
        levels = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
        
        # Real Visualization Logic
        if HAVE_REAL_VIZ and hasattr(self, 'audio_analyzer') and self.audio_analyzer:
             bars = self.audio_analyzer.get_levels(width // 2)
             # Apply pausing decay if needed
             if is_paused:
                 return " ".join(["▂"] * (width // 2)), None
             
             res = []
             for val in bars:
                idx = int(val * (len(levels) - 1))
                idx = max(0, min(idx, len(levels) - 1))
                res.append(levels[idx])
             return " ".join(res), None

        # Fallback: Physics Simulation (Cava-style)
        n_bars = width // 2
        if state is None:
            state = {"bars": [0.0] * n_bars, "energy": 0.0, "phase": 0.0}
            
        bars = state["bars"]
        energy = state["energy"]
        phase = state["phase"]
        
        if is_paused:
            energy = max(0.0, energy - 0.2)
            for i in range(len(bars)):
                bars[i] = max(0.0, bars[i] - 0.2)
        else:
            if random.random() < 0.08: energy += random.uniform(0.5, 0.9)
            energy = max(0.0, energy - 0.1)
            # Phase for swirling effect
            # Randomize phase speed slightly to break loops
            phase += 0.1 + (random.uniform(-0.05, 0.05))
            state["phase"] = phase

            # 2. Apply to Bars
            center = len(bars) // 2
            for i in range(len(bars)):
                # Base height from Energy
                target = energy
                
                # Frequency distribution logic
                # Low freq (left) follows energy closely
                # High freq (right) adds noise
                dist_from_left = i / len(bars)
                
                # Wave function (Perlin-ish fake)
                # Vary frequency slightly
                wave = math.sin(phase + i * 0.45) * 0.3
                
                # Noise factor
                noise = random.uniform(0.0, 0.3) if dist_from_left > 0.3 else 0.0
                
                # Calculate target height for this bar
                h = target * (1.0 - dist_from_left * 0.5) + wave * 0.2 + noise
                h = max(0.0, min(1.0, h))
                if h > bars[i]: bars[i] += (h - bars[i]) * 0.6 
                else: bars[i] -= 0.08
                bars[i] = max(0.0, min(1.0, bars[i]))
            
            smoothed = bars[:]
            for i in range(1, len(bars)-1):
                smoothed[i] = (bars[i-1] * 0.5 + bars[i] + bars[i+1] * 0.5) / 2
            for i in range(len(bars)):
                bars[i] = bars[i] * 0.3 + smoothed[i] * 0.7

        res = []
        for val in bars:
            idx = int(val * (len(levels) - 1))
            res.append(levels[idx])
        return " ".join(res), state



    def play_queue(self, queue, start_index=0, enable_autoplay=True):
        idx = start_index
        
        while idx < len(queue) or enable_autoplay:
            # Determine next video
            video = None
            if idx < len(queue):
                video = queue[idx]
                idx += 1
                is_queue_item = True
            elif enable_autoplay and self.current_video_id and self.history:
                 current_title = self.history[-1]["title"]
                 with console.status("[bold blue]Finding next song...[/bold blue]", spinner="earth"):
                     next_vid = self.get_related_video(self.current_video_id, current_title)
                     
                 if next_vid:
                     video = next_vid
                     is_queue_item = False
                 else:
                     console.print("[red]Could not find related video.[/red]")
                     break
            else:
                 break

            video_id = video.get("id") 
            title = video["title"]
            local_path = self.get_downloaded_path(title)
            
            # Explicit local path provided in queue item (legacy 'path' or 'url' if no ID)
            if not video_id:
                if "path" in video and os.path.exists(video["path"]):
                    local_path = video["path"]
                elif "url" in video and os.path.exists(video["url"]):
                    local_path = video["url"]

            self.current_video_id = video_id
            if video_id: 
                self.add_to_history(video_id, title)
            
            # console.clear() # Removed to keep flow smooth, Live(screen=True) handles it
            
            source_msg = "[bold cyan]Playing from Local File 📂[/bold cyan]" if local_path else "[bold red]Streaming from YouTube 📡[/bold red]"
            # Removed static print to prevent ghosting on main buffer. UI is handled by Live loop.
            
            if local_path:
                url = local_path
            else:
                url = f"https://www.youtube.com/watch?v={video_id}"
                
            proc = None
            self.audio_analyzer = None # Avoid AttributeError in finally
            
            # Init Real Visualizer
            if HAVE_REAL_VIZ:
                 try:
                    self.audio_analyzer = AudioAnalyzer()
                 except: 
                    self.audio_analyzer = None
            
            is_paused = False # Track pause state
            
            # Generate unique pipe name
            pipe_id = uuid.uuid4().hex
            if os.name == 'nt':
                ipc_path = fr'\\.\pipe\yt_cli_mpv_{pipe_id}'
            else:
                ipc_path = f'/tmp/yt_cli_mpv_{pipe_id}'
            
            # Flush existing keys before starting song interaction
            InputHandler.flush()
            
            song_start_time = time.time()
            cooldown_seconds = 5 if os.name == 'nt' else 2.5
            last_key_time = 0
            
            try:
                # Start MPV with IPC server enabled
                # Remove stdout/stderr suppression to show MPV output (duration, codec, etc.)
                # Added options to prevent "audio device underrun"
                cmd = [
                    "mpv", 
                    "--no-video", 
                    f"--volume={self.volume}", 
                    f"--input-ipc-server={ipc_path}",
                    "--cache=yes",                  # Force cache
                    "--demuxer-max-bytes=128MiB",   # 128MB buffer
                    "--demuxer-readahead-secs=20",  # Read ahead 20s
                    "--audio-buffer=1",             # 1s audio buffer (prevents underruns)
                    url
                ]
                
                # Use PIPE for stdin to allow sending commands (like 'p' for pause) in interactive mode
                input_mode = subprocess.PIPE if self.gui_style == "arrow" else subprocess.DEVNULL
                proc = subprocess.Popen(cmd, stdin=input_mode, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Control Loop
                # Initialize interactive vars
                btn_idx = 2 # Default to Pause (Prev, Stop, Pause, Next) -> [Prev, Stop, Pause, Next]
                
                total_seconds = 0
                if "duration" in video and video["duration"]:
                     try:
                        if isinstance(video["duration"], (int, float)):
                                total_seconds = float(video["duration"])
                        else:
                                total_seconds = isodate.parse_duration(video["duration"]).total_seconds()
                     except: pass

                # Main Control Loop
                progress_bar = Progress(
                    TextColumn("[bold blue]{task.fields[title]}", justify="left"),
                    BarColumn(bar_width=None),
                    "[progress.percentage]{task.percentage:>3.0f}%",
                    TextColumn("{task.fields[current_time]}", justify="right"), # Manual Time
                    "/",
                    TextColumn("{task.fields[total_time]}")
                )
                
                task_id = progress_bar.add_task("play", total=total_seconds or 100, title=title, current_time="00:00", total_time="??:??")
                
                from rich.console import Group
                
                # CRITICAL FIX: Initialize elapsed OUTSIDE the loop to prevent resetting
                elapsed = 0
                last_duration_check = 0
                
                # Safety: Clear Main Buffer ensures no "Ghost text" remains when we switch back from Alt Buffer
                console.clear()
                
                # Use screen=True (Alt Buffer) to prevent "Now Playing" from persisting in history (Ghosting)
                with Live(Panel(progress_bar), refresh_per_second=4, console=console, screen=True, transient=True) as live:
                    while proc.poll() is None:
                        # 0. Check Playback State
                        # Dynamic Duration Check (IPC) - Only if missing
                        if total_seconds == 0 and time.time() - last_duration_check > 0.5:
                             last_duration_check = time.time()
                             res = self.send_ipc_command(ipc_path, {"command": ["get_property", "duration"]})
                             if res and res.get("data"):
                                 try:
                                     ts = float(res["data"])
                                     if ts > 0:
                                         total_seconds = ts
                                         progress_bar.update(task_id, total=total_seconds, total_time=str(datetime.timedelta(seconds=int(total_seconds))))
                                 except: pass

                        # 1. Sync Time (Accurate IPC)
                        is_buffering = False
                        
                        # Check buffering status
                        buf_res = self.send_ipc_command(ipc_path, {"command": ["get_property", "paused-for-cache"]})
                        if buf_res and buf_res.get("data") is True:
                            is_buffering = True # Timer will hold steady
                            
                        # Get Time Position from MPV
                        if not is_buffering:
                            pos_res = self.send_ipc_command(ipc_path, {"command": ["get_property", "time-pos"]})
                            if pos_res and pos_res.get("data"):
                                try:
                                    val = float(pos_res["data"])
                                    if val >= 0:
                                        elapsed = val # Update simple atomic value
                                except: pass
                        
                        # Update Progress
                        # Format current time
                        curr_time_str = str(datetime.timedelta(seconds=int(elapsed)))
                        
                        if total_seconds > 0:
                            progress_bar.update(task_id, completed=elapsed, current_time=curr_time_str)
                        else:
                            progress_bar.update(task_id, completed=elapsed, total=None, current_time=curr_time_str) 
                        
                        # Generate UI Content
                        if self.gui_style == "arrow":
                            btns = [
                                {"label": "⏮  Prev", "key": "prev"},
                                {"label": "⏹  Stop", "key": "s"},
                                {"label": "▶  Play" if is_paused else "⏸  Pause", "key": "p"},
                                {"label": "⏭  Next", "key": "n"}
                            ]
                            controls_text = Text()
                            for i, btn in enumerate(btns):
                                style = "reverse green" if i == btn_idx else "dim white"
                                controls_text.append(f" {btn['label']} ", style=style)
                                controls_text.append("  ")
                            controls_render = Align.center(controls_text)
                        
                        else:
                             status_icon = "⏸" if is_paused else "▶"
                             controls_render = Align.center(Text(f"Status: {status_icon}   [Left]Prev   [P]ause   [S]top   [N]ext", style="dim white"))

                        # Generate Visualizer
                        # Gate: Only animate if audio is playing (> 0.5s) AND not paused
                        should_animate = (elapsed > 0.5) and (not is_paused) and (not is_buffering)
                        
                        # vis_state persists in the outer loop scope (needs init)
                        if 'vis_state' not in locals(): vis_state = None
                        
                        vis_str, vis_state = self.generate_visualizer(width=50, is_paused=not should_animate, state=vis_state)
                        
                        # Mode Indicator
                        mode_mark = "[dim][R][/dim]" if (HAVE_REAL_VIZ and self.audio_analyzer) else "[dim][S][/dim]"
                        
                        visualizer_render = Text.from_markup(f"{vis_str} {mode_mark}", style="bold #d79fed", justify="center")

                        panel_content = Group(
                            Text(f"Now Playing: {title}", style="bold gold1", justify="center"),
                            Text.from_markup(source_msg, justify="center"),
                            Text("\n"),
                            progress_bar,
                            Text("\n"),
                            visualizer_render, # Add Visualizer here
                            Text("\n"),
                            controls_render
                        )
                        live.update(Panel(panel_content, border_style="green"))
                        
                        # Handle Input
                        if InputHandler.kbhit():
                            key = InputHandler.getch()
                            if not key: continue
                            
                            elapsed_check = time.time() - last_key_time
                            if elapsed_check < 0.2: 
                                continue
                            last_key_time = time.time()

                            # Interactive commands
                            if key == 'ESC' or key == 'q':
                                self.kill_proc(proc)
                                return
                            
                            if self.gui_style == "arrow":
                                if key == 'LEFT': btn_idx = (btn_idx - 1) % 4
                                elif key == 'RIGHT': btn_idx = (btn_idx + 1) % 4
                                elif key == 'ENTER':
                                    action = btns[btn_idx]["key"]
                                    if action == 'b': 
                                         self.kill_proc(proc)
                                         return
                                    elif action == 'prev':
                                         idx = max(0, idx - 2)
                                         self.kill_proc(proc)
                                         break
                                    elif action == 's':
                                        self.kill_proc(proc)
                                        return
                                    elif action == 'p':
                                        self.send_ipc_command(ipc_path, {"command": ["cycle", "pause"]})
                                        is_paused = not is_paused
                                    elif action == 'n':
                                        self.kill_proc(proc)
                                        break 
                            else:
                                if key == 'p' or key == 'SPACE':
                                    self.send_ipc_command(ipc_path, {"command": ["cycle", "pause"]})
                                    is_paused = not is_paused
                                elif key == 'n':
                                    self.kill_proc(proc)
                                    break
                                elif key == 'LEFT' or key == 'r':
                                    idx = max(0, idx - 2)
                                    self.kill_proc(proc)
                                    break
                                elif key == 'b' or key == 's':
                                    self.kill_proc(proc)
                                    return
                        
                        time.sleep(0.05)
            except KeyboardInterrupt:
                # Handle Ctrl+C gracefully
                return
            except Exception as e:
                console.print(f"[red]Playback Error: {e}[/red]")
                time.sleep(2)
            finally:
                self.kill_proc(proc)
                if self.audio_analyzer:
                     self.audio_analyzer.close()
                     self.audio_analyzer = None
            
            # Wait a tiny bit between songs
            time.sleep(0.5)

        Prompt.ask("Playback finished. Press Enter to return...")

    def play_video(self, video_id, title):
        self.play_queue([{"id": video_id, "title": title}], start_index=0, enable_autoplay=self.autoplay)

    def get_related_video(self, video_id, current_title=None):
        """
        Finds a related video to play next.
        Since 'relatedToVideoId' is deprecated, we search for the current title to find similar songs.
        """
        if not current_title:
             console.print("[yellow]No title info for autoplay, skipping...[/yellow]")
             return None

        console.print("[yellow]Finding recommendations...[/yellow]")
        try:
            # Search for similar content
            # Adding "mix" or "radio" or "official audio" can help find relevant music
            request = self.youtube.search().list(
                part="snippet",
                q=f"{current_title} official audio", 
                type="video",
                maxResults=10
            )
            response = request.execute()
            items = response.get("items", [])
            
            # Avoid loops
            recent_ids = [h['id'] for h in self.history[-20:]] # Check last 20 songs

            for item in items:
                 vid_id = item["id"]["videoId"]
                 # Skip if effectively the same video or recently played
                 if vid_id != video_id and vid_id not in recent_ids:
                     return {
                         "id": vid_id,
                         "title": item["snippet"]["title"]
                     }
            
            # If all 10 are in history, just pick the first different one to keep playing something
            if items:
                 first = items[0]
                 if first["id"]["videoId"] != video_id:
                      return {"id": first["id"]["videoId"], "title": first["snippet"]["title"]}

        except Exception as e:
            console.print(f"[red]Autoplay Search Error: {e}[/red]")
            
        return None

    def play_previous(self):
        page = 0
        current_idx = 0
        page_size = 20
        
        while True:
            if not self.history:
                console.print("[yellow]No history available.[/yellow]")
                time.sleep(2)
                return

            rev_history = list(reversed(self.history))
            total_items = len(rev_history)
            max_page = (total_items - 1) // page_size
            
            # Clamp page
            if page < 0: page = 0
            if page > max_page: page = max_page
            
            start = page * page_size
            end = start + page_size
            display_items = rev_history[start:end]
            
            # Fetch durations (with loading indicator)
            ids = [item["id"] for item in display_items]
            details = {}
            with console.status("[bold blue]Loading history details...[/bold blue]"):
                details = self.get_video_details(ids)

            if self.gui_style == "arrow":
                options = []
                # Add content items
                for idx, item in enumerate(display_items, start + 1):
                    vid_id = item["id"]
                    title_full = item["title"]
                    title = self.sanitize_text(title_full)
                    duration = details.get(vid_id, {}).get("duration", "N/A")
                    saved_mark = "Yes" if self.is_saved(vid_id) else ""
                    
                    dl_status = self.get_download_status(title_full)
                    mp3_mark = "[green]Yes[/green]" if dl_status["mp3"] else "[red]No[/red]"
                    mp4_mark = "[green]Yes[/green]" if dl_status["mp4"] else "[red]No[/red]"
                    
                    options.append({
                        "key": str(idx),
                        "no": str(idx),
                        "title": title,
                        "dur": duration,
                        "saved": saved_mark,
                        "mp3": mp3_mark,
                        "mp4": mp4_mark,
                        "raw_item": item,
                        "type": "content"
                    })
                
                # Add Navigation Items
                if page < max_page:
                    options.append({"key": "n", "no": ">>", "title": "[bold cyan]Next Page[/bold cyan]", "type": "nav", "dur": "", "saved": "", "mp3": "", "mp4": ""})
                if page > 0:
                    options.append({"key": "p", "no": "<<", "title": "[bold cyan]Prev Page[/bold cyan]", "type": "nav", "dur": "", "saved": "", "mp3": "", "mp4": ""})
                
                options.append({"key": "0", "no": "←", "title": "[ Back ]", "type": "nav", "dur": "", "saved": "", "mp3": "", "mp4": ""})

                cols = [
                    ("No.", "no", 4, "right"),
                    ("Title", "title", 100, "left"),
                    ("Duration", "dur", 8, "center"),
                    ("Saved", "saved", 6, "center"),
                    ("Mp3", "mp3", 6, "center"),
                    ("Mp4", "mp4", 6, "center")
                ]
                
                title_text = f"History (Page {page + 1}/{max_page + 1})"
                
                # We need to default selection to top of list when changing pages?
                # Or keep index? generic function keeps index. 
                # Let's just pass 0 for now.
                if current_idx >= len(options): current_idx = len(options) - 1
                selected_item, current_idx = self.render_interactive_menu(title_text, options, cols, current_idx)
                if not selected_item: return
                
                choice = selected_item["key"]
                
                if choice == "n":
                    page += 1
                elif choice == "p":
                    page -= 1
                elif choice == "0":
                    return
                elif selected_item.get("type") == "content":
                    selected = selected_item["raw_item"]
                    self.show_action_menu(selected)
                
            else:
                console.clear()
                
                table = Table(title=f"Play History (Page {page + 1}/{max_page + 1})", box=box.ROUNDED)
                table.add_column("No.", style="cyan", no_wrap=True, width=4)
                table.add_column("Title", style="white", width=100, overflow="ellipsis", no_wrap=True)
                table.add_column("Duration", style="yellow", width=8, no_wrap=True)
                table.add_column("Saved", style="green", width=6, justify="center")
                table.add_column("Mp3", justify="center", width=8)
                table.add_column("Mp4", justify="center", width=8)
                
                for idx, item in enumerate(display_items, start + 1): 
                    vid_id = item["id"]
                    title_full = item["title"]
                    title = self.sanitize_text(title_full)
                    duration = details.get(vid_id, {}).get("duration", "N/A")
                    saved_mark = "Yes" if self.is_saved(vid_id) else ""
                    
                    dl_status = self.get_download_status(title_full)
                    mp3_mark = "[green]Yes[/green]" if dl_status["mp3"] else "[red]No[/red]"
                    mp4_mark = "[green]Yes[/green]" if dl_status["mp4"] else "[red]No[/red]"
                    
                    table.add_row(str(idx), title, duration, saved_mark, mp3_mark, mp4_mark)
                    
                console.print(table)
                console.print("[dim]Enter number to select, 'n' For Next, 'p' for Prev, 'c' to Back[/dim]")
                
                # Allow n/p always to handle custom error messages
                valid_choices = [str(i) for i in range(start + 1, end + 1)] + ["c", "n", "p"]
                
                choice = Prompt.ask("Select option", choices=valid_choices)
                
                if choice == "c":
                    return
                elif choice == "n":
                    if page < max_page:
                        page += 1
                    else:
                        console.print("[yellow]You have reached the end of the history list.[/yellow]")
                        time.sleep(1.5)
                elif choice == "p":
                    if page > 0:
                        page -= 1
                    else:
                         console.print("[yellow]You are already on the first page.[/yellow]")
                         time.sleep(1.5)
                else:
                    idx = int(choice)
                    # Find item in ORIGINAL full list OR use display_items
                    # index in display_items = idx - start - 1
                    local_idx = idx - start - 1
                    if 0 <= local_idx < len(display_items):
                        selected = display_items[local_idx]
                        self.show_action_menu(selected)
                    else:
                         # Should be covered by valid_choices, but safety net
                         console.print("[red]Invalid selection.[/red]")
                         time.sleep(1)

if __name__ == "__main__":
    app = YouTubeCLI(console)
    app.main_menu()
