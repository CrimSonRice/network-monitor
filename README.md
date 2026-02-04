# Network Monitor

Live ping dashboard for monitoring many IPs or hostnames. Pagination and filters keep the display readable for 300+ targets.

## Project structure

```
network-monitor/
├── core/
├── api/
├── services/
├── models/
├── utils/
├── ui/              # TUI: ui/monitor_tui.py
├── tests/
├── main.py
├── config.py
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

## Setup

### 1. Venv and install

```bash
cd network-monitor
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Environment (optional)

```bash
# Windows
copy .env.example .env
# Linux/macOS
cp .env.example .env
```

Edit `.env` if you need to change defaults.

## Run

### TUI (live ping dashboard)

```bash
# Prompt for IPs
python -m ui.monitor_tui

# Or pass targets (comma-separated or multiple args)
python -m ui.monitor_tui 8.8.8.8 1.1.1.1
python -m ui.monitor_tui 8.8.8.8,1.1.1.1,google.com

# Options
python -m ui.monitor_tui 8.8.8.8 -i 2 -w 60 -r 0.5
python -m ui.monitor_tui ... -f 8.8          # filter by substring
python -m ui.monitor_tui ... -s up           # reachable only
python -m ui.monitor_tui ... -s down         # unreachable only
python -m ui.monitor_tui ... --page-size 30  # 30 per page (for 300+ IPs)
```

**Filters (Windows, while running):** Type to filter by text; **Esc** clears. **u** = UP only, **d** = DOWN only, **a** = all.

**Pagination:** Header shows "Page X of Y" and "Targets A–B of N". **←** = previous page, **→** = next page, **Home** = first page, **End** = last page. Use `--page-size N` or env `PAGE_SIZE` to set targets per page (default 100).

Optional env: `PING_INTERVAL`, `WINDOW_SIZE`, `REFRESH_RATE`, `PAGE_SIZE`. Press **Ctrl+C** to exit.

### API (optional)

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://localhost:8000  
- Docs: http://localhost:8000/docs  

### Tests

```bash
pytest tests/ -v
```

## License

Use as needed for your project.
