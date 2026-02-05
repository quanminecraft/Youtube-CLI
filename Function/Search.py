from rich.prompt import Prompt
from rich.table import Table
from rich import box
import time

def search_ui(app):
    query = Prompt.ask("Enter search query")
    if not query:
        return
    
    next_page_token = None
    
    while True:
        try:
            items = []
            new_token = None
            
            with app.console.status(f"[bold green]Searching for '{query}'...[/bold green]", spinner="dots"):
                request = app.youtube.search().list(
                    part="snippet",
                    maxResults=20,
                    q=query,
                    type="video",
                    pageToken=next_page_token
                )
                response = request.execute()
                items = response.get("items", [])
                new_token = response.get("nextPageToken")
            
            if not items:
                app.console.print("[red]No results found.[/red]")
                time.sleep(2)
                return

            # Collect video IDs
            video_ids = [item["id"]["videoId"] for item in items if "videoId" in item["id"]]
            
            # Fetch details (duration)
            details_map = app.get_video_details(video_ids)
            
            # Table Interaction Loop
            current_idx = 0
            while True:
                app.console.clear()
                
                if app.gui_style == "arrow":
                    menu_options = []
                    idx_counter = 1
                    seen_ids = set()
                    seen_titles = set()
                    
                    for item in items:
                        if "videoId" not in item["id"]: continue
                        vid_id = item["id"]["videoId"]
                        
                        snippet = item["snippet"]
                        info = details_map.get(vid_id, {})
                        title_full = info.get("title", snippet["title"])
                        # Sanitize immediately for comparison
                        title = app.sanitize_text(title_full) 
                        
                        # Strict Deduplication: Check ID and Title
                        if vid_id in seen_ids: continue
                        if title in seen_titles: continue
                        
                        seen_ids.add(vid_id)
                        seen_titles.add(title)
                        
                        duration = info.get("duration", "N/A")
                        title = app.sanitize_text(title_full)
                        duration = info.get("duration", "N/A")
                        
                        # Channel name
                        channel_full = snippet["channelTitle"]
                        channel = app.sanitize_text(channel_full)
                        
                        saved_mark = "Yes" if app.is_saved(vid_id) else ""
                        dl_status = app.get_download_status(title_full)
                        mp3_mark = "[green]Yes[/green]" if dl_status["mp3"] else "[red]No[/red]"
                        mp4_mark = "[green]Yes[/green]" if dl_status["mp4"] else "[red]No[/red]"
                        
                        menu_options.append({
                            "key": str(idx_counter),
                            "no": str(idx_counter),
                            "title": title,
                            "dur": duration,
                            "chan": channel,
                            "saved": saved_mark,
                            "mp3": mp3_mark,
                            "mp4": mp4_mark,
                            "raw_item": {"id": vid_id, "title": title_full} 
                        })
                        idx_counter += 1
                    
                    # Navigation
                    if new_token:
                        menu_options.append({"key": "n", "no": ">>", "title": "[bold cyan]Next Page[/bold cyan]", "dur": "", "chan": "", "saved": "", "mp3": "", "mp4": ""})
                    
                    menu_options.append({"key": "0", "no": "←", "title": "[ Back ]", "dur": "", "chan": "", "saved": "", "mp3": "", "mp4": ""})
                    
                    cols = [
                        ("Title", "title", 60, "left"),
                        ("Duration", "dur", 8, "center"),
                        ("Channel", "chan", 20, "left"),
                        ("Saved", "saved", 6, "center"),
                        ("Mp3", "mp3", 6, "center"),
                        ("Mp4", "mp4", 6, "center")
                    ]
                    
                    if current_idx >= len(menu_options): current_idx = len(menu_options) - 1
                    selected_item, current_idx = app.render_interactive_menu(f"Results for '{query}'", menu_options, cols, current_idx)
                    
                    if not selected_item: return
                    choice = selected_item["key"]
                    
                    if choice == "0": return
                    if choice == "n":
                        if new_token:
                            next_page_token = new_token
                            break 
                        else: continue

                    if "raw_item" in selected_item:
                         selected_song = selected_item["raw_item"]
                         app.show_action_menu(selected_song)
                
                else:
                    # Classic
                    table = Table(title=f"Results for '{query}'", box=box.ROUNDED)
                    table.add_column("No.", style="cyan", no_wrap=True, width=4)
                    table.add_column("Title", style="white", width=90, overflow="ellipsis", no_wrap=True)
                    table.add_column("Duration", style="yellow", width=8, no_wrap=True)
                    table.add_column("Channel", style="magenta", width=25, overflow="ellipsis", no_wrap=True)
                    # ... (rest of columns) ...
                    # Simplified for brevity in tool call, will rely on full implementation logic if I copy fully?
                    # Ensure I copy correctly.
                    table.add_column("Saved", style="green", width=6, justify="center")
                    table.add_column("Mp3", justify="center", width=8)
                    table.add_column("Mp4", justify="center", width=8)
                    
                    video_map = {}
                    idx_counter = 1
                    for item in items:
                        if "videoId" not in item["id"]: continue
                        vid_id = item["id"]["videoId"]
                        snippet = item["snippet"]
                        info = details_map.get(vid_id, {})
                        title_full = info.get("title", snippet["title"])
                        title = app.sanitize_text(title_full)
                        duration = info.get("duration", "N/A")
                        channel = app.sanitize_text(snippet["channelTitle"])
                        saved_mark = "Yes" if app.is_saved(vid_id) else ""
                        dl_status = app.get_download_status(title_full)
                        mp3_mark = "[green]Yes[/green]" if dl_status["mp3"] else "[red]No[/red]"
                        mp4_mark = "[green]Yes[/green]" if dl_status["mp4"] else "[red]No[/red]"
                        
                        table.add_row(str(idx_counter), title, duration, channel, saved_mark, mp3_mark, mp4_mark)
                        video_map[str(idx_counter)] = {"id": vid_id, "title": title_full}
                        idx_counter += 1
                    
                    app.console.print(table)
                    options = list(video_map.keys()) + ["c"]
                    prompt_text = "[dim]Enter number, 'c' back[/dim]"
                    if new_token:
                        options.append("n")
                        prompt_text = "[dim]Enter number, 'n' next page, 'c' back[/dim]"
                    
                    app.console.print(prompt_text)
                    choice = Prompt.ask("Select", choices=options)
                    
                    if choice == "c": return
                    if choice == "n" and new_token:
                        next_page_token = new_token
                        break
                    
                    if choice in video_map:
                        app.show_action_menu(video_map[choice])
        
        except Exception as e:
            app.console.print(f"[red]Search failed: {e}[/red]")
            Prompt.ask("Enter to continue...")
            return
