# Live Targets Dashboard (JavaScript)

Modern real-time dashboard for your team to track targets, with:

- dark "trading-style" UI
- live updates for all connected users
- per-box data source: **manual** or **API-fed**
- fast filtering (search + source type)

## Stack

- Node.js + Express
- Socket.IO for real-time sync
- Vanilla JavaScript frontend (no framework)

## Install

```bash
npm install
```

## Run

```bash
npm start
```

Open: `http://localhost:3000`

For auto-reload during development:

```bash
npm run dev
```

## How to use

1. Click **+ Add Match** to create a row.
2. Fill event fields (game, match number, venue) directly inline.
3. For each category box, click **Configure**:
   - **Manual**: type value directly
   - **API**: set URL + optional field path + refresh interval
4. Click **Refresh** for immediate pull, or let auto-polling run.

## API path examples

If your API returns:

```json
{
  "data": {
    "price": 92.5
  }
}
```

Use:

- URL: `https://your-api.example.com/endpoint`
- Field path: `data.price`

If `fieldPath` is left empty, the full response is used.

## Live behavior

- Every change is broadcast via Socket.IO.
- API cells are polled automatically based on each cell interval.
- Row and cell updates are immediately visible to all connected users.

## Legacy files

The repository still includes older Python automation files (`om_eticket_downloader.py`, `streamlit_app.py`) which are not required for this JavaScript dashboard.
