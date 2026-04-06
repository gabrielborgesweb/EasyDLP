import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sv_ttk
import darkdetect
import tksvg
from PIL import Image, ImageTk
import yt_dlp
import os
import sys
import threading
import queue
import json
import time
import winsound
import requests
from io import BytesIO
from win11toast import toast

# Constants
FORMATS = ["mp4", "mp3", "webm", "wav"]
QUALITIES = [
    "Automático",
    "2160p | 60fps",
    "2160p | 30fps",
    "1440p | 60fps",
    "1440p | 30fps",
    "1080p | 60fps",
    "1080p | 30fps",
    "720p | 60fps",
    "720p | 30fps",
    "480p",
    "360p",
]
CODECS = ["Automático", "H.264", "H.265", "VP9"]
POST_ACTIONS = ["Nada", "Abrir Pasta", "Desligar PC", "Notificar"]


def get_base_path():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(get_base_path(), "userpref.json")
HISTORY_PATH = os.path.join(get_base_path(), "history.json")


class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg=self.get_bg_color())
        self.scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview
        )
        self.scrollable_window = ttk.Frame(self.canvas)

        self.scrollable_window.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.scrollable_window, anchor="nw"
        )

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def get_bg_color(self):
        # Approximate background color for Sun Valley theme
        return "#1c1c1c" if darkdetect.isDark() else "#f3f3f3"

    def _on_canvas_configure(self, event):
        # Resize the scrollable window to match the canvas width
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class PlaylistPopup(tk.Toplevel):
    def __init__(self, parent, title="Playlist Detectada"):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x180")
        self.resizable(False, False)
        self.result = None

        self.label = ttk.Label(
            self,
            text="Este link contém uma playlist.\nO que deseja fazer?",
            font=("Segoe UI", 11),
            justify="center",
        )
        self.label.pack(pady=20)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)

        self.btn_playlist = ttk.Button(
            btn_frame,
            text="Playlist Completa",
            style="Accent.TButton",
            command=self.on_playlist,
        )
        self.btn_playlist.pack(side="left", padx=10)

        self.btn_single = ttk.Button(
            btn_frame, text="Apenas um Vídeo", command=self.on_single
        )
        self.btn_single.pack(side="left", padx=10)

        self.btn_cancel = ttk.Button(btn_frame, text="Cancelar", command=self.on_cancel)
        self.btn_cancel.pack(side="left", padx=10)

        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.wait_window()

    def on_playlist(self):
        self.result = "playlist"
        self.destroy()

    def on_single(self):
        self.result = "single"
        self.destroy()

    def on_cancel(self):
        self.result = "cancel"
        self.destroy()


class DownloadCard(ttk.Frame):
    def __init__(self, master, info, app, **kwargs):
        super().__init__(master, **kwargs)
        self.info = info
        self.app = app
        self.status = "waiting"
        self.file_path = None
        self.thumbnail_image = None  # Keep reference

        self.columnconfigure(1, weight=1)

        # Thumbnail placeholder
        self.thumb_label = ttk.Label(
            self,
            text="...",
            background="#333" if darkdetect.isDark() else "#ccc",
            width=15,
        )
        self.thumb_label.grid(row=0, column=0, rowspan=2, padx=10, pady=10)

        # Text Frame
        self.text_frame = ttk.Frame(self)
        self.text_frame.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(10, 0))
        self.text_frame.columnconfigure(0, weight=1)

        self.title_label = ttk.Label(
            self.text_frame,
            text=info.get("title", "Extraindo..."),
            font=("Segoe UI", 10, "bold"),
        )
        self.title_label.grid(row=0, column=0, sticky="w")

        self.info_label = ttk.Label(
            self.text_frame, text="Aguardando...", font=("Segoe UI", 9)
        )
        self.info_label.grid(row=1, column=0, sticky="w")

        # Progress
        self.progress_bar = ttk.Progressbar(self, mode="determinate")
        self.progress_bar.grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10)
        )

        # Controls
        self.controls_frame = ttk.Frame(self)
        self.controls_frame.grid(row=0, column=2, rowspan=3, padx=10)

        self.btn_open = ttk.Button(
            self.controls_frame,
            image=self.app.icons["play"],
            width=5,
            state="disabled",
            command=self.open_file,
        )
        self.btn_open.pack(side="left", padx=2)

        self.btn_folder = ttk.Button(
            self.controls_frame,
            image=self.app.icons["folder"],
            width=5,
            state="disabled",
            command=self.open_folder,
        )
        self.btn_folder.pack(side="left", padx=2)

        self.btn_copy = ttk.Button(
            self.controls_frame,
            image=self.app.icons["copy"],
            width=5,
            command=self.copy_link,
        )
        self.btn_copy.pack(side="left", padx=2)

        self.btn_delete = ttk.Button(
            self.controls_frame,
            image=self.app.icons["trash"],
            width=5,
            command=self.remove_self,
        )
        self.btn_delete.pack(side="left", padx=2)

    def update_progress(self, d):
        if d["status"] == "downloading":
            p = (
                (d.get("downloaded_bytes", 0) / d.get("total_bytes", 1)) * 100
                if d.get("total_bytes")
                else 0
            )
            self.progress_bar["value"] = p
            percent = d.get("_percent_str", "0%")
            speed = d.get("_speed_str", "0MB/s")
            self.info_label.configure(text=f"{percent} - {speed}")
        elif d["status"] == "finished":
            self.progress_bar["value"] = 100
            self.info_label.configure(text="Concluído", foreground="green")
            self.btn_open.configure(state="normal")
            self.btn_folder.configure(state="normal")
            self.status = "finished"
            self.file_path = d.get("info_dict", {}).get("_filename")

    def open_file(self):
        if self.file_path and os.path.exists(self.file_path):
            os.startfile(self.file_path)

    def open_folder(self):
        if self.file_path:
            folder = os.path.dirname(self.file_path)
            if os.path.exists(folder):
                os.startfile(folder)

    def copy_link(self):
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(
            self.info.get("webpage_url", "") or self.info.get("url", "")
        )

    def remove_self(self):
        self.app.remove_from_queue(self)


class EasyDLPApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EasyDLP")
        self.root.geometry("1050x650")

        self.apply_theme()
        self.load_icons()

        self.queue = []
        self.download_queue = queue.Queue()
        self.is_processing = False

        self.setup_ui()
        self.load_settings()

        threading.Thread(target=self.queue_processor, daemon=True).start()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def apply_theme(self):
        theme = darkdetect.theme() or "dark"
        sv_ttk.set_theme(theme.lower())

    def load_icons(self):
        self.icons = {}
        base = get_base_path()
        icon_files = {
            "play": "play.svg",
            "folder": "folder.svg",
            "copy": "copy.svg",
            "trash": "trash.svg",
        }
        for key, name in icon_files.items():
            path = os.path.join(base, name)
            if os.path.exists(path):
                self.icons[key] = tksvg.SvgImage(file=path, scale=0.6)
            else:
                self.icons[key] = None

    def setup_ui(self):
        # Grid layout
        self.root.columnconfigure(0, weight=0)  # Config
        self.root.columnconfigure(1, weight=1)  # Fila
        self.root.rowconfigure(0, weight=1)

        # Left Panel (Config)
        self.left_frame = ttk.Frame(self.root, padding=20, style="Card.TFrame")
        self.left_frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(
            self.left_frame, text="Configurações", font=("Segoe UI", 18, "bold")
        ).pack(pady=(0, 20), anchor="w")

        # URL
        url_frame = ttk.Frame(self.left_frame)
        url_frame.pack(fill="x", pady=(0, 15))
        ttk.Label(url_frame, text="URL do Vídeo/Playlist:").pack(anchor="w")

        entry_row = ttk.Frame(url_frame)
        entry_row.pack(fill="x")
        self.url_entry = ttk.Entry(entry_row, width=35)
        self.url_entry.pack(side="left", fill="x", expand=True)
        self.btn_paste = ttk.Button(entry_row, text="Colar", command=self.paste_url)
        self.btn_paste.pack(side="right", padx=(5, 0))

        # Format & Quality
        fq_frame = ttk.Frame(self.left_frame)
        fq_frame.pack(fill="x", pady=(0, 15))

        f_sub = ttk.Frame(fq_frame)
        f_sub.pack(side="left", fill="x", expand=True)
        ttk.Label(f_sub, text="Formato:").pack(anchor="w")
        self.format_var = tk.StringVar(value=FORMATS[0])
        self.format_menu = ttk.Combobox(
            f_sub, values=FORMATS, textvariable=self.format_var, state="readonly"
        )
        self.format_menu.pack(fill="x", padx=(0, 5))

        q_sub = ttk.Frame(fq_frame)
        q_sub.pack(side="left", fill="x", expand=True)
        ttk.Label(q_sub, text="Qualidade:").pack(anchor="w")
        self.quality_var = tk.StringVar(value=QUALITIES[0])
        self.quality_menu = ttk.Combobox(
            q_sub, values=QUALITIES, textvariable=self.quality_var, state="readonly"
        )
        self.quality_menu.pack(fill="x")

        # Codec
        ttk.Label(self.left_frame, text="Codec:").pack(anchor="w")
        self.codec_var = tk.StringVar(value=CODECS[0])
        self.codec_menu = ttk.Combobox(
            self.left_frame,
            values=CODECS,
            textvariable=self.codec_var,
            state="readonly",
        )
        self.codec_menu.pack(fill="x", pady=(0, 15))

        # Destination
        ttk.Label(self.left_frame, text="Destino:").pack(anchor="w")
        dest_row = ttk.Frame(self.left_frame)
        dest_row.pack(fill="x", pady=(0, 15))
        self.dest_var = tk.StringVar(
            value=os.path.join(os.path.expanduser("~"), "Downloads")
        )
        self.dest_entry = ttk.Entry(dest_row, textvariable=self.dest_var)
        self.dest_entry.pack(side="left", fill="x", expand=True)
        self.dest_btn = ttk.Button(
            dest_row, text="...", width=3, command=self.browse_dest
        )
        self.dest_btn.pack(side="right", padx=(5, 0))

        # Post Action
        ttk.Label(self.left_frame, text="Após baixar:").pack(anchor="w")
        self.post_action_var = tk.StringVar(value=POST_ACTIONS[0])
        self.post_action_menu = ttk.Combobox(
            self.left_frame,
            values=POST_ACTIONS,
            textvariable=self.post_action_var,
            state="readonly",
        )
        self.post_action_menu.pack(fill="x", pady=(0, 30))

        # Add Button
        self.add_btn = ttk.Button(
            self.left_frame,
            text="Adicionar à Fila",
            style="Accent.TButton",
            command=self.on_add_click,
        )
        self.add_btn.pack(fill="x", pady=10)

        # Right Panel (Queue)
        self.right_frame = ttk.Frame(self.root, padding=20)
        self.right_frame.grid(row=0, column=1, sticky="nsew")
        self.right_frame.columnconfigure(0, weight=1)
        self.right_frame.rowconfigure(1, weight=1)

        header_row = ttk.Frame(self.right_frame)
        header_row.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        ttk.Label(
            header_row, text="Fila de Downloads", font=("Segoe UI", 18, "bold")
        ).pack(side="left")

        self.btn_clear = ttk.Button(
            header_row, text="Limpar Concluídos", command=self.clear_finished
        )
        self.btn_clear.pack(side="right")

        self.scroll_frame = ScrollableFrame(self.right_frame)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")

    def paste_url(self):
        try:
            url = self.root.clipboard_get()
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, url)
        except:
            pass

    def browse_dest(self):
        path = filedialog.askdirectory()
        if path:
            self.dest_var.set(path)

    def on_add_click(self):
        url = self.url_entry.get().strip()
        if not url:
            return
        threading.Thread(target=self.handle_new_url, args=(url,), daemon=True).start()

    def handle_new_url(self, url):
        ydl_opts = {"quiet": True, "extract_flat": "in_playlist"}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if "entries" in info:
                    self.root.after(0, lambda: self.show_playlist_popup(info))
                else:
                    self.root.after(0, lambda: self.add_single_video(info))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Erro", str(e)))

    def show_playlist_popup(self, info):
        popup = PlaylistPopup(self.root)
        if popup.result == "playlist":
            for entry in info["entries"]:
                self.add_single_video(entry)
        elif popup.result == "single":
            self.add_single_video(info["entries"][0])

    def add_single_video(self, info, from_history=False):
        card = DownloadCard(self.scroll_frame.scrollable_window, info, self)
        card.pack(fill="x", pady=5, padx=5)
        self.queue.append(card)

        url = info.get("webpage_url") or info.get("url")
        # Fix: Always try to fetch/render thumbnail even from history
        threading.Thread(
            target=self.fetch_card_details, args=(card, url), daemon=True
        ).start()

        if not from_history:
            task = {
                "card": card,
                "url": url,
                "format": self.format_var.get(),
                "quality": self.quality_var.get(),
                "codec": self.codec_var.get(),
                "dest": self.dest_var.get(),
            }
            self.download_queue.put(task)

    def fetch_card_details(self, card, url):
        ydl_opts = {"quiet": True, "skip_download": True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "Sem título")
                thumb_url = info.get("thumbnail")

                self.root.after(0, lambda: card.title_label.configure(text=title))

                if thumb_url:
                    response = requests.get(thumb_url, timeout=10)
                    img = Image.open(BytesIO(response.content))
                    img.thumbnail((120, 68))
                    photo = ImageTk.PhotoImage(img)
                    self.root.after(0, lambda: self.update_card_thumb(card, photo))
        except:
            pass

    def update_card_thumb(self, card, photo):
        card.thumbnail_image = photo  # Keep reference
        card.thumb_label.configure(image=photo, text="")

    def remove_from_queue(self, card):
        card.destroy()
        if card in self.queue:
            self.queue.remove(card)

    def clear_finished(self):
        to_remove = [c for c in self.queue if c.status == "finished"]
        for c in to_remove:
            self.remove_from_queue(c)
        print("Lista limpa com sucesso.")

    def queue_processor(self):
        while True:
            task = self.download_queue.get()
            if task is None:
                break
            card = task["card"]
            if not card.winfo_exists():
                self.download_queue.task_done()
                continue
            self.is_processing = True
            card.status = "downloading"
            self.run_download(task)
            self.download_queue.task_done()
            if self.download_queue.empty():
                self.is_processing = False
                self.root.after(0, self.on_all_finished)

    def run_download(self, task):
        card, url, fmt, quality, codec, dest = (
            task["card"],
            task["url"],
            task["format"],
            task["quality"],
            task["codec"],
            task["dest"],
        )
        ydl_opts = {
            "outtmpl": os.path.join(dest, "%(title)s.%(ext)s"),
            "progress_hooks": [card.update_progress],
            "noprogress": True,
            "quiet": True,
        }
        if fmt in ["mp3", "wav"]:
            ydl_opts.update(
                {
                    "format": "bestaudio/best",
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": fmt,
                            "preferredquality": "192",
                        }
                    ],
                }
            )
        else:
            q_str = quality.split("|")[0].strip().replace("p", "")
            fps = (
                "[fps>30]"
                if "60fps" in quality
                else ("[fps<=30]" if "30fps" in quality else "")
            )
            c_filter = (
                "[vcodec^=avc1]"
                if codec == "H.264"
                else (
                    "[vcodec^=hev1]"
                    if codec == "H.265"
                    else ("[vcodec^=vp9]" if codec == "VP9" else "")
                )
            )
            if quality == "Automático":
                ydl_opts.update(
                    {
                        "format": f"bestvideo{c_filter}+bestaudio/best",
                        "merge_output_format": fmt,
                    }
                )
            else:
                ydl_opts.update(
                    {
                        "format": f"bestvideo[height<={q_str}]{fps}{c_filter}+bestaudio/best",
                        "merge_output_format": fmt,
                    }
                )
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            self.root.after(
                0,
                lambda: card.info_label.configure(
                    text=f"Erro: {str(e)}", foreground="red"
                ),
            )

    def on_all_finished(self):
        action = self.post_action_var.get()
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
        toast("EasyDLP", "Todos os downloads foram concluídos!")
        if action == "Abrir Pasta":
            os.startfile(self.dest_var.get())
        elif action == "Desligar PC":
            os.system("shutdown /s /t 60")

    def load_settings(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r") as f:
                    data = json.load(f)
                    self.format_var.set(data.get("format", FORMATS[0]))
                    self.quality_var.set(data.get("quality", QUALITIES[0]))
                    self.codec_var.set(data.get("codec", CODECS[0]))
                    self.dest_var.set(data.get("dest", self.dest_var.get()))
                    self.post_action_var.set(data.get("post_action", POST_ACTIONS[0]))
            except:
                pass
        if os.path.exists(HISTORY_PATH):
            try:
                with open(HISTORY_PATH, "r") as f:
                    history = json.load(f)
                    for item in history:
                        self.add_single_video(item, from_history=True)
            except:
                pass

    def save_settings(self):
        data = {
            "format": self.format_var.get(),
            "quality": self.quality_var.get(),
            "codec": self.codec_var.get(),
            "dest": self.dest_var.get(),
            "post_action": self.post_action_var.get(),
        }
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(data, f)
            history = [card.info for card in self.queue if card.winfo_exists()]
            with open(HISTORY_PATH, "w") as f:
                json.dump(history, f)
        except:
            pass

    def on_closing(self):
        self.save_settings()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = EasyDLPApp(root)
    root.mainloop()
