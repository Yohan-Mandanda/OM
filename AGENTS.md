# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

OM E-Ticket Downloader — a Python automation tool using Playwright to bulk-download e-tickets from `billetterie.om.fr`. Two interfaces: CLI (`om_eticket_downloader.py`) and a Streamlit web UI (`streamlit_app.py`). No databases, Docker, or backend services required.

### Running the application

- **CLI**: `python om_eticket_downloader.py --accounts-file accounts_example.csv --match "Lille" --output-dir downloads --headless`
- **Streamlit UI**: `streamlit run streamlit_app.py --server.port 8501 --server.headless true`
- Standard commands are documented in `README.md`.

### Key caveats

- The venv lives at `/workspace/.venv`. Always activate it before running: `source /workspace/.venv/bin/activate`.
- Playwright Chromium must be installed separately after pip deps: `python -m playwright install --with-deps chromium`.
- End-to-end testing against the live OM ticketing site requires valid credentials and an active match with downloadable tickets. Without those, the CLI will start the browser and navigate but fail at login.
- Running in non-headless (headed) mode on a headless server requires a display server (Xvfb or similar). For CI/cloud environments, use `--headless`.
- No linter or automated test suite is configured in this repo. Validation is done by running the CLI with `--help` and verifying imports.
