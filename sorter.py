import os
import json
import shutil
import re
import sys
import tkinter as tk
from tkinter import filedialog, ttk
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time

CONFIG_FILE = "sorting_rules.json"
TAG_PATTERN = r"^(\[.*?\])"


def get_unique_filename(destination, file_name):
    base_name, ext = os.path.splitext(file_name)
    new_file_path = os.path.join(destination, file_name)
    counter = 1
    while os.path.exists(new_file_path):
        new_file_name = f"{base_name}_{counter}{ext}"
        new_file_path = os.path.join(destination, new_file_name)
        counter += 1
    return new_file_path


class AutoSortHandler(FileSystemEventHandler):
    def __init__(self, sorting_rules):
        super().__init__()
        self.sorting_rules = sorting_rules

    def on_created(self, event):
        if event.is_directory:
            return
        
        file_path = event.src_path
        file_name = os.path.basename(file_path)

        if self.wait_for_download(file_path):
            tag = self.extract_tag(file_name)
            if tag and tag in self.sorting_rules:
                destination_folder = self.sorting_rules[tag]
                self.move_file(file_path, destination_folder)

    def wait_for_download(self, file_path, timeout=30, interval=1):
        """Waits until the file is fully downloaded and not locked by any process."""
        previous_size = -1
        elapsed_time = 0

        while elapsed_time < timeout:
            if not os.path.exists(file_path):
                time.sleep(interval)
                elapsed_time += interval
                continue

            current_size = os.path.getsize(file_path)

            # Check if the file size has stopped changing
            if current_size == previous_size:
                # Check if the file is locked (Windows-specific issue)
                try:
                    with open(file_path, "rb"):
                        return True  # If file can be opened, it's not locked
                except PermissionError:
                    pass  # File is still locked, wait longer

            previous_size = current_size
            time.sleep(interval)
            elapsed_time += interval

        print(f"Timeout: File {file_path} may not have fully downloaded.")
        return False

    def extract_tag(self, file_name):
        match = re.match(TAG_PATTERN, file_name)
        return match.group(1).lower() if match else None

    def move_file(self, file_path, destination_folder):
        if not os.path.exists(destination_folder):
            return
        file_name = os.path.basename(file_path)
        new_path = get_unique_filename(destination_folder, file_name)
        
        time.sleep(1)  # Ensure processing delay of 1 second before moving
        shutil.move(file_path, new_path)



class AutoSorterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sakura Sorter")
        self.root.geometry("640x480")
        self.root.configure(bg="#121212")
        self.settings = self.load_settings()
        self.sorting_rules = self.settings.get("sorting_rules", {})
        self.watch_folder = tk.StringVar(value=self.settings.get("watch_folder", ""))
        self.observer = None
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.apply_styles()
        self.create_widgets()
        self.set_icon()

    def set_icon(self):
        if sys.platform.startswith("win"):
            icon_path = os.path.join(os.getcwd(), "icon.ico")
        else:
            icon_path = os.path.join(os.getcwd(), "icon.png")
        if os.path.exists(icon_path):
            self.root.iconphoto(True, tk.PhotoImage(file=icon_path))

    def apply_styles(self):
        self.style.configure("TButton", font=("Fira Code", 10), padding=5, background="#1E1E1E", foreground="white")
        self.style.configure("TLabel", background="#121212", foreground="white", font=("Fira Code", 12))
        self.style.configure("TEntry", fieldbackground="#1E1E1E", foreground="white", font=("Fira Code", 10))
        self.style.configure("Treeview", background="#1E1E1E", foreground="white", fieldbackground="#1E1E1E", font=("Fira Code", 10))
        self.style.configure("Treeview.Heading", font=("Fira Code", 10, "bold"), background="#333333", foreground="white")

    def create_widgets(self):
        tk.Label(self.root, text="Watch Folder:", bg="#121212", fg="white").pack(pady=5)
        
        watch_frame = tk.Frame(self.root, bg="#121212")
        watch_frame.pack(fill="x", padx=10)
        
        watch_entry = ttk.Entry(watch_frame, textvariable=self.watch_folder, width=30)  # Reduced width
        watch_entry.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        
        ttk.Button(watch_frame, text="Browse", command=self.choose_watch_folder).pack(side="right", padx=5)
        
        self.tree = ttk.Treeview(self.root, columns=("Tag", "Path"), show="headings", height=5)
        self.tree.heading("Tag", text="Tag")
        self.tree.heading("Path", text="Destination Path")
        self.tree.pack(fill="both", expand=True, padx=10, pady=5)
        self.refresh_table()
        
        input_frame = tk.Frame(self.root, bg="#121212")
        input_frame.pack(fill="x", padx=10, pady=5)

        self.tag_entry = ttk.Entry(input_frame, width=12)  # Shorter width
        self.tag_entry.pack(side="left", padx=5)
        self.tag_entry.insert(0, "Tag")

        self.path_entry = ttk.Entry(input_frame, width=20)  # Shorter width
        self.path_entry.pack(side="left", padx=5)
        self.path_entry.insert(0, "Path")

        ttk.Button(input_frame, text="Browse", command=self.choose_folder).pack(side="left", padx=5)
        ttk.Button(input_frame, text="Add", command=self.add_tag).pack(side="left", padx=5)
        ttk.Button(input_frame, text="Remove", command=self.remove_tag).pack(side="left", padx=5)

        self.start_button = ttk.Button(self.root, text="Start Monitoring", command=self.toggle_monitoring)
        self.start_button.pack(fill="x", padx=10, pady=10)

    def save_settings(self):
        """Saves sorting rules and watch folder to JSON."""
        data = {
            "sorting_rules": self.sorting_rules,
            "watch_folder": self.watch_folder.get()
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=4)

    def load_settings(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        return {"sorting_rules": {}, "watch_folder": ""}

    def choose_watch_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.watch_folder.set(folder)
            self.save_settings()

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, folder)

    def add_tag(self):
        tag = self.tag_entry.get().strip().lower()
        path = self.path_entry.get().strip()
        if tag and path:
            self.sorting_rules[tag] = path
            self.save_settings()
            self.refresh_table()

    def remove_tag(self):
        selected_item = self.tree.selection()
        if selected_item:
            tag = self.tree.item(selected_item, "values")[0]
            del self.sorting_rules[tag]
            self.save_settings()
            self.refresh_table()

    def refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for tag, path in self.sorting_rules.items():
            self.tree.insert("", "end", values=(tag, path))

    def toggle_monitoring(self):
        if self.observer:
            self.stop_monitoring()
        else:
            self.start_monitoring()

    def show_warning(self, title, message):
        warning_window = tk.Toplevel(self.root)
        warning_window.title(title)
        warning_window.configure(bg="#121212")
        
        tk.Label(warning_window, text=message, fg="white", bg="#121212", font=("Fira Code", 10)).pack(pady=10, padx=20)
        
        ttk.Button(warning_window, text="OK", command=warning_window.destroy).pack(pady=10)

        warning_window.transient(self.root)
        warning_window.grab_set()
        self.root.wait_window(warning_window)

    def start_monitoring(self):
        if not self.watch_folder.get():
            self.show_warning("Error", "Please select a watch folder!")
            return
        event_handler = AutoSortHandler(self.sorting_rules)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.watch_folder.get(), recursive=False)
        self.observer.start()
        self.start_button.config(text="Stop Monitoring")

    def stop_monitoring(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            self.start_button.config(text="Start Monitoring")

    def on_closing(self):
        self.stop_monitoring()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoSorterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()