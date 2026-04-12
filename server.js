const express = require("express");
const http = require("http");
const path = require("path");
const axios = require("axios");
const { Server } = require("socket.io");

const PORT = process.env.PORT || 3000;
const POLL_TICK_MS = 5000;
const DEFAULT_INTERVAL_SECONDS = 60;
const CELL_COUNT = 4;

function createCell(label) {
  return {
    label,
    source: "manual",
    manualValue: 0,
    value: 0,
    api: {
      url: "",
      fieldPath: "",
      intervalSeconds: DEFAULT_INTERVAL_SECONDS,
    },
    status: "idle",
    error: null,
    lastUpdated: null,
    nextPollAt: null,
  };
}

function createRow(id) {
  return {
    id,
    matchNumber: "",
    venue: "",
    game: "",
    faceValue: Array.from({ length: CELL_COUNT }, (_, i) => createCell(`Category ${i + 1}`)),
    inTargets: Array.from({ length: CELL_COUNT }, (_, i) => createCell(`Category ${i + 1}`)),
  };
}

const state = {
  updatedAt: new Date().toISOString(),
  rows: [createRow("row-1")],
};

function touchState() {
  state.updatedAt = new Date().toISOString();
}

function toNumberIfPossible(input) {
  if (typeof input === "number") {
    return Number.isFinite(input) ? input : 0;
  }
  if (typeof input === "string") {
    const parsed = Number.parseFloat(input);
    return Number.isFinite(parsed) ? parsed : input;
  }
  return input;
}

function getByPath(payload, fieldPath) {
  if (!fieldPath || typeof fieldPath !== "string") {
    return payload;
  }
  return fieldPath.split(".").reduce((acc, token) => {
    if (acc === null || acc === undefined) {
      return undefined;
    }
    return acc[token];
  }, payload);
}

function normalizeSection(section) {
  if (section === "faceValue" || section === "inTargets") {
    return section;
  }
  return null;
}

function getCellFromParams({ rowId, section, index }) {
  const row = state.rows.find((entry) => entry.id === rowId);
  const normalizedSection = normalizeSection(section);
  const parsedIndex = Number.parseInt(index, 10);

  if (!row || !normalizedSection || Number.isNaN(parsedIndex) || parsedIndex < 0 || parsedIndex >= CELL_COUNT) {
    return { error: "Unknown row/section/index" };
  }

  return {
    row,
    cell: row[normalizedSection][parsedIndex],
    section: normalizedSection,
    index: parsedIndex,
  };
}

async function refreshApiCell(cell) {
  if (!cell.api.url) {
    throw new Error("API URL is required for API source");
  }

  const response = await axios.get(cell.api.url, {
    timeout: 10000,
  });
  const raw = getByPath(response.data, cell.api.fieldPath);
  if (raw === undefined) {
    throw new Error("Field path not found in API response");
  }

  cell.value = toNumberIfPossible(raw);
  cell.lastUpdated = new Date().toISOString();
  cell.error = null;
  cell.status = "ok";
}

const app = express();
const server = http.createServer(app);
const io = new Server(server);

app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

function emitState() {
  touchState();
  io.emit("state", state);
}

app.get("/api/state", (_, res) => {
  res.json(state);
});

app.post("/api/rows", (req, res) => {
  const rowId = `row-${Date.now()}`;
  const row = createRow(rowId);
  row.matchNumber = String(req.body?.matchNumber ?? "");
  row.venue = String(req.body?.venue ?? "");
  row.game = String(req.body?.game ?? "");

  state.rows.push(row);
  emitState();
  res.status(201).json(row);
});

app.patch("/api/rows/:rowId", (req, res) => {
  const row = state.rows.find((entry) => entry.id === req.params.rowId);
  if (!row) {
    res.status(404).json({ error: "Row not found" });
    return;
  }

  const { matchNumber, venue, game } = req.body ?? {};
  if (matchNumber !== undefined) row.matchNumber = String(matchNumber);
  if (venue !== undefined) row.venue = String(venue);
  if (game !== undefined) row.game = String(game);

  emitState();
  res.json(row);
});

app.delete("/api/rows/:rowId", (req, res) => {
  const originalLength = state.rows.length;
  state.rows = state.rows.filter((entry) => entry.id !== req.params.rowId);
  if (state.rows.length === originalLength) {
    res.status(404).json({ error: "Row not found" });
    return;
  }

  emitState();
  res.status(204).send();
});

app.patch("/api/cells/:rowId/:section/:index", (req, res) => {
  const result = getCellFromParams(req.params);
  if (result.error) {
    res.status(404).json({ error: result.error });
    return;
  }

  const { cell } = result;
  const { source, manualValue, api } = req.body ?? {};

  if (source === "manual" || source === "api") {
    cell.source = source;
  }

  if (manualValue !== undefined) {
    cell.manualValue = toNumberIfPossible(manualValue);
    if (cell.source === "manual") {
      cell.value = cell.manualValue;
      cell.status = "ok";
      cell.error = null;
      cell.lastUpdated = new Date().toISOString();
    }
  }

  if (api) {
    if (api.url !== undefined) cell.api.url = String(api.url);
    if (api.fieldPath !== undefined) cell.api.fieldPath = String(api.fieldPath);
    if (api.intervalSeconds !== undefined) {
      const interval = Number.parseInt(api.intervalSeconds, 10);
      cell.api.intervalSeconds = Number.isFinite(interval) && interval > 0 ? interval : DEFAULT_INTERVAL_SECONDS;
    }
  }

  if (cell.source === "api") {
    cell.status = "idle";
    cell.nextPollAt = 0;
  }

  emitState();
  res.json(cell);
});

app.post("/api/cells/:rowId/:section/:index/refresh", async (req, res) => {
  const result = getCellFromParams(req.params);
  if (result.error) {
    res.status(404).json({ error: result.error });
    return;
  }

  const { cell } = result;
  try {
    if (cell.source === "manual") {
      cell.value = cell.manualValue;
      cell.status = "ok";
      cell.error = null;
      cell.lastUpdated = new Date().toISOString();
    } else {
      cell.status = "loading";
      emitState();
      await refreshApiCell(cell);
      cell.nextPollAt = Date.now() + cell.api.intervalSeconds * 1000;
    }

    emitState();
    res.json(cell);
  } catch (error) {
    cell.status = "error";
    cell.error = error.message || "Unknown API error";
    cell.lastUpdated = new Date().toISOString();
    cell.nextPollAt = Date.now() + cell.api.intervalSeconds * 1000;
    emitState();
    res.status(400).json({ error: cell.error });
  }
});

io.on("connection", (socket) => {
  socket.emit("state", state);
});

let pollInFlight = false;

setInterval(async () => {
  if (pollInFlight) {
    return;
  }
  pollInFlight = true;

  try {
    const now = Date.now();
    const work = [];
    for (const row of state.rows) {
      for (const section of ["faceValue", "inTargets"]) {
        for (const cell of row[section]) {
          if (cell.source !== "api" || !cell.api.url) {
            continue;
          }
          if (cell.nextPollAt && now < cell.nextPollAt) {
            continue;
          }
          work.push(cell);
        }
      }
    }

    if (!work.length) {
      return;
    }

    for (const cell of work) {
      try {
        cell.status = "loading";
        emitState();
        await refreshApiCell(cell);
      } catch (error) {
        cell.status = "error";
        cell.error = error.message || "Unknown API error";
        cell.lastUpdated = new Date().toISOString();
      } finally {
        cell.nextPollAt = Date.now() + cell.api.intervalSeconds * 1000;
        emitState();
      }
    }
  } finally {
    pollInFlight = false;
  }
}, POLL_TICK_MS);

server.listen(PORT, () => {
  // eslint-disable-next-line no-console
  console.log(`Live target dashboard running on http://localhost:${PORT}`);
});
