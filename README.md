# Telegram File Explorer

A modern desktop application built with **Python**, **Telethon**, and **PySide6** that enables users to authenticate directly with their own Telegram account via MTProto API to browse, index, search, preview, and download files and media across all accessible chats, groups, and channels.

---

## Key Features

- **MTProto User Authentication**: Direct user session support (Phone, SMS/App OTP, 2FA password). No bot token limitations.
- **Chat & Channel Discovery**: Browse dialogues, groups, and channels with profile pictures and metadata.
- **Resumable Media Indexer**: Scan messages in background to index documents, videos, audio, images, archives without auto-downloading large files.
- **SQLite & SQLAlchemy Engine**: Structured local storage with FTS5 (Full-Text Search) for blazing-fast lookups.
- **Modern Desktop File Manager UI**: PySide6 dark-themed interface with file categories, metadata views, and thumbnail previews.
- **Asynchronous Download Manager**: Multi-threaded downloads with pause/resume, speed meters, and progress reporting.
- **Privacy & Security First**: Session files and credentials remain strictly local and gitignored.

---

## Tech Stack

- **GUI**: PySide6 (Qt for Python)
- **Telegram Client**: Telethon (MTProto API)
- **Database**: SQLite with SQLAlchemy ORM & FTS5 full-text indexing
- **Settings**: Pydantic / python-dotenv
- **Imaging**: Pillow

---

## Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/36-wissam/telegram-file-explorer.git
   cd telegram-file-explorer
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # Linux/macOS:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Copy `.env.example` to `.env` and fill in your Telegram API credentials obtained from [my.telegram.org](https://my.telegram.org):
   ```env
   TELEGRAM_API_ID=your_api_id
   TELEGRAM_API_HASH=your_api_hash
   ```

5. **Run the Application**:
   ```bash
   python main.py
   ```

---

## Project Structure

```
telegram-file-explorer/
├── app/
│   ├── core/          # Configuration, logging, event bus
│   ├── database/      # SQLAlchemy models & migrations
│   ├── telegram/      # Telethon client wrapper & background workers
│   ├── services/      # Indexing, search engine, download manager
│   └── ui/            # PySide6 widgets, dialogs, styles
├── data/              # SQLite database and local cache (ignored)
├── logs/              # Application logs (ignored)
├── main.py            # Application entry point
├── pyproject.toml     # Project metadata
├── requirements.txt   # Python dependencies
└── README.md
```

---

## Security & Local Data Privacy

The application is engineered with a strict **Local-First, Zero-Cloud** security architecture:

1. **Strict Local Isolation**: All API credentials (`API_ID`, `API_HASH`), phone numbers, MTProto `.session` binary files, and SQLite databases remain 100% on the user's personal machine in the gitignored `data/` directory. No telemetry, analytics, or external cloud servers are ever used.
2. **Ephemeral In-Memory 2FA Handling**: Cloud passwords used during Two-Factor Authentication (2FA) SRP challenge are processed transiently in volatile RAM and immediately discarded. Passwords are never stored on disk, in SQLite, or in logs.
3. **Log Sanitization & Masking**: The custom `SensitiveDataFormatter` automatically redacts phone numbers, 32-character hexadecimal API hashes, and credential keywords in all console streams and rotating log files.
4. **File Permission Hardening**: Local credential stores and Telethon session files are protected with restricted read/write permissions (`0o600`).
5. **Complete Data Eradication**: Full session logout and data wipe utilities enable immediate eradication of all local session tokens, SQLite databases, and cached media.

---

## License

MIT License.

