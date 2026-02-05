
import speedtest
import sys
import os
import socket
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt
from rich.table import Table
from rich.align import Align
from rich.text import Text
from rich import box

def check_connection(host="8.8.8.8", port=53, timeout=3):
    """
    Checks internet connection by attempting to connect to Google DNS.
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except socket.error:
        return False

def run_test(console, gui_style="choice", input_handler=None):
    console.clear()
    console.rule("[bold cyan]Internet Speed Test 🚀[/bold cyan]")
    
    # 1. Connection Check
    with console.status("[bold yellow]Checking Internet Connection...[/bold yellow]", spinner="dots"):
        is_connected = check_connection()
        
    if not is_connected:
        console.print(Panel("[bold red]❌ No Internet Connection Detected![/bold red]\nPlease check your network settings.", title="Error", border_style="red"))
        Prompt.ask("Press Enter to return...")
        return

    console.print("[bold green]✔ Internet Connection Active[/bold green]\n")

    # 2. Unit Selection
    unit_choice = "1"
    
    # If we have 'arrow' style and an input handler, use interactive menu
    if gui_style == "arrow" and input_handler:
        options = [
            {"key": "1", "desc": "Mbps (Standard)"},
            {"key": "2", "desc": "MB/s (File Speed)"},
            {"key": "0", "desc": "Cancel"}
        ]
        options = [
            {"key": "1", "desc": "Mbps (Standard)"},
            {"key": "2", "desc": "MB/s (File Speed)"},
            {"key": "0", "desc": "Cancel"}
        ]
        idx = 0
        
        def generate_st_menu(current_idx):
            menu_table = Table(box=box.ROUNDED, show_header=False)
            menu_table.add_column("Option", justify="left")
            
            for i, opt in enumerate(options):
                style = "reverse #d79fed" if i == current_idx else ""
                menu_table.add_row(opt['desc'], style=style)
            
            return Group(
                Align.center(menu_table),
                Text("\nNavigate: ▲ ▼ | Select: Enter", style="dim", justify="center")
            )

        console.clear()
        console.rule("[bold cyan]Internet Speed Test 🚀[/bold cyan]\n")
        console.print("[dim]Select Display Unit:[/dim]")
        
        with Live(generate_st_menu(idx), auto_refresh=False, console=console, transient=True) as live:
            while True:
                live.update(generate_st_menu(idx), refresh=True)
                
                key = input_handler.getch()
                if key == 'UP': idx = (idx - 1) % len(options)
                elif key == 'DOWN': idx = (idx + 1) % len(options)
                elif key == 'ENTER': 
                    unit_choice = options[idx]["key"]
                    break
                elif key == 'ESC': 
                    unit_choice = "0"
                    break
                
    else:
        # Classic Mode
        console.print("[dim]Select Display Unit:[/dim]")
        console.print("[1] Mbps (Megabits per second) - Standard")
        console.print("[2] MB/s (Megabytes per second) - File Transfer Speed")
        console.print("[0] Cancel")
        unit_choice = Prompt.ask("Select Unit", choices=["1", "2", "0"], default="1")

    if unit_choice == "0":
        return

    is_mbps = (unit_choice == "1")
    unit_label = "Mbps" if is_mbps else "MB/s"
    conversion = 1.0 if is_mbps else 0.125 # 1 Mbps = 0.125 MB/s

    # 3. Running Test
    try:
        st = None
        
        # We use a progress bar for the phases
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            
            # Phase 1: Finding Server
            task_setup = progress.add_task("[cyan]Finding best server...[/cyan]", total=None)
            st = speedtest.Speedtest()
            st.get_best_server()
            ping = st.results.ping
            progress.update(task_setup, completed=100, description=f"[green]Server Found! (Ping: {ping:.1f} ms)[/green]")
            
            # Phase 2: Download
            task_down = progress.add_task("[blue]Testing Download Speed...[/blue]", total=100)
            
            # Custom callback to update progress
            def update_down(current_bytes, total_bytes=None):
                # Speedtest doesn't always give total, so we simulate or pulse
                # Ideally we just let it spin, but let's try to animate
                pass

            # Since speedtest-cli callbacks are tricky to map exactly to % usage without known total size properly, 
            # we will just indicate we are working.
            # But st.download() runs synchronously. We can't easily update the progress bar in real-time 
            # without threading or hacking the callback. 
            # speedtest-cli allows a callback? No, standard usage blocks.
            # We'll just set indeterminate state.
            
            # Force indeterminate
            progress.update(task_down, total=None)
            download_speed_bits = st.download()
            progress.update(task_down, total=100, completed=100, description="[green]Download Test Complete[/green]")
            
            # Phase 3: Upload
            task_up = progress.add_task("[magenta]Testing Upload Speed...[/magenta]", total=None)
            upload_speed_bits = st.upload()
            progress.update(task_up, total=100, completed=100, description="[green]Upload Test Complete[/green]")

        # 4. Results
        server = st.results.server
        ping = st.results.ping
        
        d_val = (download_speed_bits / 1_000_000) * conversion
        u_val = (upload_speed_bits / 1_000_000) * conversion
        
        results_table = Table(box=None, show_header=False)
        results_table.add_column("Label", style="cyan")
        results_table.add_column("Value", style="bold white")
        
        results_table.add_row("Server", f"{server['name']} ({server['country']})")
        results_table.add_row("Sponsor", server['sponsor'])
        results_table.add_row("Ping", f"{ping:.1f} ms")
        results_table.add_row("Download", f"{d_val:.2f} {unit_label}")
        results_table.add_row("Upload", f"{u_val:.2f} {unit_label}")
        
        panel = Panel(
            Align.center(results_table),
            title=f"[bold gold1]Speed Test Results ({unit_label})[/bold gold1]",
            border_style="green",
            padding=(1, 2)
        )
        
        console.print("\n")
        console.print(panel)
        
    except Exception as e:
        console.print(f"\n[red]Speed Test Failed: {e}[/red]")
    
    Prompt.ask("\nPress Enter to return...")
