from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.prompt import Prompt
import time

def saved_songs_ui(app):
    current_idx = 0
    while True:
        if not app.saved_songs:
            app.console.print(Panel("[yellow]No saved songs yet.[/yellow]", title="Saved Songs", border_style="yellow"))
            time.sleep(1.5)
            return

        if app.gui_style == "arrow":
            # Fetch durations for saved items
            ids = [song["id"] for song in app.saved_songs if "id" in song]
            details = {}
            if ids:
                 with app.console.status("[bold blue]Loading saved details...[/bold blue]"):
                     details = app.get_video_details(ids)

            options = []
            options.append({"key": "0", "no": "←", "title": "[ Back ]", "dur": "", "mp3": "", "mp4": ""})
            
            for idx, song in enumerate(app.saved_songs, 1):
                vid_id = song.get('id')
                dl_status = app.get_download_status(song['title'])
                mp3_mark = "[green]Yes[/green]" if dl_status["mp3"] else "[red]No[/red]"
                mp4_mark = "[green]Yes[/green]" if dl_status["mp4"] else "[red]No[/red]"
                
                duration = details.get(vid_id, {}).get("duration", "N/A")

                options.append({
                    "key": str(idx),
                    "no": str(idx),
                    "title": song['title'],
                    "dur": duration,
                    "mp3": mp3_mark,
                    "mp4": mp4_mark,
                    "raw": song
                })

            cols = [
                ("Title", "title", 60, "left"),
                ("Duration", "dur", 8, "center"),
                ("Mp3", "mp3", 8, "center"),
                ("Mp4", "mp4", 8, "center")
            ]
            
            if current_idx >= len(options): current_idx = len(options) - 1
            selected, current_idx = app.render_interactive_menu("Saved Songs 💾", options, cols, current_idx)
            
            if not selected: return
            choice = selected["key"]
            
            if choice == "0": return
            
            if "raw" in selected:
                # Pass full playlist context
                try:
                    p_idx = int(choice) - 1
                except:
                    p_idx = 0
                app.show_action_menu(selected["raw"], playlist=app.saved_songs, playlist_index=p_idx)

        else:
            table = Table(title="Saved Songs", box=box.ROUNDED)
            table.add_column("No.", style="cyan", width=4)
            table.add_column("Title", style="white", width=60)
            table.add_column("Mp3", justify="center", width=8)
            table.add_column("Mp4", justify="center", width=8)

            item_map = {}
            for idx, song in enumerate(app.saved_songs, 1):
                dl_status = app.get_download_status(song['title'])
                mp3_mark = "[green]Yes[/green]" if dl_status["mp3"] else "[red]No[/red]"
                mp4_mark = "[green]Yes[/green]" if dl_status["mp4"] else "[red]No[/red]"
                
                duration = details.get(song.get('id'), {}).get("duration", "N/A")
                
                table.add_row(str(idx), song['title'], duration, mp3_mark, mp4_mark)
                item_map[str(idx)] = song
            
            app.console.print(table)
            choice = Prompt.ask("[dim]Select song number or 0 to back[/dim]", default="0")
            
            if choice == "0": return
            if choice in item_map:
                try:
                    p_idx = int(choice) - 1
                except:
                    p_idx = 0
                app.show_action_menu(item_map[choice], playlist=app.saved_songs, playlist_index=p_idx)
