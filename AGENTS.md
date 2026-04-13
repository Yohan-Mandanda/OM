## Cursor Cloud specific instructions

### Overview
OM E-Ticket Downloader — a Playwright-based browser automation tool that logs into the OM football club ticketing site (`billetterie.om.fr`) and downloads e-tickets. It has two interfaces: a CLI script (`om_eticket_downloader.py`) and an optional Streamlit web UI (`streamlit_app.py`).

### Services

| Service | How to run |
|---|---|
| **CLI** | `source .venv/bin/activate && python om_eticket_downloader.py --accounts-file <file> --match "<name>" --output-dir downloads --headless` |
| **Streamlit UI** | `source .venv/bin/activate && streamlit run streamlit_app.py --server.headless true --server.port 8501` |

### Important caveats
- **No test suite exists** in this repository. There are no unit tests, integration tests, or linting configured. Validation is done by running the scripts directly.
- **End-to-end testing requires real OM ticketing credentials** and network access to `https://billetterie.om.fr`. Without valid credentials, the CLI will fail at the login step (expected behavior).
- **Playwright Chromium must be installed** after pip dependencies: `python -m playwright install --with-deps chromium`. This downloads ~110 MB of browser binaries.
- The virtual environment lives at `.venv/`. Always activate it before running commands.
- Streamlit runs on port 8501 by default. Pass `--server.headless true` to avoid the "email prompt" on first launch.
- For standard setup steps, see `README.md`.
