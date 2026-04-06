import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import yt_dlp
import os
import sys
import threading
import configparser
import winsound
import darkdetect
import sv_ttk
from win11toast import toast

# Constants
FORMATS = ["mp4", "mp3", "webm", "wav"]
QUALITIES = ["Automático", "2160p", "1440p", "1080p", "720p", "480p"]
POST_ACTIONS = ["Nada", "Abrir Pasta", "Abrir Arquivo"]


def get_base_path():
    """Returns the base path for userpref.ini, compatible with PyInstaller."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(get_base_path(), "userpref.ini")


class EasyDLPApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EasyDLP")
        self.root.geometry("520x420")
        self.root.resizable(False, False)

        # Variables
        self.url_var = tk.StringVar()
        self.format_var = tk.StringVar(value=FORMATS[0])
        self.quality_var = tk.StringVar(value=QUALITIES[0])  # Default Automático
        self.save_path_var = tk.StringVar(
            value=os.path.join(os.path.expanduser("~"), "Downloads")
        )
        self.post_action_var = tk.StringVar(value=POST_ACTIONS[0])

        self.load_prefs()
        self.setup_ui()
        self.apply_theme()

        # Handle app close to save preferences
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def apply_theme(self):
        """Applies theme based on system settings."""
        theme = darkdetect.theme()
        if theme:
            sv_ttk.set_theme(theme.lower())
        else:
            sv_ttk.set_theme("light")

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # URL
        ttk.Label(main_frame, text="URL do Vídeo (obrigatório):").pack(
            anchor=tk.W, pady=(0, 5)
        )
        self.url_entry = ttk.Entry(main_frame, textvariable=self.url_var, width=60)
        self.url_entry.pack(fill=tk.X, pady=(0, 15))

        # Format and Quality (side by side)
        options_frame = ttk.Frame(main_frame)
        options_frame.pack(fill=tk.X, pady=(0, 15))

        format_subframe = ttk.Frame(options_frame)
        format_subframe.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(format_subframe, text="Formato:").pack(anchor=tk.W)
        self.format_menu = ttk.Combobox(
            format_subframe,
            textvariable=self.format_var,
            values=FORMATS,
            state="readonly",
        )
        self.format_menu.pack(fill=tk.X, padx=(0, 10))

        quality_subframe = ttk.Frame(options_frame)
        quality_subframe.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(quality_subframe, text="Qualidade:").pack(anchor=tk.W)
        self.quality_menu = ttk.Combobox(
            quality_subframe,
            textvariable=self.quality_var,
            values=QUALITIES,
            state="readonly",
        )
        self.quality_menu.pack(fill=tk.X)

        # Save Path
        ttk.Label(main_frame, text="Salvar em:").pack(anchor=tk.W, pady=(0, 5))
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill=tk.X, pady=(0, 15))
        ttk.Entry(path_frame, textvariable=self.save_path_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Carregar ícone (com fallback caso o arquivo não exista)
        self.save_icon = None
        icon_path = os.path.join(get_base_path(), "save.png")
        if os.path.exists(icon_path):
            try:
                self.save_icon = tk.PhotoImage(file=icon_path)
                ttk.Button(path_frame, image=self.save_icon, command=self.browse_path).pack(side=tk.RIGHT, padx=(5, 0))
            except Exception:
                ttk.Button(path_frame, text="Procurar", command=self.browse_path).pack(side=tk.RIGHT, padx=(5, 0))
        else:
            ttk.Button(path_frame, text="Procurar", command=self.browse_path).pack(side=tk.RIGHT, padx=(5, 0))

        # Post Action
        ttk.Label(main_frame, text="Após baixar:").pack(anchor=tk.W, pady=(0, 5))
        self.post_action_menu = ttk.Combobox(
            main_frame,
            textvariable=self.post_action_var,
            values=POST_ACTIONS,
            state="readonly",
        )
        self.post_action_menu.pack(fill=tk.X, pady=(0, 20))

        # Progress / Status
        self.status_label = ttk.Label(main_frame, text="Pronto", foreground="gray")
        self.status_label.pack(pady=(0, 10))

        # Download Button
        self.download_btn = ttk.Button(
            main_frame,
            text="Baixar Agora",
            style="Accent.TButton",
            command=self.start_download_thread,
        )
        self.download_btn.pack(pady=5)

    def browse_path(self):
        directory = filedialog.askdirectory(initialdir=self.save_path_var.get())
        if directory:
            self.save_path_var.set(directory)

    def load_prefs(self):
        config = configparser.ConfigParser()
        if os.path.exists(CONFIG_PATH):
            try:
                config.read(CONFIG_PATH)
                if "Settings" in config:
                    self.format_var.set(
                        config.get("Settings", "format", fallback=FORMATS[0])
                    )
                    self.quality_var.set(
                        config.get("Settings", "quality", fallback=QUALITIES[0])
                    )
                    self.save_path_var.set(
                        config.get(
                            "Settings", "save_path", fallback=self.save_path_var.get()
                        )
                    )
                    self.post_action_var.set(
                        config.get("Settings", "post_action", fallback=POST_ACTIONS[0])
                    )
            except Exception as e:
                print(f"Erro ao carregar preferências: {e}")

    def save_prefs(self):
        config = configparser.ConfigParser()
        config["Settings"] = {
            "format": self.format_var.get(),
            "quality": self.quality_var.get(),
            "save_path": self.save_path_var.get(),
            "post_action": self.post_action_var.get(),
        }
        try:
            with open(CONFIG_PATH, "w") as configfile:
                config.write(configfile)
        except Exception as e:
            print(f"Erro ao salvar preferências: {e}")

    def on_closing(self):
        self.save_prefs()
        self.root.destroy()

    def update_status(self, text, color=None):
        if color:
            self.status_label.config(text=text, foreground=color)
        else:
            self.status_label.config(text=text)

    def start_download_thread(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showwarning(
                "Campo Obrigatório", "Por favor, insira a URL do vídeo."
            )
            return

        self.download_btn.config(state="disabled")
        self.update_status("Iniciando download...", "blue")

        thread = threading.Thread(target=self.download_media, args=(url,), daemon=True)
        thread.start()

    def download_media(self, url):
        fmt = self.format_var.get()
        quality_sel = self.quality_var.get()
        save_path = self.save_path_var.get()

        ydl_opts = {
            "outtmpl": os.path.join(save_path, "%(title)s.%(ext)s"),
            "logger": MyLogger(self),
            "progress_hooks": [self.progress_hook],
        }

        # Format Logic
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
            # Video format
            if quality_sel == "Automático":
                ydl_opts.update(
                    {
                        "format": f"bestvideo[ext={fmt}]+bestaudio[ext=m4a]/best",
                        "merge_output_format": fmt,
                    }
                )
            else:
                quality_str = quality_sel.replace("p", "")
                ydl_opts.update(
                    {
                        "format": f"bestvideo[height<={quality_str}][ext={fmt}]+bestaudio[ext=m4a]/best[height<={quality_str}]",
                        "merge_output_format": fmt,
                    }
                )

            # Special case for webm
            if fmt == "webm":
                if quality_sel == "Automático":
                    ydl_opts.update(
                        {"format": "bestvideo[ext=webm]+bestaudio[ext=webm]/best"}
                    )
                else:
                    quality_str = quality_sel.replace("p", "")
                    ydl_opts.update(
                        {
                            "format": f"bestvideo[height<={quality_str}][ext=webm]+bestaudio[ext=webm]/best[height<={quality_str}]"
                        }
                    )

        last_file = None

        def post_download_hook(d):
            nonlocal last_file
            if d["status"] == "finished":
                last_file = d.get("info_dict").get("_filename")

        ydl_opts["progress_hooks"].append(post_download_hook)

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                # If extraction was direct or last_file not set by hook yet
                if not last_file:
                    last_file = ydl.prepare_filename(info)

            # Success actions
            self.root.after(0, self.handle_success, last_file)

        except Exception as e:
            self.root.after(0, lambda: self.update_status("Erro no download", "red"))
            self.root.after(
                0, lambda: messagebox.showerror("Erro", f"Ocorreu um erro: {str(e)}")
            )
        finally:
            self.root.after(0, lambda: self.download_btn.config(state="normal"))

    def handle_success(self, file_path):
        self.update_status("Concluído com sucesso!", "green")

        # Play sound
        winsound.MessageBeep(winsound.MB_ICONASTERISK)

        # System notification if out of focus
        # In Tkinter, root.focus_displayof() or checking if root is active
        if not self.root.focus_displayof():
            toast("EasyDLP", f"Download concluído:\n{os.path.basename(file_path)}")

        # Post action logic
        action = self.post_action_var.get()
        if action == "Abrir Pasta":
            os.startfile(os.path.dirname(file_path))
        elif action == "Abrir Arquivo" and os.path.exists(file_path):
            os.startfile(file_path)

    def progress_hook(self, d):
        if d["status"] == "downloading":
            p = d.get("_percent_str", "0%")
            self.root.after(0, lambda: self.update_status(f"Baixando: {p}"))
        elif d["status"] == "finished":
            self.root.after(0, lambda: self.update_status("Processando...", "orange"))


class MyLogger:
    def __init__(self, app):
        self.app = app

    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        print(msg)


if __name__ == "__main__":
    root = tk.Tk()
    # Apply initial system theme
    app = EasyDLPApp(root)
    root.mainloop()
