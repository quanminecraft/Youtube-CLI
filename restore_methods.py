    def saved_songs_ui(self):
        while True:
            if not self.saved_songs:
                console.print(Panel("[yellow]No saved songs yet.[/yellow]", title="Saved Songs", border_style="yellow"))
                time.sleep(1.5)
                return

            if self.gui_style == "arrow":
                options = []
                options.append({"key": "0", "no": "←", "title": "[ Back ]"})
                
                for idx, song in enumerate(self.saved_songs, 1):
                    options.append({
                        "key": str(idx),
                        "no": str(idx),
                        "title": song['title'],
                        "raw": song
                    })

                cols = [
                    ("No.", "no", 4, "right"),
                    ("Title", "title", 60, "left")
                ]
                
                selected, _ = self.render_interactive_menu("Saved Songs 💾", options, cols, 0)
                
                if not selected: return
                choice = selected["key"]
                
                if choice == "0": return
                
                if "raw" in selected:
                    self.show_action_menu(selected["raw"])

            else:
                table = Table(title="Saved Songs 💾", box=box.ROUNDED)
                table.add_column("No.", style="cyan", width=4)
                table.add_column("Title", style="white", width=60)

                item_map = {}
                for idx, song in enumerate(self.saved_songs, 1):
                    table.add_row(str(idx), song['title'])
                    item_map[str(idx)] = song

                console.print(table)
                choice = Prompt.ask("[dim]Select song number or 0 to back[/dim]", default="0")
                
                if choice == "0": return
                if choice in item_map:
                    self.show_action_menu(item_map[choice])

    def play_history_ui(self):
        while True:
            if not self.history:
                console.print(Panel("[yellow]No play history yet.[/yellow]", title="Play History", border_style="yellow"))
                time.sleep(1.5)
                return
            
            # Reverse history (Newest first)
            rev_history = self.history[::-1]
            
            if self.gui_style == "arrow":
                options = []
                options.append({"key": "0", "no": "←", "title": "[ Back ]"})
                
                for idx, item in enumerate(rev_history, 1):
                    options.append({
                        "key": str(idx),
                        "no": str(idx),
                        "title": item['title'],
                        "raw": item
                    })

                cols = [
                    ("No.", "no", 4, "right"),
                    ("Title", "title", 60, "left")
                ]
                
                selected, _ = self.render_interactive_menu("Play History 📜", options, cols, 0)
                
                if not selected: return
                choice = selected["key"]
                
                if choice == "0": return
                
                if "raw" in selected:
                    self.show_action_menu(selected["raw"])

            else:
                table = Table(title="Play History (Recent 50)", box=box.ROUNDED)
                table.add_column("No.", style="cyan", width=4)
                table.add_column("Title", style="white", width=60)

                item_map = {}
                for idx, item in enumerate(rev_history, 1):
                    table.add_row(str(idx), item['title'])
                    item_map[str(idx)] = item
                
                console.print(table)
                choice = Prompt.ask("[dim]Select history item or 0 to back[/dim]", default="0")
                
                if choice == "0": return
                if choice in item_map:
                    self.show_action_menu(item_map[choice])
