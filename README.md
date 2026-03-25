# OM E-Ticket Downloader

Automation tool to log into OM billetterie accounts and download e-tickets for a selected match.

## What is included

- `om_eticket_downloader.py`: CLI automation script (Playwright, multi-account support).
- `streamlit_app.py`: optional web interface to run the same automation.
- `accounts_example.csv`: sample spreadsheet format.
- `chatgpt_invoice_downloader.py`: ChatGPT billing portal invoice downloader by month.
- `download`: terminal command wrapper for ChatGPT invoice download flow.

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

## ChatGPT invoice downloader

This automation assumes you are already logged in (or will log in once in the persistent browser profile).

### Terminal command

From the repository root:

```bash
./download invoice chat gbt "March"
```

By default, files are saved to:

`downloads/chatgpt-invoices/`

### Optional one-time setup (run `download` without `./`)

Add this repository to your PATH:

```bash
export PATH="/workspace:$PATH"
```

Then run:

```bash
download invoice chat gbt "March"
```

### Optional flags

```bash
download invoice chat gbt "March" --headless
download invoice chat gbt "March" --output-dir /tmp/invoices
download invoice chat gbt "March" --user-data-dir /tmp/chatgpt-profile
download invoice chat gbt "March" --captcha-wait-seconds 300
download invoice chat gbt "March" --auto-login-start
```

Notes:

- `--user-data-dir` keeps the browser session state (cookies/login) between runs.
- Default mode expects a real pre-authenticated session in your profile and avoids scripted login start.
- Use `--auto-login-start` only if you explicitly want the script to run the login-popup click steps.
- If captcha appears, solve it manually in the opened browser window.
- In captcha scenarios, headed mode is recommended (avoid `--headless`).
- If ChatGPT updates UI selectors, adjust selectors inside `chatgpt_invoice_downloader.py`.

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
