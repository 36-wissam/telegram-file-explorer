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

## Roadmap

- [x] **Stage 1 — Project Foundation**: Project structure, configuration, logging, and basic PySide6 window.
- [ ] **Stage 2 — Telegram API Configuration**: MTProto client setup and secure session storage.
- [ ] **Stage 3 — Telegram Authentication**: Login UI, OTP verification, 2FA, session persistence.
- [ ] **Stage 4 — Telegram Chat Discovery**: List dialogs, channels, groups, and navigation.
- [ ] **Stage 5 — Media/File Indexing**: Message scanning and metadata extraction.
- [ ] **Stage 6 — Database Layer**: SQLAlchemy models and resumable indexing state.
- [ ] **Stage 7 — File Explorer UI**: Modern file manager interface with grid/list views.
- [ ] **Stage 8 — Search Engine**: SQLite FTS5 full-text search with multi-faceted filtering.
- [ ] **Stage 9 — File Preview**: Cached thumbnails, metadata previews, image inspection.
- [ ] **Stage 10 — File Download Manager**: Asynchronous downloader with progress and speed tracking.
- [ ] **Stage 11 — Advanced Filtering**: Size range, date range, type, extension filters.
- [ ] **Stage 12 — Indexing Controls**: Pause, resume, re-index, per-chat indexing controls.
- [ ] **Stage 13 — Performance & Reliability**: Query optimization, rate limit handling, connection recovery.
- [ ] **Stage 14 — Security Review**: Credential hardening and privacy auditing.
- [ ] **Stage 15 — Final Polish**: UI polish, shortcuts, icons, and final packaging.

---

## License

MIT License.
