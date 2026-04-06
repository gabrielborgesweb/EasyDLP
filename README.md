# EasyDLP

Um baixador de vídeos simples usando Python, Tkinter e yt-dlp.

## Requisitos

- Python 3.x
- FFmpeg (necessário para conversão de áudio e junção de vídeo/áudio de alta qualidade)

## Como rodar

1. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

2. Execute o script:
   ```bash
   python main.py
   ```

## Como criar o executável (EasyDLP.exe)

Para criar o arquivo `.exe` mencionado:

1. Instale o PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. Gere o executável:
   ```bash
   pyinstaller --noconsole --onefile --name EasyDLP main.py
   ```

O arquivo `EasyDLP.exe` será criado na pasta `dist/`. Ao executá-lo, o arquivo `userpref.ini` será criado automaticamente na mesma pasta ao fechar o app.

---
**Nota:** Certifique-se de que o `ffmpeg` esteja no seu PATH do sistema para que as conversões de formato e downloads em alta qualidade funcionem corretamente.
