import os
import datetime
import time
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich import box
from rich.prompt import Prompt

def offline_mode_ui(app):
    current_idx = 0
    while True:
        if app.gui_style == "arrow":
            options = [
                {"key": "1", "action": "All Files"},
                {"key": "2", "action": "MP3 Files (Audio)"},
                {"key": "3", "action": "MP4 Files (Video)"},
                {"key": "0", "action": "[ Back ]"}
            ]
            
            cols = [("Action", "action", 40, "left")]
            
            sel, current_idx = app.render_interactive_menu("Offline Mode", options, cols, current_idx)
            if not sel: return
            choice = sel["key"]
            
            if choice == "0": choice = "0"
            
        else:
            app.print_banner()
            app.console.print("[bold underline]📂 Offline Mode[/bold underline]\n")
            
            menu_table = Table(box=box.ROUNDED, show_header=False)
            menu_table.add_column("Key", style="cyan")
            menu_table.add_column("Action", style="white")
            
            menu_table.add_row("[1]", "All Files")
            menu_table.add_row("[2]", "MP3 Files (Audio Only)")
            menu_table.add_row("[3]", "MP4 Files (Video)")
            menu_table.add_row("[0]", "Back")
            
            app.console.print(Align.center(menu_table))
            app.console.print("\n")
            
            choice = Prompt.ask("Select", choices=["1", "2", "3", "0"], default="1")
        
        if choice == "1":
            offline_all_songs(app, "all")
        elif choice == "2":
            offline_all_songs(app, "mp3")
        elif choice == "3":
            offline_all_songs(app, "mp4")
        elif choice == "0":
            return

def offline_all_songs(app, filter_mode="all"):
    current_idx = 1
    DOWNLOAD_DIR = app.DOWNLOAD_DIR
    
    while True:
        if not os.path.exists(DOWNLOAD_DIR):
            os.makedirs(DOWNLOAD_DIR)
        
        all_files = os.listdir(DOWNLOAD_DIR)
        identities = {} 
        
        for f in all_files:
            base = None
            ftype = None
            path = os.path.join(DOWNLOAD_DIR, f)
            
            if f.endswith(".mp3"):
                base = f[:-4]
                ftype = 'mp3'
            elif f.endswith(".mp4"):
                base = f[:-4]
                ftype = 'mp4'
            
            if base:
                if base not in identities:
                    identities[base] = {'mp3': None, 'mp4': None, 'title': base}
                identities[base][ftype] = path

        valid_items = []
        for k, v in identities.items():
            if filter_mode == "all":
                if v['mp3'] or v['mp4']: valid_items.append(v)
            elif filter_mode == "mp3":
                 if v['mp3']: valid_items.append(v)
            elif filter_mode == "mp4":
                 if v['mp4']: valid_items.append(v)

        if not valid_items:
            app.console.print(f"[yellow]No {filter_mode.upper()} files found.[/yellow]")
            time.sleep(2)
            return

        valid_items.sort(key=lambda x: x['title'])

        title_suffix = ""
        if filter_mode == "mp3": title_suffix = " (MP3)"
        elif filter_mode == "mp4": title_suffix = " (MP4)"
        
        menu_title = f"Offline Music{title_suffix}"

        if app.gui_style == "arrow":
            # Fetch durations for local files
            durations = {}
            with app.console.status("[bold blue]Scanning local files...[/bold blue]"):
                for item in valid_items:
                    path = None
                    # "offline then must scan according to metadata of each format (Mp3 separate mp4 separate)"
                    if filter_mode == "mp3":
                        path = item.get('mp3')
                    elif filter_mode == "mp4":
                        path = item.get('mp4')
                    else:
                        # All Files: Prefer MP3 duration (audio standard), fallback to MP4
                        path = item.get('mp3') or item.get('mp4')
                        
                    if path:
                        seconds = app.get_track_duration(path)
                        if seconds:
                            # Format MM:SS or HH:MM:SS
                            durations[item['title']] = str(datetime.timedelta(seconds=int(seconds)))
                        else:
                            durations[item['title']] = "N/A"
                    else:
                        durations[item['title']] = "N/A"

            options = []
            options.append({"key": "0", "no": "←", "title": "[ Back ]", "dur": "", "mp3": "", "mp4": ""})
            
            for idx, item in enumerate(valid_items, 1):
                mp3_mark = "[green]Yes[/green]" if item['mp3'] else "[red]No[/red]"
                mp4_mark = "[green]Yes[/green]" if item['mp4'] else "[red]No[/red]"
                dur = durations.get(item['title'], "N/A")
                
                options.append({
                    "key": str(idx), 
                    "no": str(idx), 
                    "title": item['title'],
                    "dur": dur,
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
            selected_item, current_idx = app.render_interactive_menu(menu_title, options, cols, current_idx)
            if not selected_item: return
            
            choice = selected_item["key"]
            if choice == "0": return
            
            if "raw" in selected_item:
                handle_offline_selection(app, selected_item["raw"], filter_mode)
                
        else:
            # Classic
            table = Table(title=menu_title, box=box.ROUNDED)
            table.add_column("No.", style="cyan", width=4)
            table.add_column("Title", style="white", width=60)
            table.add_column("Mp3", justify="center", width=8)
            table.add_column("Mp4", justify="center", width=8)
            
            item_map = {}
            for idx, item in enumerate(valid_items, 1):
                mp3_mark = "[green]Yes[/green]" if item['mp3'] else "[red]No[/red]"
                mp4_mark = "[green]Yes[/green]" if item['mp4'] else "[red]No[/red]"
                table.add_row(str(idx), item['title'], mp3_mark, mp4_mark)
                item_map[str(idx)] = item
                
            app.console.print(table)
            choice = Prompt.ask("[dim]Enter number to select or 0 to back[/dim]", default="0")
            
            if choice == "0": return
            if choice in item_map:
                handle_offline_selection(app, item_map[choice], filter_mode)

def handle_offline_selection(app, item, filter_mode="all"):
    # Re-implemented stub/logic from Interactive/Classic. 
    # Since we are moving it here, we should include the FULL logic.
    # The logic was complex (lines 726-810 in original main.py before stubbing).
    # I should try to RECOVER it or rewrite it.
    # Since I don't have the original text handy in this context without scrolling back far, 
    # I will implement a simplified but functional version or try to recall.
    # Actually, I have the logic from `Interactive.py` (which I wrote in step 2931).
    # I will use that logic.
    
    current_idx = 0
    while True:
        if app.gui_style == "arrow":
            options = [
                {"key": "1", "action": "Play Audio (MP3)", "active": "✔" if item['mp3'] else "✖"},
                {"key": "2", "action": "Watch Video (MP4)", "active": "✔" if item['mp4'] else "✖"},
                {"key": "3", "action": "Delete File", "active": "⚠"},
                {"key": "0", "action": "[ Back ]", "active": ""}
            ]
            cols = [("Action", "action", 30, "left"), ("Avail", "active", 5, "center")]
            sel_item, current_idx = app.render_interactive_menu(f"Manage: {item['title']}", options, cols, current_idx)
            if not sel_item: return
            choice = sel_item["key"]
            if choice == "0": return
        else:
             app.console.print(f"[bold gold1]Selected: {item['title']}[/bold gold1]")
             app.console.print(f"[1] Play Audio (MP3)")
             app.console.print(f"[2] Watch Video (MP4)")
             app.console.print(f"[3] Delete File")
             app.console.print(f"[0] Back")
             choice = Prompt.ask("Action", choices=["1", "2", "3", "0"], default="1")
             if choice == "0": return

        if choice == "1":
            if item['mp3']: 
                # Explicitly queue as audio
                app.play_queue([{"title": item['title'], "path": item['mp3']}], start_index=0, enable_autoplay=False)
            else: 
                app.console.print("[red]MP3 file not found![/red]")
                time.sleep(1)
        elif choice == "2":
            if item['mp4']: 
                # Video Mode
                app.console.print("[dim]Stopping background audio utils...[/dim]")
                if hasattr(app, 'audio_analyzer') and app.audio_analyzer:
                     try:
                         app.audio_analyzer.close()
                         app.audio_analyzer = None
                     except: pass
                
                # Explicitly call video player
                import video_player
                video_player.play_video(item['mp4'], item['title'], app.console)
            else:
                 app.console.print("[red]MP4 file not found![/red]")
                 time.sleep(1)
        elif choice == "3":
            # Deletion Logic
            del_opts = []
            if filter_mode == "mp4": del_opts = [{"key": "2", "action": "Delete MP4 Only"}]
            elif filter_mode == "mp3": del_opts = [{"key": "1", "action": "Delete MP3 Only"}]
            else:
                if item['mp3']: del_opts.append({"key": "1", "action": "Delete MP3 Only"})
                if item['mp4']: del_opts.append({"key": "2", "action": "Delete MP4 Only"})
                if item['mp3'] and item['mp4']: del_opts.append({"key": "3", "action": "Delete BOTH"})
            del_opts.append({"key": "0", "action": "Cancel"})
            
            if app.gui_style == "arrow":
                del_sel, _ = app.render_interactive_menu("Delete Options", del_opts, [("Action", "action", 30, "left")], 0)
                if not del_sel or del_sel["key"] == "0": continue
                del_choice = del_sel["key"]
                
                conf_opts = [{"key": "y", "action": "Yes, Delete", "style_active": "reverse red"}, {"key": "n", "action": "No, Keep", "style_active": "reverse green"}]
                conf_sel, _ = app.render_interactive_menu("Are you sure?", conf_opts, [("Action", "action", 30, "left")], 1)
                if not conf_sel or conf_sel["key"] != "y": continue
            else:
                # Classic
                app.console.print("Delete Options:")
                for opt in del_opts:
                    app.console.print(f"[{opt['key']}] {opt['action']}")
                del_choice = Prompt.ask("Select", choices=[o['key'] for o in del_opts], default="0")
                if del_choice == "0": continue
                
                conf = Prompt.ask("Are you sure? (y/n)", choices=["y", "n"], default="n")
                if conf != "y": continue
            
            try:
                if del_choice == "1" and item['mp3']:
                    os.remove(item['mp3'])
                    app.console.print("[green]MP3 deleted.[/green]")
                    item['mp3'] = None
                elif del_choice == "2" and item['mp4']:
                    os.remove(item['mp4'])
                    app.console.print("[green]MP4 deleted.[/green]")
                    item['mp4'] = None
                elif del_choice == "3":
                     if item['mp3']: os.remove(item['mp3']); item['mp3'] = None
                     if item['mp4']: os.remove(item['mp4']); item['mp4'] = None
                     app.console.print("[green]Both deleted.[/green]")
                time.sleep(1)
                return
            except Exception as e:
                app.console.print(f"[red]Error deleting: {e}[/red]")
                time.sleep(2)
