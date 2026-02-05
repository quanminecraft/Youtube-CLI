from rich.prompt import Prompt
import time

def play_link_ui(app):
    app.console.clear()
    app.print_banner()
    app.console.print("[bold underline]🌐 Play from link[/bold underline]\n")
    
    url = Prompt.ask("Enter YouTube URL (Cancel with 0 or empty)")
    if not url or url == "0":
        return
        
    vid_id = app.extract_video_id(url)
    if not vid_id:
        app.console.print("[red]Invalid YouTube URL. Could not extract Video ID.[/red]")
        time.sleep(2)
        return
        
    with app.console.status("[bold blue]Fetching details...[/bold blue]"):
        details = app.get_video_details([vid_id])
        
    if not details or vid_id not in details:
        app.console.print("[red]Video not found or unavailable.[/red]")
        time.sleep(2)
        return
        
    info = details[vid_id]
    
    video = {
        "id": vid_id,
        "title": info["title"],
        "duration": info["duration"]
    }
    
    app.show_action_menu(video)
