import subprocess
import os
import time
from rich.console import Console
from rich.panel import Panel

def play_video(url, title, console: Console):
    """
    Launches MPV in video mode (windowed).
    This function blocks until the MPV window is closed.
    """
    source_msg = "[bold red]Streaming from YouTube 📡[/bold red]"
    if os.path.exists(url):
        source_msg = "[bold cyan]Playing from Local File 📂[/bold cyan]"

    console.print(Panel(f"[bold cyan]Launching Video Player...[/bold cyan]\n"
                        f"[yellow]{title}[/yellow]\n"
                        f"{source_msg}", border_style="blue"))
    
    cmd = [
        "mpv",
        url,
        "--force-window",  # Ensure window opens even for audio-only inputs (though we expect video)
        "--title=YouTube CLI - " + title,
        "--osc",           # On Screen Controller
        "--no-terminal"    # Verify if we want terminal output. Usually clean is better.
    ]
    
    try:
        # We run blocking, because CLI interaction isn't needed while watching video
        # (Status controls are in the MPV window itself)
        process = subprocess.Popen(cmd)
        process.wait() 
        
    except FileNotFoundError:
        console.print("[bold red]Error:[/bold red] 'mpv' executable not found. Please install MPV and add to PATH.")
        time.sleep(2)
    except KeyboardInterrupt:
        # Allow Ctrl+C to kill the player if needed
        if process:
             process.terminate()
        console.print("[dim]Video stopped.[/dim]")
    except Exception as e:
         console.print(f"[bold red]Video Player Error:[/bold red] {e}")
         time.sleep(2)
