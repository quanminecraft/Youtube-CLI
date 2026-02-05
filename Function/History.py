from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.prompt import Prompt
import time

def history_ui(app):
    current_idx = 0
    page = 0
    while True:
        if not app.history:
            app.console.print(Panel("[yellow]No play history yet.[/yellow]", title="Play History", border_style="yellow"))
            time.sleep(1.5)
            return
        
        rev_history = app.history[::-1]
        
        if app.gui_style == "arrow":
            # Fetch durations for displayed items
            ids = [item["id"] for item in rev_history]
            details = {}
            with app.console.status("[bold blue]Loading history details...[/bold blue]"):
                details = app.get_video_details(ids)

            options = []
            options.append({"key": "0", "no": "←", "title": "[ Back ]", "dur": "", "mp3": "", "mp4": ""})
            
            for idx, item in enumerate(rev_history, 1):
                vid_id = item['id']
                dl_status = app.get_download_status(item['title'])
                mp3_mark = "[green]Yes[/green]" if dl_status["mp3"] else "[red]No[/red]"
                mp4_mark = "[green]Yes[/green]" if dl_status["mp4"] else "[red]No[/red]"
                
                # Get duration from details or 'N/A'
                duration = details.get(vid_id, {}).get("duration", "N/A")

                options.append({
                    "key": str(idx),
                    "no": str(idx),
                    "title": item['title'],
                    "dur": duration,
                    "mp3": mp3_mark,
                    "mp4": mp4_mark,
                    "raw": item
                })

            cols = [
                ("Title", "title", 60, "left"),
                ("Duration", "dur", 8, "center"),
                ("Mp3", "mp3", 8, "center"),
                ("Mp4", "mp4", 8, "center")
            ]
            
            if current_idx >= len(options): current_idx = len(options) - 1
            selected, current_idx = app.render_interactive_menu("Play History 📜", options, cols, current_idx)
            
            if not selected: return
            choice = selected["key"]
            
            if choice == "0": return
            
            if "raw" in selected:
                app.show_action_menu(selected["raw"])

        else:
            MAX_PAGE = (len(rev_history) - 1) // 20
            if page > MAX_PAGE: page = MAX_PAGE
            if page < 0: page = 0
            
            start = page * 20
            end = start + 20
            view_items = rev_history[start:end]

            table = Table(title=f"Play History (Page {page + 1}/{MAX_PAGE + 1})", box=box.ROUNDED)
            table.add_column("No.", style="cyan", width=4)
            table.add_column("Title", style="white", width=60)
            table.add_column("Mp3", justify="center", width=8)
            table.add_column("Mp4", justify="center", width=8)

            item_map = {}
            for idx, item in enumerate(view_items, start + 1):
                dl_status = app.get_download_status(item['title'])
                mp3_mark = "[green]Yes[/green]" if dl_status["mp3"] else "[red]No[/red]"
                mp4_mark = "[green]Yes[/green]" if dl_status["mp4"] else "[red]No[/red]"
                
                table.add_row(str(idx), item['title'], mp3_mark, mp4_mark)
                item_map[str(idx)] = item
            
            app.console.print(table)
            
            choices = list(item_map.keys()) + ["0"]
            nav_msg = ""
            if len(rev_history) > end:
                choices.append("n")
                nav_msg += ", 'n' Next"
            if page > 0:
                 choices.append("p")
                 nav_msg += ", 'p' Prev"
            
            choice = Prompt.ask(f"[dim]Select number{nav_msg} or 0 to back[/dim]", choices=choices, default="0")
            
            if choice == "0": return
            elif choice == "n":
                page += 1
                continue
            elif choice == "p":
                page -= 1
                continue
            elif choice in item_map:
                app.show_action_menu(item_map[choice])
