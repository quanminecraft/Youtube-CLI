import time
import os
from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from rich import box
from rich.live import Live
from rich.console import Group

class InteractiveMode:
    def __init__(self, app, input_handler):
        self.app = app
        self.console = app.console
        self.input_handler = input_handler
        self.current_idx = 0 

    def render_interactive_menu(self, title, options, columns, selected_idx, allow_back=True, back_key='BACKSPACE', allow_pagination=True, show_banner=False):
        PAGE_SIZE = 10
        start_idx = 0
        if selected_idx >= PAGE_SIZE:
            start_idx = selected_idx - PAGE_SIZE + 1
            
        def generate_table(current_idx, start_pos):
            end_pos = start_pos + PAGE_SIZE
            view_options = options[start_pos:end_pos]
            table = Table(box=box.ROUNDED, show_header=True, show_edge=True, pad_edge=True, expand=True)
            # FORCE SINGLE-LINE LAYOUT
            # This fixes the "Highlight Bleed" bug where one item lights up two rows.
            # All columns will truncate with ellipsis (...) if too long.
            for col in columns:
                align = col[3] if len(col) > 3 else "left"
                w = col[2]
                if w < 12: 
                    table.add_column(col[0], width=w, justify=align, no_wrap=True, overflow="ellipsis")
                else: 
                    table.add_column(col[0], ratio=w, justify=align, no_wrap=True, overflow="ellipsis", min_width=20)

            for i, item in enumerate(view_options):
                true_idx = start_pos + i
                style = item.get("style_active", "reverse #d79fed") if true_idx == current_idx else ""
                
                # Standard data extraction (Sanitization handled at source)
                row_data = [str(item.get(col[1], "")) for col in columns]
                
                table.add_row(*row_data, style=style)
            total = len(options)
            visible_count = len(view_options)
            
            back_symbol = "←" if back_key == "LEFT" else "Backspace"
            back_hint = f" | Back: {back_symbol}" if allow_back else ""
            
            nav_hint = "▲/▼"
            if allow_pagination:
                if back_key != "LEFT": nav_hint = "◄/▲/▼/►"
                elif total > PAGE_SIZE: nav_hint = "▲/▼/►"

            if total > PAGE_SIZE and allow_pagination: 
                 footer_text = f"\nShowing {start_pos + 1}-{start_pos + visible_count} of {total} | Navigate: {nav_hint} | Select: Enter{back_hint}"
            else: 
                 footer_text = f"\nNavigate: {nav_hint} | Select: Enter{back_hint}"

            # Build Render Group strictly top-to-bottom
            render_group = []
            
            # 1. App Banner (Optional)
            if show_banner and hasattr(self.app, 'get_banner_renderable'):
                render_group.append(self.app.get_banner_renderable())
            
            # 2. Menu Title (Always show if present)
            if title:
                # Reduced padding to prevent screen overflow
                render_group.append(Align.center(Text(f"{title}", style="bold gold1")))
                render_group.append(Text(" ")) # Small spacer
            
            # 3. Data Table
            render_group.append(Align.center(table))
            
            # 4. Footer
            if footer_text:
                render_group.append(Align.center(Text(footer_text, style="dim")))
            
            return Group(*render_group)

        # screen=True enables alternate screen buffer (fullscreen), preventing ghosting/history issues
        with Live(generate_table(selected_idx, start_idx), auto_refresh=False, console=self.console, screen=True, transient=True) as live:
            while True:
                if selected_idx < start_idx: start_idx = selected_idx
                elif selected_idx >= start_idx + PAGE_SIZE: start_idx = selected_idx - PAGE_SIZE + 1
                max_start = max(0, len(options) - PAGE_SIZE)
                live.update(generate_table(selected_idx, start_idx), refresh=True)
                key = self.input_handler.getch()
                if key == 'UP': selected_idx = (selected_idx - 1) % len(options)
                elif key == 'DOWN': selected_idx = (selected_idx + 1) % len(options)
                elif key == 'ENTER': return options[selected_idx], selected_idx
                elif key == back_key and allow_back: return None, selected_idx
                
                # Dynamic Logic for Left/Right
                elif key == 'RIGHT' and allow_pagination:
                    next_page_opt = next((opt for opt in options if opt.get("key") == "n"), None)
                    if next_page_opt: return next_page_opt, selected_idx
                    # Page Down
                    if selected_idx + PAGE_SIZE < len(options): selected_idx += PAGE_SIZE
                    else: selected_idx = len(options) - 1
                
                elif key == 'LEFT' and allow_pagination:
                    # If back_key is LEFT, it's already handled above.
                    # Otherwise, this is "Previous" / Page Up
                    if selected_idx - PAGE_SIZE >= 0: selected_idx -= PAGE_SIZE
                    else: selected_idx = 0


    def main_menu(self):
        options = [
            {"key": "1", "icon": "🔍", "action": "Search", "desc": "Search YouTube and Play"},
            {"key": "2", "icon": "🌐", "action": "Play from link", "desc": "Play directly from YouTube URL"},
            {"key": "3", "icon": "💾", "action": "Saved Songs", "desc": "Your personal playlist"},
            {"key": "4", "icon": "📜", "action": "Play History", "desc": "Recently played tracks"},
            # Autoplay removed (moved to settings)
            {"key": "5", "icon": "🔧", "action": "Settings", "desc": "API Key, Volume, Autoplay, Style"},
            {"key": "6", "icon": "📂", "action": "Offline Mode", "desc": "Play downloaded content"},
            {"key": "7", "icon": "🚀", "action": "Internet Speed Test", "desc": "Check network connection speed"},
            {"key": "0", "icon": "🚪", "action": "[ Exit ]", "desc": "Close application"}
        ]
        cols = [("Icon", "icon", 4, "center"), ("Action", "action", 25, "left"), ("Desc", "desc", 40, "left")]
        while True:
            sel, self.app.main_menu_idx = self.render_interactive_menu(None, options, cols, self.app.main_menu_idx, allow_back=False, allow_pagination=False, show_banner=True)
            if not sel: return "0"
            return sel["key"]
