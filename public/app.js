const socket = io();

const tableBody = document.getElementById("targetBody");
const addRowButton = document.getElementById("addRowBtn");
const connectionBadge = document.getElementById("connectionBadge");
const modalBackdrop = document.getElementById("modalBackdrop");
const cellForm = document.getElementById("modalForm");
const modalTitle = document.getElementById("modalTitle");
const modalSubtitle = document.getElementById("modalSubtitle");
const modalCancelButton = document.getElementById("modalCancelBtn");
const searchInput = document.getElementById("searchInput");
const clearSearchButton = document.getElementById("clearSearchBtn");
const sourceFilter = document.getElementById("sourceFilter");

let currentState = null;
let activeCellRef = null;
const lastValueMap = new Map();
let searchTerm = "";
let selectedSource = "all";

const fmtNumber = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 2,
});

function api(path, options = {}) {
  return fetch(path, {
    method: options.method || "GET",
    headers: {
      "Content-Type": "application/json",
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  }).then(async (response) => {
    if (!response.ok) {
      let message = `Request failed (${response.status})`;
      try {
        const payload = await response.json();
        if (payload?.error) {
          message = payload.error;
        }
      } catch (_err) {
        // Ignore JSON parsing errors.
      }
      throw new Error(message);
    }
    if (response.status === 204) {
      return null;
    }
    return response.json();
  });
}

function updateConnection(online) {
  if (online) {
    connectionBadge.classList.add("online");
    connectionBadge.classList.remove("offline");
    connectionBadge.textContent = "Live";
    return;
  }
  connectionBadge.classList.remove("online");
  connectionBadge.classList.add("offline");
  connectionBadge.textContent = "Disconnected";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function createCellKey(rowId, section, index) {
  return `${rowId}:${section}:${index}`;
}

function createDeltaBadge(value, previousValue) {
  if (typeof value !== "number" || typeof previousValue !== "number") {
    return '<span class="perf-pill warn">n/a</span>';
  }

  const delta = value - previousValue;
  if (delta === 0) {
    return '<span class="perf-pill warn">0.00</span>';
  }

  if (delta > 0) {
    return `<span class="perf-pill good">+${fmtNumber.format(delta)}</span>`;
  }
  return `<span class="perf-pill bad">${fmtNumber.format(delta)}</span>`;
}

function deriveStock(row) {
  return row.inTargets.reduce((sum, cell) => sum + (Number(cell.value) || 0), 0);
}

function deriveSoldUnsold(row) {
  const faceTotal = row.faceValue.reduce((sum, cell) => sum + (Number(cell.value) || 0), 0);
  const targetTotal = row.inTargets.reduce((sum, cell) => sum + (Number(cell.value) || 0), 0);
  const sold = Math.max(0, Math.round(faceTotal - targetTotal));
  const unsold = Math.max(0, Math.round(targetTotal));
  return `${sold} / ${unsold}`;
}

function formatValue(value) {
  if (typeof value === "number") {
    return fmtNumber.format(value);
  }
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

function rowSummary(row) {
  const total = row.faceValue.reduce((sum, cell) => sum + (Number(cell.value) || 0), 0);
  const stock = deriveStock(row);
  return {
    total,
    stock,
    soldUnsold: deriveSoldUnsold(row),
  };
}

function statusText(cell) {
  if (cell.status === "error") return "Error";
  if (cell.status === "loading") return "Syncing";
  return cell.source === "api" ? "API" : "Manual";
}

function renderCellCard(row, section, index, cell) {
  const cellKey = createCellKey(row.id, section, index);
  const previous = lastValueMap.get(cellKey);
  const valueLabel = formatValue(cell.value);
  const hint =
    cell.source === "api"
      ? cell.api.url || "API URL missing"
      : `Manual value: ${formatValue(cell.manualValue)}`;

  lastValueMap.set(cellKey, typeof cell.value === "number" ? cell.value : previous);

  return `
    <div class="metric-card">
      <div class="metric-top">
        <span class="mini-tag ${cell.source === "api" ? "api" : "manual"}">${cell.source.toUpperCase()}</span>
        <span class="mini-status">${statusText(cell)}</span>
      </div>
      <div class="value-line">
        <strong class="value-main">${escapeHtml(valueLabel)}</strong>
        ${createDeltaBadge(typeof cell.value === "number" ? cell.value : null, previous)}
      </div>
      <div class="api-preview">${escapeHtml(cell.error || hint)}</div>
      <div class="card-actions">
        <button data-action="refresh-cell" data-row-id="${row.id}" data-section="${section}" data-index="${index}">
          Refresh
        </button>
        <button data-action="edit-cell" data-row-id="${row.id}" data-section="${section}" data-index="${index}">
          Configure
        </button>
      </div>
    </div>
  `;
}

function rowMatchesSource(row) {
  if (selectedSource === "all") {
    return true;
  }
  const allCells = [...row.faceValue, ...row.inTargets];
  return allCells.some((cell) => cell.source === selectedSource);
}

function render() {
  if (!currentState) {
    return;
  }

  const filteredRows = currentState.rows.filter((row) => {
    const matchesSearch = !searchTerm
      ? true
      : `${row.matchNumber} ${row.venue} ${row.game}`.toLowerCase().includes(searchTerm);
    return matchesSearch && rowMatchesSource(row);
  });

  if (!filteredRows.length) {
    tableBody.innerHTML = `
      <tr>
        <td colspan="14" class="empty">No rows match your current filters.</td>
      </tr>
    `;
    return;
  }

  tableBody.innerHTML = filteredRows
    .map((row) => {
      const summary = rowSummary(row);
      const perfValue = summary.total - summary.stock;
      const perfClass = perfValue >= 0 ? "good" : "bad";
      const perfLabel = `${perfValue >= 0 ? "+" : ""}${fmtNumber.format(perfValue)}`;

      return `
        <tr>
          <td class="event-cell">
            <p class="event-title">
              <input
                class="editable"
                data-inline-field="game"
                data-row-id="${row.id}"
                value="${escapeHtml(row.game || "")}"
              />
            </p>
            <p class="event-sub">
              #<input
                class="editable"
                data-inline-field="matchNumber"
                data-row-id="${row.id}"
                value="${escapeHtml(row.matchNumber || "")}"
              />
              ·
              <input
                class="editable"
                data-inline-field="venue"
                data-row-id="${row.id}"
                value="${escapeHtml(row.venue || "")}"
              />
            </p>
          </td>
          <td class="metric-cell">${fmtNumber.format(summary.total)}</td>
          <td class="metric-cell">${fmtNumber.format(summary.stock)}</td>
          <td class="metric-cell">${escapeHtml(summary.soldUnsold)}</td>
          <td><span class="perf-pill ${perfClass}">${perfLabel}</span></td>
          ${row.faceValue.map((cell, index) => `<td>${renderCellCard(row, "faceValue", index, cell)}</td>`).join("")}
          ${row.inTargets.map((cell, index) => `<td>${renderCellCard(row, "inTargets", index, cell)}</td>`).join("")}
          <td>
            <div class="row-actions">
              <button data-action="edit-row" data-row-id="${row.id}">Edit</button>
              <button class="danger-btn" data-action="delete-row" data-row-id="${row.id}">Delete</button>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
}

function showModal(rowId, section, index) {
  const row = currentState.rows.find((entry) => entry.id === rowId);
  if (!row) return;

  const cell = row[section][Number(index)];
  if (!cell) return;

  activeCellRef = { rowId, section, index: Number(index) };
  modalTitle.textContent = "Configure box source";
  modalSubtitle.textContent = `${row.game || "Match"} · ${section === "faceValue" ? "Face Value" : "In Targets"} C${
    Number(index) + 1
  }`;

  cellForm.innerHTML = `
    <div class="modal-row">
      <label for="sourceInput">Source</label>
      <select id="sourceInput" name="source" required>
        <option value="manual" ${cell.source === "manual" ? "selected" : ""}>Manual</option>
        <option value="api" ${cell.source === "api" ? "selected" : ""}>API</option>
      </select>
    </div>
    <div class="modal-row">
      <label for="manualValueInput">Manual value</label>
      <input id="manualValueInput" name="manualValue" type="number" step="0.01" value="${Number(cell.manualValue) || 0}" />
    </div>
    <div class="modal-row">
      <label for="apiUrlInput">API URL</label>
      <input
        id="apiUrlInput"
        name="apiUrl"
        type="url"
        placeholder="https://api.example.com/data"
        value="${escapeHtml(cell.api.url || "")}"
      />
    </div>
    <div class="modal-row">
      <label for="fieldPathInput">Field path</label>
      <input
        id="fieldPathInput"
        name="fieldPath"
        type="text"
        placeholder="data.price"
        value="${escapeHtml(cell.api.fieldPath || "")}"
      />
    </div>
    <div class="modal-row">
      <label for="intervalInput">Refresh interval (seconds)</label>
      <input
        id="intervalInput"
        name="intervalSeconds"
        type="number"
        min="5"
        value="${Number(cell.api.intervalSeconds) || 60}"
      />
    </div>
  `;
  modalBackdrop.classList.add("active");
}

function hideModal() {
  activeCellRef = null;
  modalBackdrop.classList.remove("active");
}

async function handleActionClick(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) {
    return;
  }

  const action = button.dataset.action;
  const rowId = button.dataset.rowId;
  const section = button.dataset.section;
  const index = button.dataset.index;

  try {
    if (action === "refresh-cell") {
      await api(`/api/cells/${rowId}/${section}/${index}/refresh`, { method: "POST" });
      return;
    }

    if (action === "edit-cell") {
      showModal(rowId, section, index);
      return;
    }

    if (action === "delete-row") {
      if (!window.confirm("Delete this row?")) {
        return;
      }
      await api(`/api/rows/${rowId}`, { method: "DELETE" });
      return;
    }

    if (action === "edit-row") {
      const row = currentState.rows.find((entry) => entry.id === rowId);
      if (!row) return;

      const matchNumber = window.prompt("Match number", row.matchNumber || "");
      if (matchNumber === null) return;
      const venue = window.prompt("Venue", row.venue || "");
      if (venue === null) return;
      const game = window.prompt("Game", row.game || "");
      if (game === null) return;

      await api(`/api/rows/${rowId}`, {
        method: "PATCH",
        body: { matchNumber, venue, game },
      });
    }
  } catch (error) {
    window.alert(error.message);
  }
}

async function handleInlineRowUpdate(input) {
  const rowId = input.dataset.rowId;
  const field = input.dataset.inlineField;
  if (!rowId || !field) {
    return;
  }
  try {
    await api(`/api/rows/${rowId}`, {
      method: "PATCH",
      body: { [field]: input.value },
    });
  } catch (error) {
    window.alert(error.message);
  }
}

async function handleCreateRow() {
  try {
    const matchNumber = window.prompt("Match number");
    if (matchNumber === null) return;
    const venue = window.prompt("Venue");
    if (venue === null) return;
    const game = window.prompt("Game");
    if (game === null) return;

    await api("/api/rows", {
      method: "POST",
      body: { matchNumber, venue, game },
    });
  } catch (error) {
    window.alert(error.message);
  }
}

async function submitCellForm(event) {
  event.preventDefault();
  if (!activeCellRef) {
    return;
  }

  try {
    const sourceInput = document.getElementById("sourceInput");
    const manualValueInput = document.getElementById("manualValueInput");
    const apiUrlInput = document.getElementById("apiUrlInput");
    const fieldPathInput = document.getElementById("fieldPathInput");
    const intervalInput = document.getElementById("intervalInput");

    await api(`/api/cells/${activeCellRef.rowId}/${activeCellRef.section}/${activeCellRef.index}`, {
      method: "PATCH",
      body: {
        source: sourceInput.value,
        manualValue: Number(manualValueInput.value || 0),
        api: {
          url: apiUrlInput.value.trim(),
          fieldPath: fieldPathInput.value.trim(),
          intervalSeconds: Number(intervalInput.value || 60),
        },
      },
    });

    await api(`/api/cells/${activeCellRef.rowId}/${activeCellRef.section}/${activeCellRef.index}/refresh`, {
      method: "POST",
    });
    hideModal();
  } catch (error) {
    window.alert(error.message);
  }
}

tableBody.addEventListener("click", handleActionClick);
tableBody.addEventListener(
  "blur",
  (event) => {
    const input = event.target.closest("input[data-inline-field]");
    if (!input) {
      return;
    }
    handleInlineRowUpdate(input);
  },
  true
);

addRowButton.addEventListener("click", handleCreateRow);
cellForm.addEventListener("submit", submitCellForm);
modalCancelButton.addEventListener("click", hideModal);
modalBackdrop.addEventListener("click", (event) => {
  if (event.target === modalBackdrop) {
    hideModal();
  }
});

searchInput.addEventListener("input", () => {
  searchTerm = searchInput.value.trim().toLowerCase();
  render();
});

sourceFilter.addEventListener("change", () => {
  selectedSource = sourceFilter.value;
  render();
});

clearSearchButton.addEventListener("click", () => {
  searchTerm = "";
  selectedSource = "all";
  searchInput.value = "";
  sourceFilter.value = "all";
  render();
});

socket.on("connect", () => updateConnection(true));
socket.on("disconnect", () => updateConnection(false));
socket.on("state", (incomingState) => {
  currentState = incomingState;
  render();
});
