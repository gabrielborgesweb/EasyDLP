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
    "2160p | 60fps", "2160p | 30fps",
    "1440p | 60fps", "1440p | 30fps",
    "1080p | 60fps", "1080p | 30fps",
    "720p | 60fps", "720p | 30fps",
    "480p", "360p"
]
CODECS = ["Automático", "H.264", "H.265", "VP9"]
POST_ACTIONS = ["Nada", "Abrir Pasta", "Desligar PC", "Notificar"]

def get_base_path():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(get_base_path(), "userpref.json")
HISTORY_PATH = os.path.join(get_base_path(), "history.json")
CACHE_DIR = os.path.join(get_base_path(), "thumbnail_cache")

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)
    print(f"[DEBUG] Cache directory created: {CACHE_DIR}")

class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0, bg=self.get_bg_color())
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_window = ttk.Frame(self.canvas)

        self.scrollable_window.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_window, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def get_bg_color(self):
        return "#1c1c1c" if darkdetect.isDark() else "#f3f3f3"

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        if self.canvas.winfo_exists():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

class DownloadCard(ttk.Frame):
    def __init__(self, master, info, app, index, **kwargs):
        super().__init__(master, **kwargs)
        self.info = info
        self.app = app
        self.status = info.get('status', 'waiting')
        self.file_path = info.get('file_path')
        self.thumbnail_image = None
        
        print(f"[DEBUG] Creating card for: {info.get('title', 'Unknown')} | Status: {self.status} | Path: {self.file_path}")

        self.columnconfigure(1, weight=1)
        
        # Thumbnail
        self.thumb_label = ttk.Label(self, text="...", background="#333" if darkdetect.isDark() else "#ccc", width=15)
        self.thumb_label.grid(row=0, column=0, rowspan=2, padx=10, pady=10)
        
        # Text Frame
        self.text_frame = ttk.Frame(self)
        self.text_frame.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(10, 0))
        self.text_frame.columnconfigure(0, weight=1)

        self.title_label = ttk.Label(self.text_frame, text=info.get('title', 'Extraindo...'), font=("Segoe UI", 10, "bold"))
        self.title_label.grid(row=0, column=0, sticky="w")
        
        self.channel_label = ttk.Label(self.text_frame, text=info.get('uploader', 'Canal desconhecido'), font=("Segoe UI", 9), foreground="gray")
        self.channel_label.grid(row=1, column=0, sticky="w")
        
        self.info_label = ttk.Label(self.text_frame, text="Aguardando...", font=("Segoe UI", 9))
        self.info_label.grid(row=2, column=0, sticky="w")
        
        # Progress Bar
        self.progress_bar = ttk.Progressbar(self, mode="determinate")
        self.progress_bar.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        
        # Controls Frame
        self.controls_frame = ttk.Frame(self)
        self.controls_frame.grid(row=0, column=2, rowspan=4, padx=10)
        
        self.btn_open = ttk.Button(self.controls_frame, image=self.app.icons['play'], width=5, command=self.open_file)
        self.btn_folder = ttk.Button(self.controls_frame, image=self.app.icons['folder'], width=5, command=self.open_folder)
        self.btn_copy = ttk.Button(self.controls_frame, image=self.app.icons['copy'], width=5, command=self.copy_link)
        self.btn_delete = ttk.Button(self.controls_frame, image=self.app.icons['trash'], width=5, command=self.remove_self)
        
        self.btn_copy.pack(side="left", padx=2)
        self.btn_delete.pack(side="left", padx=2)
        
        if self.status == 'finished':
            self.show_finished_state()
        else:
            self.progress_bar.grid()

    def show_finished_state(self):
        self.status = 'finished'
        self.progress_bar.grid_remove()
        self.info_label.configure(text="Concluído", foreground="#4caf50")
        
        self.btn_copy.pack_forget()
        self.btn_delete.pack_forget()
        
        self.btn_open.pack(side="left", padx=2)
        self.btn_folder.pack(side="left", padx=2)
        self.btn_copy.pack(side="left", padx=2)
        self.btn_delete.pack(side="left", padx=2)
        
        print(f"[DEBUG] Card '{self.info.get('title')}' finished state. Path: {self.file_path}")

    def update_progress(self, d):
        if d['status'] == 'downloading':
            p = (d.get('downloaded_bytes', 0) / d.get('total_bytes', 1)) * 100 if d.get('total_bytes') else 0
            self.progress_bar['value'] = p
            percent = d.get('_percent_str', '0%')
            speed = d.get('_speed_str', '0MB/s')
            self.info_label.configure(text=f"{percent} - {speed}")
        elif d['status'] == 'finished':
            print(f"[DEBUG] Hook 'finished' for {self.info.get('title')}")

    def open_file(self):
        print(f"[DEBUG] Attempting to open file: {self.file_path}")
        if self.file_path and os.path.exists(self.file_path):
            os.startfile(self.file_path)
        else:
            print(f"[ERROR] File not found: {self.file_path}")
            messagebox.showwarning("Arquivo não encontrado", f"O arquivo não foi encontrado:\n{self.file_path}")

    def open_folder(self):
        print(f"[DEBUG] Attempting to open folder for: {self.file_path}")
        if self.file_path:
            folder = os.path.dirname(self.file_path)
            if os.path.exists(folder):
                os.startfile(folder)
            else:
                print(f"[ERROR] Folder not found: {folder}")
                messagebox.showwarning("Pasta não encontrada", f"A pasta não foi encontrada:\n{folder}")

    def copy_link(self):
        url = self.info.get('webpage_url') or self.info.get('url', '')
        self.app.root.clipboard_clear()
        self.app.root.clipboard_append(url)
        print(f"[DEBUG] URL copied: {url}")

    def remove_self(self):
        print(f"[DEBUG] Removing card: {self.info.get('title')}")
        self.app.remove_from_queue(self)

class EasyDLPApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EasyDLP")
        self.root.geometry("1100x700")
        
        self.apply_theme()
        self.load_icons()
        self.setup_styles()
        
        self.queue = []
        self.download_queue = queue.Queue()
        
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
        for key in ['play', 'folder', 'copy', 'trash']:
            path = os.path.join(base, f"{key}.svg")
            if os.path.exists(path):
                self.icons[key] = tksvg.SvgImage(file=path, scale=0.6)
            else:
                print(f"[WARNING] Icon not found: {path}")
                self.icons[key] = None

    def setup_styles(self):
        self.style = ttk.Style()
        is_dark = darkdetect.isDark()
        bg_odd = "#252525" if is_dark else "#f0f0f0"
        self.style.configure("Odd.TFrame", background=bg_odd)
        self.style.configure("Odd.TLabel", background=bg_odd)

    def setup_ui(self):
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Left Panel (Config)
        self.left_frame = ttk.Frame(self.root, padding=20)
        self.left_frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(self.left_frame, text="Configurações", font=("Segoe UI", 18, "bold")).pack(pady=(0, 20), anchor="w")
        
        # URL
        u_frame = ttk.Frame(self.left_frame)
        u_frame.pack(fill="x", pady=(0, 15))
        ttk.Label(u_frame, text="URL do Vídeo/Playlist:").pack(anchor="w")
        er = ttk.Frame(u_frame)
        er.pack(fill="x")
        self.url_entry = ttk.Entry(er)
        self.url_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(er, text="Colar", command=self.paste_url).pack(side="right", padx=(5, 0))

        # F&Q
        fq = ttk.Frame(self.left_frame)
        fq.pack(fill="x", pady=(0, 15))
        f_s = ttk.Frame(fq)
        f_s.pack(side="left", fill="x", expand=True)
        ttk.Label(f_s, text="Formato:").pack(anchor="w")
        self.format_var = tk.StringVar(value=FORMATS[0])
        ttk.Combobox(f_s, values=FORMATS, textvariable=self.format_var, state="readonly").pack(fill="x", padx=(0, 5))
        
        q_s = ttk.Frame(fq)
        q_s.pack(side="left", fill="x", expand=True)
        ttk.Label(q_s, text="Qualidade:").pack(anchor="w")
        self.quality_var = tk.StringVar(value=QUALITIES[0])
        ttk.Combobox(q_s, values=QUALITIES, textvariable=self.quality_var, state="readonly").pack(fill="x")

        # Codec
        ttk.Label(self.left_frame, text="Codec:").pack(anchor="w")
        self.codec_var = tk.StringVar(value=CODECS[0])
        ttk.Combobox(self.left_frame, values=CODECS, textvariable=self.codec_var, state="readonly").pack(fill="x", pady=(0, 15))
        
        # Destination
        ttk.Label(self.left_frame, text="Destino:").pack(anchor="w")
        dr = ttk.Frame(self.left_frame)
        dr.pack(fill="x", pady=(0, 15))
        self.dest_var = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads"))
        self.dest_entry = ttk.Entry(dr, textvariable=self.dest_var)
        self.dest_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(dr, text="...", width=3, command=self.browse_dest).pack(side="right", padx=(5, 0))
        
        # Post Action
        ttk.Label(self.left_frame, text="Após baixar:").pack(anchor="w")
        self.post_var = tk.StringVar(value=POST_ACTIONS[0])
        ttk.Combobox(self.left_frame, values=POST_ACTIONS, textvariable=self.post_var, state="readonly").pack(fill="x", pady=(0, 30))
        
        ttk.Button(self.left_frame, text="Adicionar à Fila", style="Accent.TButton", command=self.on_add_click).pack(fill="x")

        # Right Panel (Queue)
        self.right_frame = ttk.Frame(self.root, padding=20)
        self.right_frame.grid(row=0, column=1, sticky="nsew")
        self.right_frame.columnconfigure(0, weight=1)
        self.right_frame.rowconfigure(1, weight=1)
        
        hr = ttk.Frame(self.right_frame)
        hr.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        ttk.Label(hr, text="Fila de Downloads", font=("Segoe UI", 18, "bold")).pack(side="left")
        ttk.Button(hr, text="Limpar Concluídos", command=self.clear_finished).pack(side="right")
        
        self.scroll_frame = ScrollableFrame(self.right_frame)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")

    def paste_url(self):
        try:
            self.url_entry.delete(0, tk.END)
            self.url_entry.insert(0, self.root.clipboard_get())
        except: pass

    def browse_dest(self):
        p = filedialog.askdirectory()
        if p: self.dest_var.set(p)

    def on_add_click(self):
        u = self.url_entry.get().strip()
        if u:
            print(f"[DEBUG] Adding URL to processing: {u}")
            threading.Thread(target=self.handle_new_url, args=(u,), daemon=True).start()

    def handle_new_url(self, url):
        ydl_opts = {'quiet': True, 'extract_flat': 'in_playlist'}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if 'entries' in info:
                    self.root.after(0, lambda: self.show_playlist_popup(info))
                else:
                    self.root.after(0, lambda: self.add_single_video(info))
        except Exception as e:
            print(f"[ERROR] Metadata extraction failed: {e}")
            self.root.after(0, lambda: messagebox.showerror("Erro", str(e)))

    def show_playlist_popup(self, info):
        p = PlaylistPopup(self.root)
        if p.result == "playlist":
            for e in info['entries']: self.add_single_video(e)
        elif p.result == "single":
            self.add_single_video(info['entries'][0])

    def add_single_video(self, info, from_history=False):
        index = len(self.queue)
        style = "Odd.TFrame" if index % 2 != 0 else "TFrame"
        
        card = DownloadCard(self.scroll_frame.scrollable_window, info, self, index, style=style)
        if index % 2 != 0:
            for child in card.winfo_children():
                try: child.configure(style="Odd.TLabel")
                except: 
                    try: child.configure(background="#252525" if darkdetect.isDark() else "#f0f0f0")
                    except: pass
            card.text_frame.configure(style="Odd.TFrame")
            card.controls_frame.configure(style="Odd.TFrame")

        card.pack(fill="x", pady=0, padx=5)
        self.queue.append(card)
        
        url = info.get('webpage_url') or info.get('url')
        threading.Thread(target=self.fetch_card_details, args=(card, url, info), daemon=True).start()
        
        if not from_history:
            self.download_queue.put({
                'card': card, 'url': url,
                'format': self.format_var.get(),
                'quality': self.quality_var.get(),
                'codec': self.codec_var.get(),
                'dest': self.dest_var.get()
            })

    def fetch_card_details(self, card, url, info_input):
        vid_id = info_input.get('id')
        cache_path = os.path.join(CACHE_DIR, f"{vid_id}.jpg") if vid_id else None
        
        if cache_path and os.path.exists(cache_path):
            self.render_thumb(card, cache_path)
        
        ydl_opts = {'quiet': True, 'skip_download': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                card.info.update(info)
                self.root.after(0, lambda: card.title_label.configure(text=info.get('title', 'Sem título')))
                self.root.after(0, lambda: card.channel_label.configure(text=info.get('uploader', 'Canal desconhecido')))
                
                thumb_url = info.get('thumbnail')
                if thumb_url and cache_path and not os.path.exists(cache_path):
                    resp = requests.get(thumb_url, timeout=10)
                    with open(cache_path, 'wb') as f: f.write(resp.content)
                    self.render_thumb(card, cache_path)
        except: pass

    def render_thumb(self, card, path):
        try:
            img = Image.open(path)
            img.thumbnail((120, 68))
            photo = ImageTk.PhotoImage(img)
            self.root.after(0, lambda: self.update_card_thumb(card, photo))
        except: pass

    def update_card_thumb(self, card, photo):
        card.thumbnail_image = photo
        card.thumb_label.configure(image=photo, text="", background="#1c1c1c" if darkdetect.isDark() else "#f3f3f3")

    def clear_finished(self):
        finished = [c for c in self.queue if c.status == "finished"]
        for c in finished: self.remove_from_queue(c)

    def remove_from_queue(self, card):
        card.destroy()
        if card in self.queue: self.queue.remove(card)

    def queue_processor(self):
        while True:
            t = self.download_queue.get()
            if t is None: break
            c = t['card']
            if c.winfo_exists():
                c.status = 'downloading'
                print(f"[DEBUG] Starting download for: {c.info.get('title')}")
                self.run_download(t)
                if self.download_queue.empty(): self.root.after(0, self.on_all_finished)
            self.download_queue.task_done()

    def run_download(self, t):
        card, url, fmt, quality, codec, dest = t['card'], t['url'], t['format'], t['quality'], t['codec'], t['dest']
        ydl_opts = {
            'outtmpl': os.path.join(dest, '%(title)s.%(ext)s'), 
            'progress_hooks': [card.update_progress], 
            'noprogress': True, 'quiet': True
        }
        
        if fmt in ["mp3", "wav"]:
            ydl_opts.update({'format': 'bestaudio/best', 'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': fmt,'preferredquality': '192'}]})
        else:
            q = quality.split('|')[0].strip().replace('p', '')
            fps = "[fps>30]" if '60fps' in quality else ("[fps<=30]" if '30fps' in quality else "")
            cf = "[vcodec^=avc1]" if codec == "H.264" else ("[vcodec^=hev1]" if codec == "H.265" else ("[vcodec^=vp9]" if codec == "VP9" else ""))
            ydl_opts.update({'format': f'bestvideo{"[height<="+q+"]" if q != "Automático" else ""}{fps}{cf}+bestaudio/best', 'merge_output_format': fmt})
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Use extract_info with download=True to get the final metadata including merged file path
                final_info = ydl.extract_info(url, download=True)
                card.file_path = final_info.get('_filename') or ydl.prepare_filename(final_info)
                print(f"[DEBUG] Download finished. Captured path: {card.file_path}")
                self.root.after(0, card.show_finished_state)
        except Exception as e:
            print(f"[ERROR] Download failed: {e}")
            self.root.after(0, lambda: card.info_label.configure(text=f"Erro: {str(e)}", foreground="#f44336"))

    def on_all_finished(self):
        print("[DEBUG] Queue empty. All downloads finished.")
        toast("EasyDLP", "Todos os downloads foram concluídos!")
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
        if self.post_var.get() == "Abrir Pasta": os.startfile(self.dest_var.get())
        elif self.post_var.get() == "Desligar PC": os.system("shutdown /s /t 60")

    def load_settings(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    d = json.load(f)
                    self.format_var.set(d.get('format', FORMATS[0]))
                    self.quality_var.set(d.get('quality', QUALITIES[0]))
                    self.codec_var.set(d.get('codec', CODECS[0]))
                    self.dest_var.set(d.get('dest', self.dest_var.get()))
                    self.post_var.set(d.get('post_action', POST_ACTIONS[0]))
                    print("[DEBUG] Settings loaded.")
            except: pass
        if os.path.exists(HISTORY_PATH):
            try:
                with open(HISTORY_PATH, 'r') as f:
                    history = json.load(f)
                    print(f"[DEBUG] Loading {len(history)} items from history.")
                    for i in history: self.add_single_video(i, from_history=True)
            except: pass

    def on_closing(self):
        print("[DEBUG] App closing. Saving settings and history.")
        settings = {'format': self.format_var.get(), 'quality': self.quality_var.get(), 'codec': self.codec_var.get(), 'dest': self.dest_var.get(), 'post_action': self.post_var.get()}
        try:
            with open(CONFIG_PATH, 'w') as f: json.dump(settings, f)
            history = []
            for c in self.queue:
                if c.winfo_exists():
                    item = c.info.copy()
                    item['status'] = c.status
                    item['file_path'] = c.file_path
                    history.append(item)
            with open(HISTORY_PATH, 'w') as f: json.dump(history, f)
        except: pass
        self.root.destroy()

class PlaylistPopup(tk.Toplevel):
    def __init__(self, parent, title="Playlist Detectada"):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x180")
        self.resizable(False, False)
        self.result = None
        self.label = ttk.Label(self, text="Este link contém uma playlist.\nO que deseja fazer?", font=("Segoe UI", 11), justify="center")
        self.label.pack(pady=20)
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="Playlist Completa", style="Accent.TButton", command=self.on_playlist).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="Apenas um Vídeo", command=self.on_single).pack(side="left", padx=10)
        ttk.Button(btn_frame, text="Cancelar", command=self.on_cancel).pack(side="left", padx=10)
        self.transient(parent); self.grab_set(); self.protocol("WM_DELETE_WINDOW", self.on_cancel); self.wait_window()
    def on_playlist(self): self.result = "playlist"; self.destroy()
    def on_single(self): self.result = "single"; self.destroy()
    def on_cancel(self): self.result = "cancel"; self.destroy()

if __name__ == "__main__":
    root = tk.Tk(); app = EasyDLPApp(root); root.mainloop()
