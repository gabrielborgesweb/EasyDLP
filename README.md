![EasyDLP app logo](logo.png)

**EasyDLP** é um baixador de vídeos e áudios moderno, rápido e totalmente gratuito, construído em Python.

### 💡 O Propósito

Cansado de ferramentas de download de vídeo que parecem todas iguais, mas que escondem funções básicas atrás de um **paywall** chato ou limitam a velocidade de download? O EasyDLP foi criado para resolver essa dor: uma interface limpa, sem anúncios e sem cobranças, aproveitando todo o poder do `yt-dlp`.

---

## ✨ Funcionalidades

- 🎥 **Qualidade Máxima:** Suporta resoluções de até 4K (2160p) a 60fps.
- 🎵 **Conversão de Áudio:** Extração direta para MP3 e WAV.
- 📂 **Gestão de Fila:** Adicione múltiplos links e deixe o app trabalhar em segundo plano.
- 🎞️ **Suporte a Playlists:** Detecta automaticamente playlists e permite escolher entre baixar o vídeo atual ou a lista completa.
- 🎨 **Interface Moderna:** Tema escuro/claro automático baseado no sistema (usando `sv-ttk`).
- 🔔 **Notificações:** Alertas nativos do Windows ao finalizar os downloads.
- 💾 **Persistência:** Salva automaticamente seu histórico de downloads e preferências de pasta/formato.

---

## 🛠️ Requisitos do Sistema

- **Python 3.10+** (para rodar via script)
- **FFmpeg:** Essencial para unir trilhas de áudio/vídeo em alta qualidade e para conversão de MP3.
  - _Certifique-se de que o `ffmpeg` esteja no seu PATH do sistema._

---

## 🚀 Como Executar (Desenvolvimento)

1. Clone o repositório:

   ```bash
   git clone https://github.com/seu-usuario/EasyDLP.git
   cd EasyDLP
   ```

2. Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

3. Execute o app:
   ```bash
   python main.py
   ```

---

## 📦 Como Gerar o Executável (.exe)

Se você deseja distribuir o app como um arquivo único para Windows, use o PyInstaller com o comando abaixo para garantir que todos os ícones e temas sejam incluídos corretamente:

```powershell
pyinstaller --noconfirm --onefile --windowed --icon "icon.ico" --add-data "icon.ico;." --add-data "*.svg;." --collect-all sv_ttk --collect-all tksvg --name EasyDLP main.py
```

O executável será gerado na pasta `dist/`.

---

## 📝 Notas de Uso

- O app cria uma pasta em `%APPDATA%/EasyDLP` para armazenar suas configurações (`userpref.json`), histórico e cache de miniaturas.
- Se o `ffmpeg` não for detectado, o app exibirá um aviso, mas ainda permitirá downloads básicos em qualidades limitadas (onde o merge não é necessário).

---

Criado com ❤️ por [Gabriel Borges](https://github.com/gabrielborgesweb)

Gerado através do [Gemini CLI](https://geminicli.com) (`gemini-3-flash-preview`)
