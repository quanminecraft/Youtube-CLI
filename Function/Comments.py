from rich.table import Table
from rich.panel import Panel
from rich.align import Align
from rich import box
from rich.prompt import Prompt
from rich.text import Text
import textwrap

def show_comments(app, video_id, title):
    next_page_token = None
    total_comments = "Unknown"
    
    # Fetch Statistics First
    try:
        with app.console.status("[bold blue]Fetching statistics...[/bold blue]"):
            stat_req = app.youtube.videos().list(
                part="statistics",
                id=video_id
            )
            stat_resp = stat_req.execute()
            if stat_resp.get("items"):
                total_comments = stat_resp["items"][0]["statistics"].get("commentCount", "Unknown")
    except: pass

    current_idx = 0
    
    while True: # Page Loop
        try:
            items = []
            new_token = None
            
            with app.console.status(f"[bold blue]Loading comments ({total_comments} total)...[/bold blue]"):
                request = app.youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    maxResults=30, # Increased limit
                    textFormat="plainText",
                    order="relevance",
                    pageToken=next_page_token
                )
                response = request.execute()
                items = response.get("items", [])
                new_token = response.get("nextPageToken")

            if not items and not next_page_token:
                app.console.print("[yellow]No comments found.[/yellow]")
                Prompt.ask("Press Enter to return...")
                return

            comments_data = []
            for item in items:
                comment = item["snippet"]["topLevelComment"]["snippet"]
                comments_data.append({
                    "author": comment["authorDisplayName"],
                    "text": comment["textDisplay"],
                    "likes": str(comment["likeCount"]),
                    "date": comment["publishedAt"][:10]
                })
            
            # Display Loop (Interaction within page)
            while True:
                app.console.clear()
                app.print_banner()
                app.console.print(f"[bold gold1]Comments for: {title}[/bold gold1]")
                app.console.print(f"[dim]Total Comments: {total_comments} | Showing {len(comments_data)} on this page[/dim]\n")
                
                if app.gui_style == "arrow":
                    options = []
                    # Add Next Page option if token exists
                    extras_len = 0
                    
                    options.append({"key": "0", "author": "[ Back ]", "preview": "Return to menu", "likes": ""})
                    
                    for idx, c in enumerate(comments_data, 1):
                        preview = textwrap.shorten(c["text"], width=60, placeholder="...")
                        options.append({
                            "key": str(idx),
                            "author": c["author"],
                            "preview": preview,
                            "likes": f"👍 {c['likes']}",
                            "full_text": c["text"]
                        })
                    
                    if new_token:
                         options.append({"key": "n", "author": ">>", "preview": "Next Page", "likes": ""})

                    cols = [
                        ("Author", "author", 20, "left"),
                        ("Comment", "preview", 60, "left"),
                        ("Likes", "likes", 10, "center")
                    ]
                    
                    if current_idx >= len(options): current_idx = len(options) - 1
                    selected, current_idx = app.render_interactive_menu(None, options, cols, current_idx)
                    
                    if not selected: return
                    choice = selected["key"]
                    
                    if choice == "0": return
                    
                    if choice == "n":
                        if new_token:
                            next_page_token = new_token
                            break # Break inner loop to fetch next page (outer loop)
                        else: continue

                    # Show Full Comment
                    if "full_text" in selected:
                        app.console.clear()
                        panel = Panel(
                            Text(selected["full_text"], style="white"),
                            title=f"[cyan]{selected['author']}[/cyan] ({selected['likes']})",
                            subtitle="Press Enter to close",
                            border_style="green",
                            padding=(1, 2)
                        )
                        app.console.print(Align.center(panel))
                        app.input_handler.getch() # Wait for key
                        
                else:
                    # Classic Mode
                    table = Table(box=box.ROUNDED, show_header=True)
                    table.add_column("No.", style="cyan", width=4)
                    table.add_column("Author", style="magenta", width=20)
                    table.add_column("Comment", style="white", width=70)
                    table.add_column("Likes", style="green", width=8)
                    
                    for idx, c in enumerate(comments_data, 1):
                        preview = textwrap.shorten(c["text"], width=70, placeholder="...")
                        table.add_row(str(idx), c["author"], preview, c["likes"])
                    
                    app.console.print(table)
                    
                    prompt_opts = [str(i) for i in range(1, len(comments_data)+1)] + ["0"]
                    prompt_msg = "[dim]Enter number to read, or 0 to back[/dim]"
                    
                    if new_token:
                        prompt_opts.append("n")
                        prompt_msg = "[dim]Enter number to read, 'n' for Next Page, or 0 to back[/dim]"
                    
                    app.console.print(prompt_msg)
                    choice = Prompt.ask("Select", choices=prompt_opts, default="0")
                    
                    if choice == "0": return
                    
                    if choice == "n":
                        if new_token:
                            next_page_token = new_token
                            break
                        continue
                    
                    try:
                        idx = int(choice) - 1
                        if 0 <= idx < len(comments_data):
                            c = comments_data[idx]
                            app.console.clear()
                            panel = Panel(
                                Text(c["text"], style="white"),
                                title=f"[cyan]{c['author']}[/cyan] (👍 {c['likes']})",
                                subtitle="Press Enter to close",
                                border_style="green",
                                padding=(1, 2)
                            )
                            app.console.print(Align.center(panel))
                            Prompt.ask("")
                    except: pass
                    
        except Exception as e:
            app.console.print(f"[red]Error loading comments: {e}[/red]")
            Prompt.ask("Press Enter to return...")
            return
