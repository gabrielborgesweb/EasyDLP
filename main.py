import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image
import yt_dlp
import os
import sys
import threading
import queue
import json
import time
import winsound
from win11toast import toast
import webbrowser

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

class PlaylistPopup(ctk.CTkToplevel):
    def __init__(self, parent, title="Playlist Detectada"):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x200")
        self.result = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.label = ctk.CTkLabel(self, text="Este link contém uma playlist.\nO que deseja fazer?", font=("Arial", 16))
        self.label.pack(pady=20)
        
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)
        
        self.btn_playlist = ctk.CTkButton(btn_frame, text="Playlist Completa", fg_color="#1f538d", command=self.on_playlist)
        self.btn_playlist.pack(side="left", padx=10)
        
        self.btn_single = ctk.CTkButton(btn_frame, text="Apenas um Vídeo", command=self.on_single)
        self.btn_single.pack(side="left", padx=10)
        
        self.btn_cancel = ctk.CTkButton(btn_frame, text="Cancelar", fg_color="#a12c2c", hover_color="#802323", command=self.on_cancel)
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

class DownloadCard(ctk.CTkFrame):
    def __init__(self, master, info, app, **kwargs):
        super().__init__(master, **kwargs)
        self.info = info
        self.app = app
        self.status = "waiting" # waiting, downloading, finished, error
        self.file_path = None
        
        self.grid_columnconfigure(1, weight=1)
        
        # Thumbnail
        self.thumb_label = ctk.CTkLabel(self, text="", width=120, height=68, fg_color="gray30")
        self.thumb_label.grid(row=0, column=0, rowspan=2, padx=10, pady=10)
        
        # Title
        self.title_label = ctk.CTkLabel(self, text=info.get('title', 'Extraindo...'), font=("Arial", 12, "bold"), anchor="w")
        self.title_label.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(10, 0))
        
        # Info (Size, Speed)
        self.info_label = ctk.CTkLabel(self, text="Aguardando...", font=("Arial", 10), anchor="w")
        self.info_label.grid(row=1, column=1, sticky="ew", padx=(0, 10))
        
        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 5))
        self.progress_bar.set(0)
        
        # Controls Frame
        self.controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.controls_frame.grid(row=0, column=2, rowspan=3, padx=10)
        
        self.btn_open = ctk.CTkButton(self.controls_frame, text="Abrir", width=60, height=24, state="disabled", command=self.open_file)
        self.btn_open.pack(pady=2)
        
        self.btn_folder = ctk.CTkButton(self.controls_frame, text="Pasta", width=60, height=24, state="disabled", command=self.open_folder)
        self.btn_folder.pack(pady=2)
        
        self.btn_copy = ctk.CTkButton(self.controls_frame, text="Link", width=60, height=24, command=self.copy_link)
        self.btn_copy.pack(pady=2)
        
        self.btn_delete = ctk.CTkButton(self.controls_frame, text="X", width=24, height=24, fg_color="#a12c2c", hover_color="#802323", command=self.remove_self)
        self.btn_delete.pack(pady=2)

    def update_progress(self, d):
        if d['status'] == 'downloading':
            p = d.get('downloaded_bytes', 0) / d.get('total_bytes', 1) if d.get('total_bytes') else 0
            self.progress_bar.set(p)
            percent = d.get('_percent_str', '0%')
            speed = d.get('_speed_str', '0MB/s')
            self.info_label.configure(text=f"{percent} - {speed}")
        elif d['status'] == 'finished':
            self.progress_bar.set(1)
            self.info_label.configure(text="Concluído", text_color="green")
            self.btn_open.configure(state="normal")
            self.btn_folder.configure(state="normal")
            self.status = "finished"
            self.file_path = d.get('info_dict', {}).get('_filename')

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
        self.app.root.clipboard_append(self.info.get('webpage_url', ''))

    def remove_self(self):
        self.app.remove_from_queue(self)

class EasyDLPApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EasyDLP - Gerenciador de Downloads")
        self.root.geometry("1000x600")
        ctk.set_appearance_mode("System")
        
        self.queue = []
        self.download_queue = queue.Queue()
        self.is_processing = False
        
        self.setup_ui()
        self.load_settings()
        
        # Start queue processor
        threading.Thread(target=self.queue_processor, daemon=True).start()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        self.root.grid_columnconfigure(0, weight=0) # Config panel
        self.root.grid_columnconfigure(1, weight=1) # Queue panel
        self.root.grid_rowconfigure(0, weight=1)

        # --- Left Panel (Config) ---
        self.config_frame = ctk.CTkFrame(self.root, width=350, corner_radius=0)
        self.config_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        
        ctk.CTkLabel(self.config_frame, text="Configurações", font=("Arial", 20, "bold")).pack(pady=20, padx=20)
        
        # URL
        ctk.CTkLabel(self.config_frame, text="URL do Vídeo/Playlist:").pack(anchor="w", padx=20)
        self.url_entry = ctk.CTkEntry(self.config_frame, width=310, placeholder_text="Cole o link aqui...")
        self.url_entry.pack(pady=(5, 15), padx=20)
        self.url_entry.bind("<Control-v>", lambda e: self.root.after(100, self.on_url_pasted))

        # Format & Quality
        fq_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        fq_frame.pack(fill="x", padx=20)
        
        f_sub = ctk.CTkFrame(fq_frame, fg_color="transparent")
        f_sub.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(f_sub, text="Formato:").pack(anchor="w")
        self.format_var = ctk.StringVar(value=FORMATS[0])
        self.format_menu = ctk.CTkOptionMenu(f_sub, values=FORMATS, variable=self.format_var)
        self.format_menu.pack(fill="x", padx=(0, 5))
        
        q_sub = ctk.CTkFrame(fq_frame, fg_color="transparent")
        q_sub.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(q_sub, text="Qualidade:").pack(anchor="w")
        self.quality_var = ctk.StringVar(value=QUALITIES[0])
        self.quality_menu = ctk.CTkOptionMenu(q_sub, values=QUALITIES, variable=self.quality_var)
        self.quality_menu.pack(fill="x")

        # Codec & Destination
        cd_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        cd_frame.pack(fill="x", padx=20, pady=(15, 0))
        
        c_sub = ctk.CTkFrame(cd_frame, fg_color="transparent")
        c_sub.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(c_sub, text="Codec:").pack(anchor="w")
        self.codec_var = ctk.StringVar(value=CODECS[0])
        self.codec_menu = ctk.CTkOptionMenu(c_sub, values=CODECS, variable=self.codec_var)
        self.codec_menu.pack(fill="x", padx=(0, 5))
        
        # Destination
        ctk.CTkLabel(self.config_frame, text="Destino:").pack(anchor="w", padx=20, pady=(15, 0))
        dest_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        dest_frame.pack(fill="x", padx=20)
        self.dest_var = ctk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads"))
        self.dest_entry = ctk.CTkEntry(dest_frame, textvariable=self.dest_var, width=240)
        self.dest_entry.pack(side="left", fill="x", expand=True)
        self.dest_btn = ctk.CTkButton(dest_frame, text="...", width=40, command=self.browse_dest)
        self.dest_btn.pack(side="right", padx=(5, 0))
        
        # Post Action
        ctk.CTkLabel(self.config_frame, text="Após baixar:").pack(anchor="w", padx=20, pady=(15, 0))
        self.post_action_var = ctk.StringVar(value=POST_ACTIONS[0])
        self.post_action_menu = ctk.CTkOptionMenu(self.config_frame, values=POST_ACTIONS, variable=self.post_action_var, width=310)
        self.post_action_menu.pack(padx=20, pady=(5, 20))
        
        # Add Button
        self.add_btn = ctk.CTkButton(self.config_frame, text="Adicionar à Fila", font=("Arial", 16, "bold"), height=45, command=self.on_add_click)
        self.add_btn.pack(pady=20, padx=20, fill="x")

        # --- Right Panel (Queue) ---
        self.queue_frame = ctk.CTkFrame(self.root, corner_radius=0, fg_color="transparent")
        self.queue_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.queue_frame.grid_columnconfigure(0, weight=1)
        self.queue_frame.grid_rowconfigure(1, weight=1)
        
        ctk.CTkLabel(self.queue_frame, text="Fila de Downloads", font=("Arial", 20, "bold")).grid(row=0, column=0, pady=(10, 20), sticky="w")
        
        self.scrollable_queue = ctk.CTkScrollableFrame(self.queue_frame, label_text="")
        self.scrollable_queue.grid(row=1, column=0, sticky="nsew")
        self.scrollable_queue.grid_columnconfigure(0, weight=1)

    def browse_dest(self):
        path = filedialog.askdirectory()
        if path:
            self.dest_var.set(path)

    def on_url_pasted(self):
        url = self.url_entry.get().strip()
        if url:
            threading.Thread(target=self.fetch_metadata, args=(url,), daemon=True).start()

    def fetch_metadata(self, url):
        # This could be used to pre-fill or show a preview
        pass

    def on_add_click(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Aviso", "Por favor, insira uma URL.")
            return
        
        threading.Thread(target=self.handle_new_url, args=(url,), daemon=True).start()

    def handle_new_url(self, url):
        ydl_opts = {'quiet': True, 'no_warnings': True, 'extract_flat': 'in_playlist'}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if 'entries' in info:
                    # It's a playlist
                    self.root.after(0, lambda: self.show_playlist_popup(info))
                else:
                    self.root.after(0, lambda: self.add_single_video(info))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Erro", f"Não foi possível extrair informações: {str(e)}"))

    def show_playlist_popup(self, info):
        popup = PlaylistPopup(self.root)
        if popup.result == "playlist":
            for entry in info['entries']:
                self.add_single_video(entry)
        elif popup.result == "single":
            # Find the specific video in the playlist if possible, or just the first one
            self.add_single_video(info['entries'][0])

    def add_single_video(self, info, from_history=False):
        card = DownloadCard(self.scrollable_queue, info, self)
        card.pack(fill="x", pady=5, padx=5)
        self.queue.append(card)
        
        # Async fetch thumbnail and full title if needed
        url = info.get('webpage_url') or info.get('url')
        threading.Thread(target=self.fetch_card_details, args=(card, url), daemon=True).start()

        if not from_history:
            # Prepare download task
            task = {
                'card': card,
                'url': url,
                'format': self.format_var.get(),
                'quality': self.quality_var.get(),
                'codec': self.codec_var.get(),
                'dest': self.dest_var.get()
            }
            self.download_queue.put(task)

    def fetch_card_details(self, card, url):
        ydl_opts = {'quiet': True, 'skip_download': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'Sem título')
                thumb_url = info.get('thumbnail')
                
                self.root.after(0, lambda: card.title_label.configure(text=title))
                
                if thumb_url:
                    import requests
                    from io import BytesIO
                    response = requests.get(thumb_url, timeout=10)
                    img_data = BytesIO(response.content)
                    img = Image.open(img_data)
                    # Resize while keeping aspect ratio
                    img.thumbnail((120, 68))
                    ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                    self.root.after(0, lambda: card.thumb_label.configure(image=ctk_img, text=""))
        except:
            pass

    def remove_from_queue(self, card):
        card.destroy()
        if card in self.queue:
            self.queue.remove(card)

    def queue_processor(self):
        while True:
            task = self.download_queue.get()
            if task is None: break
            
            card = task['card']
            if not card.winfo_exists():
                self.download_queue.task_done()
                continue
            
            self.is_processing = True
            card.status = "downloading"
            self.run_download(task)
            self.download_queue.task_done()
            
            # Check if all tasks done
            if self.download_queue.empty():
                self.is_processing = False
                self.root.after(0, self.on_all_finished)

    def run_download(self, task):
        card = task['card']
        url = task['url']
        fmt = task['format']
        quality = task['quality']
        codec = task['codec']
        dest = task['dest']

        ydl_opts = {
            'outtmpl': os.path.join(dest, '%(title)s.%(ext)s'),
            'progress_hooks': [card.update_progress],
            'noprogress': True,
            'quiet': True
        }

        # Format & Quality Logic
        if fmt in ["mp3", "wav"]:
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': fmt,
                    'preferredquality': '192',
                }]
            })
        else:
            # Video
            q_str = quality.split('|')[0].strip().replace('p', '')
            fps = ""
            if '60fps' in quality: fps = "[fps>30]"
            elif '30fps' in quality: fps = "[fps<=30]"
            
            codec_filter = ""
            if codec == "H.264": codec_filter = "[vcodec^=avc1]"
            elif codec == "H.265": codec_filter = "[vcodec^=hev1]"
            elif codec == "VP9": codec_filter = "[vcodec^=vp9]"

            if quality == "Automático":
                ydl_opts.update({'format': f'bestvideo{codec_filter}+bestaudio/best', 'merge_output_format': fmt})
            else:
                ydl_opts.update({
                    'format': f'bestvideo[height<={q_str}]{fps}{codec_filter}+bestaudio/best',
                    'merge_output_format': fmt
                })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            self.root.after(0, lambda: card.info_label.configure(text=f"Erro: {str(e)}", text_color="red"))

    def on_all_finished(self):
        action = self.post_action_var.get()
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
        toast("EasyDLP", "Todos os downloads foram concluídos!")
        
        if action == "Abrir Pasta":
            os.startfile(self.dest_var.get())
        elif action == "Desligar PC":
            os.system("shutdown /s /t 60")
        elif action == "Notificar":
            pass # Already notified

    def load_settings(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r') as f:
                    data = json.load(f)
                    self.format_var.set(data.get('format', FORMATS[0]))
                    self.quality_var.set(data.get('quality', QUALITIES[0]))
                    self.codec_var.set(data.get('codec', CODECS[0]))
                    self.dest_var.set(data.get('dest', self.dest_var.get()))
                    self.post_action_var.set(data.get('post_action', POST_ACTIONS[0]))
            except: pass
        
        if os.path.exists(HISTORY_PATH):
            try:
                with open(HISTORY_PATH, 'r') as f:
                    history = json.load(f)
                    for item in history:
                        self.add_single_video(item, from_history=True)
            except: pass

    def save_settings(self):
        data = {
            'format': self.format_var.get(),
            'quality': self.quality_var.get(),
            'codec': self.codec_var.get(),
            'dest': self.dest_var.get(),
            'post_action': self.post_action_var.get()
        }
        try:
            with open(CONFIG_PATH, 'w') as f:
                json.dump(data, f)
        except: pass
        
        history = [card.info for card in self.queue if card.winfo_exists()]
        try:
            with open(HISTORY_PATH, 'w') as f:
                json.dump(history, f)
        except: pass

    def on_closing(self):
        self.save_settings()
        self.root.destroy()

if __name__ == "__main__":
    root = ctk.CTk()
    app = EasyDLPApp(root)
    root.mainloop()
