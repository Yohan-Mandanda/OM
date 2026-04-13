## Cursor Cloud specific instructions

This repository contains multiple projects across different branches.

### Live Targets Dashboard (branch: `cursor/js-live-target-dashboard-9781`)

**Overview:** A real-time dashboard (Node.js + Express + Socket.IO) for tracking live ticket targets with a dark trading-style UI. Vanilla JS frontend, no build step.

**Services:**

| Service | How to run | Port |
|---|---|---|
| **Dev server** (auto-reload) | `npm run dev` | 3000 |
| **Production server** | `npm start` | 3000 |

**Caveats:**
- **No test suite or linter** is configured. Validation is done by running the server and testing via browser/API.
- `npm run dev` uses `node --watch server.js` for auto-reload during development.
- State is in-memory only — restarting the server resets all rows/cells.
- The REST API is at `/api/state`, `/api/rows`, `/api/cells/:rowId/:section/:index`. See `README.md` for details.
- Socket.IO broadcasts state changes in real time to all connected browser clients.

### OM E-Ticket Downloader (branch: `main`)

**Overview:** A Playwright-based browser automation tool that logs into the OM football club ticketing site (`billetterie.om.fr`) and downloads e-tickets. Two interfaces: CLI (`om_eticket_downloader.py`) and Streamlit UI (`streamlit_app.py`).

**Services:**

| Service | How to run |
|---|---|
| **CLI** | `source .venv/bin/activate && python om_eticket_downloader.py --accounts-file <file> --match "<name>" --output-dir downloads --headless` |
| **Streamlit UI** | `source .venv/bin/activate && streamlit run streamlit_app.py --server.headless true --server.port 8501` |

**Caveats:**
- **No test suite exists.** Validation is done by running the scripts directly.
- **End-to-end testing requires real OM ticketing credentials** and network access to `https://billetterie.om.fr`.
- **Playwright Chromium must be installed** after pip deps: `python -m playwright install --with-deps chromium`.
- The Python virtual environment lives at `.venv/`. Always activate before running.
- Streamlit runs on port 8501 by default. Pass `--server.headless true` to avoid the email prompt.
