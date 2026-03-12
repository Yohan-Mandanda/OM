# OM E-Ticket Downloader

Automation tool to log into OM billetterie accounts and download e-tickets for a selected match.

## What is included

- `om_eticket_downloader.py`: CLI automation script (Playwright, multi-account support).
- `streamlit_app.py`: optional web interface to run the same automation.
- `accounts_example.csv`: sample spreadsheet format.

## Requirements

- Python 3.10+
- Chromium for Playwright

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Account file format

Use CSV or XLSX with at least:

- one email column: `email` (or similar, e.g. `adresse email`)
- one password column: `mot de passe` / `password`

Example:

```csv
email,mot de passe
user1@example.com,password1
user2@example.com,password2
```

## Run from terminal (CLI)

```bash
python om_eticket_downloader.py \
  --accounts-file accounts_example.csv \
  --match "Lille" \
  --output-dir downloads
```

Useful options:

- `--headless` (not recommended if captcha appears)
- `--login-wait-seconds 180`
- `--slow-mo-ms 150`

Downloads are saved under:

`downloads/<email>/`

## Run with interface (Streamlit)

```bash
streamlit run streamlit_app.py
```

Then:

1. Upload CSV/XLSX file
2. Enter match name (e.g. `Auxerre`, `Lille`, `Metz`)
3. Click **Start download**

## Notes / limitations

- If cookie banner appears, the script tries to accept it automatically.
- If captcha appears, run in non-headless mode and solve manually in the opened browser.
- Selectors can change on OM website; if they do, update the script selectors.
