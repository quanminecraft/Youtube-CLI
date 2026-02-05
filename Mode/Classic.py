import time
import os
import re
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich.align import Align
from rich import box

class ClassicMode:
    def __init__(self, app):
        self.app = app
        self.console = app.console

    def main_menu(self):
        self.app.print_banner()
        menu_table = Table(box=box.ROUNDED, show_header=False, show_edge=True, pad_edge=True)
        menu_table.add_column("Key", justify="center", style="bold cyan", width=6) 
        menu_table.add_column("Icon", justify="center", width=4)
        menu_table.add_column("Action", justify="left", style="bold white", width=20)
        menu_table.add_column("Description", justify="left", style="dim white")
        
        menu_table.add_row("[1]", "🔍", "Search", "Search YouTube and play audio")
        menu_table.add_row("[2]", "🌐", "Play from link", "Play directly from YouTube URL")
        menu_table.add_row("[3]", "💾", "Saved Songs", "Your personal playlist")
        menu_table.add_row("[4]", "📜", "Play History", "Recently played tracks")
        # Autoplay removed
        menu_table.add_row("[5]", "🔧", "Settings", "API Key, Volume, Autoplay")
        menu_table.add_row("[6]", "📂", "Offline Mode", "Play downloaded music")
        menu_table.add_row("[7]", "🚀", "Internet Speed Test", "Check connection speed")
        menu_table.add_row("[0]", "🚪", "Exit", "Close application")
        
        self.console.print(Align.center(menu_table))
        self.console.print("\n")
        choice = Prompt.ask("[bold cyan]Select[/bold cyan]", choices=["1", "2", "3", "4", "5", "6", "7", "0"])
        return choice
