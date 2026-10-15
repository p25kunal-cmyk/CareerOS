# 🚀 CareerOS

**Personal AI-Powered Job Search and Resume Management System**

Built for MBA students — manage resumes, discover jobs, match skills, and optimise applications.
Local-first, privacy-focused, and works without AI.

---

## Quick Start

```bash
# 1. Clone and enter the project
cd CarrerOS

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and configure environment
cp .env.example .env
# Edit .env to set AI credentials (optional)

# 5. Launch the dashboard
streamlit run src/app.py
```

The database is created automatically on first launch.

## Project Structure

```
CarrerOS/
├── config/                  # Configuration management
│   └── settings.py          # Env-based settings loader
├── src/
│   ├── app.py               # Streamlit entry point
│   ├── database/            # SQLite connection + migrations
│   ├── resume/              # Parse, edit, version, export (Phase 2)
│   ├── jobs/                # Discovery + deduplication (Phase 3–4)
│   ├── matching/            # Keyword + semantic scoring (Phase 5)
│   ├── ai/                  # Provider abstraction + cache (Phase 6)
│   ├── tracker/             # Application tracking (Phase 3)
│   ├── automation/          # Scheduled tasks (Phase 8)
│   ├── api/                 # Local REST API (Phase 7)
│   ├── ui/                  # Streamlit pages and components
│   └── utils/               # Logging + helpers
├── tests/                   # pytest test suite
├── data/                    # Local data (gitignored)
│   ├── uploads/             # Uploaded resumes
│   ├── exports/             # Generated documents
│   └── backups/             # Database backups
├── requirements.txt
├── .env.example
└── .gitignore
```

## Running Tests

```bash
pytest tests/ -v
```

## AI Configuration (Optional)

All features work without AI. To enable AI-powered resume suggestions:

1. Set `CAREEROS_AI_PROVIDER` to `openai` or `google` in `.env`
2. Set `CAREEROS_AI_API_KEY` to your API key
3. Optionally adjust `CAREEROS_AI_MODEL` and `CAREEROS_AI_MONTHLY_BUDGET`

## Backup & Restore

- **Backup:** Use the Settings page or copy `data/careeros.db`
- **Restore:** Replace `data/careeros.db` with a backup copy

## Known Limitations

- Phase 1 release — resume engine, job discovery, and matching are in progress
- IIM Nagpur template requires a sample resume for accurate formatting
- Job portal integrations depend on each platform's access policies

## License

Private project — not for redistribution.
