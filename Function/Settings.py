from rich.prompt import Prompt
from rich.table import Table
from rich.align import Align
from rich import box
import time
from Mode.Interactive import InteractiveMode # Import for type hinting if needed, but mostly dynamic

def settings_ui(app):
    while True:
        # Toggle Autoplay is now here
        autoplay_status = "ON" if app.autoplay else "OFF"
        
        if app.gui_style == "arrow":
            options = [
                {"key": "1", "label": "Update API Key", "val": f"{app.api_key[:10]}..."},
                {"key": "2", "label": "Set Volume", "val": f"{app.volume}%"},
                {"key": "3", "label": "GUI Style", "val": app.gui_style.upper()},
                {"key": "4", "label": "Autoplay", "val": autoplay_status, "desc": "Toggle Autoplay"},
                {"key": "0", "label": "[ Back ]", "val": ""}
            ]
            
            cols = [
                ("Option", "label", 30, "left"),
                ("Value", "val", 20, "center")
            ]
            
            selected, _ = app.render_interactive_menu("Settings 🔧", options, cols, 0)
            if not selected: return
            
            choice = selected["key"]
            if choice == "0": return
            
            if choice == "1":
                new_key = Prompt.ask("Enter new API Key (leave empty to cancel)")
                if new_key:
                    app.save_api_key(new_key)
                    app.init_youtube_client()
            elif choice == "2":
                new_vol = Prompt.ask("Enter volume (0-100)", default=str(app.volume))
                try:
                    vol = int(new_vol)
                    if 0 <= vol <= 100:
                        app.volume = vol
                        app.save_config()
                except: pass
            elif choice == "3":
                new_style = "classic" if app.gui_style == "arrow" else "arrow"
                app.gui_style = new_style
                app.save_config()
                app.console.print(f"[green]Style changed to {new_style.upper()}[/green]")
                time.sleep(1)
            elif choice == "4":
                app.autoplay = not app.autoplay
                msg = "[green]Autoplay ON[/green]" if app.autoplay else "[red]Autoplay OFF[/red]"
                app.console.print(msg)
                time.sleep(0.5)

        else:
            # Classic
            app.console.clear()
            app.print_banner()
            app.console.print("[bold underline]🔧 Settings[/bold underline]\n")
            
            table = Table(box=box.ROUNDED, show_header=False)
            table.add_column("Key", style="cyan")
            table.add_column("Setting", style="white")
            table.add_column("Value", style="yellow")
            
            table.add_row("[1]", "API Key", f"{app.api_key[:10]}...")
            table.add_row("[2]", "Volume", f"{app.volume}%")
            table.add_row("[3]", "GUI Style", app.gui_style.upper())
            table.add_row("[4]", "Autoplay", autoplay_status)
            table.add_row("[0]", "Back")
            
            app.console.print(Align.center(table))
            choice = Prompt.ask("Select", choices=["1", "2", "3", "4", "0"], default="1")
            
            if choice == "0": return
            elif choice == "1":
                new_key = Prompt.ask("Enter new API Key")
                if new_key:
                    app.save_api_key(new_key)
                    app.init_youtube_client()
            elif choice == "2":
                # ... same logic ...
                new_vol = Prompt.ask("Enter volume (0-100)", default=str(app.volume))
                try:
                    vol = int(new_vol)
                    if 0 <= vol <= 100:
                        app.volume = vol
                        app.save_config()
                except: pass
            elif choice == "3":
                new_style = "classic" if app.gui_style == "arrow" else "arrow"
                app.gui_style = new_style
                app.save_config()
                app.console.print(f"[green]Style switched to {new_style}[/green]")
                time.sleep(1)
            elif choice == "4":
                app.autoplay = not app.autoplay
                msg = "[green]Autoplay ON[/green]" if app.autoplay else "[red]Autoplay OFF[/red]"
                app.console.print(msg)
                time.sleep(0.5)
