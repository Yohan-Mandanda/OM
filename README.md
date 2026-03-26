# OM E-Ticket Downloader

Automation tool to log into OM billetterie accounts and download e-tickets for a selected match.

## Ticketing Sales Analytics Dashboard

The Streamlit app now includes a second module focused on event analytics for ticketing businesses.

### What it does

- Upload sales data (CSV/XLSX) or use built-in demo data.
- Track key KPIs: revenue, profit, ROI, tickets sold, fill rate.
- Analyze factor impact with trend charts and correlation matrix.
- Train an ROI prediction model from historical event data.
- Simulate a new event scenario and predict ROI.

### Recommended columns

Use canonical names when possible:

- `event_date`, `event_name`, `city`, `channel`
- `tickets_sold`, `capacity`, `avg_ticket_price`
- `gross_revenue`, `refunds_amount`
- `marketing_spend`, `venue_cost`, `artist_fee`, `operational_cost`, `total_cost`
- `profit`, `roi_pct`
- optional external factors: `social_mentions`, `weather_score`

The app also auto-maps common aliases (e.g. `revenue`, `sales`, `ticket_price`, `ca`, etc.).

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

Then choose the module in the left sidebar:

1. **Sales analytics dashboard** (metrics + ROI prediction)
2. **E-ticket downloader** (existing automation flow)

## Notes / limitations

- If cookie banner appears, the script tries to accept it automatically.
- If captcha appears, run in non-headless mode and solve manually in the opened browser.
- Selectors can change on OM website; if they do, update the script selectors.
