"use strict";

const TASKS_ENABLED = document.body.dataset.tasksEnabled === "true";

const state = {
  events: [],
  filtered: [],
  sort: { key: "timestamp", dir: 1 },
};

// ---- Log viewer -----------------------------------------------------------

async function loadEvents() {
  const res = await fetch("/api/events");
  const data = await res.json();
  state.events = data.events || [];
  document.getElementById("dsmeta").textContent =
    `dataset v${data.dataset_version} · ${data.timezone} · ${data.notice}`;
  populateTypeFilter();
  applyFilters();
}

function populateTypeFilter() {
  const sel = document.getElementById("f-type");
  const types = [...new Set(state.events.map((e) => e.event_type))].sort();
  for (const t of types) {
    const o = document.createElement("option");
    o.value = t;
    o.textContent = t;
    sel.appendChild(o);
  }
}

function parseTs(v) {
  const d = new Date(v);
  return isNaN(d.getTime()) ? null : d.getTime();
}

function applyFilters() {
  const q = document.getElementById("q").value.trim().toLowerCase();
  const fu = document.getElementById("f-username").value.trim().toLowerCase();
  const fi = document.getElementById("f-ip").value.trim().toLowerCase();
  const ft = document.getElementById("f-type").value;
  const from = parseTs(document.getElementById("f-from").value.trim());
  const to = parseTs(document.getElementById("f-to").value.trim());

  state.filtered = state.events.filter((e) => {
    if (q) {
      const hay = `${e.message} ${e.username} ${e.source_ip} ${e.event_ref} ${e.event_type}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (fu && !String(e.username || "").toLowerCase().includes(fu)) return false;
    if (fi && !String(e.source_ip || "").toLowerCase().includes(fi)) return false;
    if (ft && e.event_type !== ft) return false;
    const ts = parseTs(e.timestamp);
    if (from !== null && ts < from) return false;
    if (to !== null && ts > to) return false;
    return true;
  });

  sortFiltered();
  renderRows();
}

function sortFiltered() {
  const { key, dir } = state.sort;
  state.filtered.sort((a, b) => {
    const av = a[key] ?? "";
    const bv = b[key] ?? "";
    return av < bv ? -dir : av > bv ? dir : 0;
  });
}

function renderRows() {
  const tbody = document.getElementById("rows");
  tbody.innerHTML = "";
  for (const e of state.filtered) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="ts">${escapeHtml(e.timestamp)}</td>
      <td><span class="etype ${escapeHtml(e.event_type)}">${escapeHtml(e.event_type)}</span></td>
      <td>${escapeHtml(e.username ?? "")}</td>
      <td class="ip">${escapeHtml(e.source_ip ?? "")}</td>
      <td class="ref">${escapeHtml(e.event_ref)}</td>
      <td class="msg">${escapeHtml(e.message ?? "")}</td>`;
    tbody.appendChild(tr);
  }
  document.getElementById("count").textContent =
    `${state.filtered.length} / ${state.events.length} events`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function wireViewer() {
  ["q", "f-username", "f-ip", "f-from", "f-to"].forEach((id) =>
    document.getElementById(id).addEventListener("input", applyFilters));
  document.getElementById("f-type").addEventListener("change", applyFilters);
  document.getElementById("clearBtn").addEventListener("click", () => {
    ["q", "f-username", "f-ip", "f-from", "f-to"].forEach((id) =>
      (document.getElementById(id).value = ""));
    document.getElementById("f-type").value = "";
    applyFilters();
  });
  document.querySelectorAll("th.sortable").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      state.sort.dir = state.sort.key === key ? -state.sort.dir : 1;
      state.sort.key = key;
      document.querySelectorAll("th.sortable").forEach((h) =>
        (h.textContent = h.textContent.replace(/ [▲▼]$/, "")));
      th.textContent += state.sort.dir === 1 ? " ▲" : " ▼";
      sortFiltered();
      renderRows();
    });
  });
}

// ---- Tasks ----------------------------------------------------------------

async function loadTasks() {
  const res = await fetch("/api/meta");
  const meta = await res.json();
  document.getElementById("maxscore").textContent = meta.max_score;
  renderTasks(meta);
  await refreshSession();
}

function renderTasks(meta) {
  const root = document.getElementById("sections");
  root.innerHTML = "";
  const tasks = [...meta.tasks].sort((a, b) => a.sort_order - b.sort_order);
  for (const section of meta.sections) {
    const h = document.createElement("div");
    h.className = "section-title";
    h.textContent = section.title;
    root.appendChild(h);
    for (const t of tasks.filter((x) => x.section_id === section.id)) {
      root.appendChild(renderTask(t));
    }
  }
}

function renderTask(t) {
  const el = document.createElement("div");
  el.className = "task";
  el.id = `task-${t.id}`;

  const head = document.createElement("div");
  head.className = "task-head";
  head.innerHTML = `<span class="task-title">${escapeHtml(t.title)}
      <span class="task-id">${escapeHtml(t.id)}</span></span>
      <span class="task-points">${t.points} pts</span>`;
  el.appendChild(head);

  const instr = document.createElement("p");
  instr.className = "task-instructions";
  instr.textContent = t.instructions;
  el.appendChild(instr);

  const field = document.createElement("div");
  field.className = "field";
  field.appendChild(buildInput(t));
  const btn = document.createElement("button");
  btn.className = "btn";
  btn.textContent = "Submit";
  btn.addEventListener("click", () => submitTask(t, el));
  field.appendChild(btn);
  el.appendChild(field);

  const fb = document.createElement("div");
  fb.className = "feedback";
  el.appendChild(fb);
  return el;
}

function buildInput(t) {
  const wrap = document.createElement("div");
  wrap.className = "field";
  wrap.style.flex = "1 1 100%";

  if (t.input === "choice" || t.input === "choice_with_evidence") {
    const sel = document.createElement("select");
    sel.dataset.role = "choice";
    for (const c of t.choices || []) {
      const o = document.createElement("option");
      o.value = c; o.textContent = c; sel.appendChild(o);
    }
    wrap.appendChild(sel);
    if (t.input === "choice_with_evidence") {
      const ev = document.createElement("input");
      ev.type = "text"; ev.dataset.role = "evidence";
      ev.placeholder = t.evidence_hint || "evidence";
      wrap.appendChild(ev);
    }
  } else if (t.input === "ordered_events") {
    for (let i = 0; i < (t.event_choices || []).length; i++) {
      const row = document.createElement("div");
      row.className = "ordered-row";
      const label = document.createElement("span");
      label.textContent = `#${i + 1}`;
      const sel = document.createElement("select");
      sel.dataset.role = "order";
      const blank = document.createElement("option");
      blank.value = ""; blank.textContent = "— pick —"; sel.appendChild(blank);
      for (const c of t.event_choices) {
        const o = document.createElement("option");
        o.value = c; o.textContent = c; sel.appendChild(o);
      }
      row.appendChild(label); row.appendChild(sel);
      wrap.appendChild(row);
    }
  } else {
    const inp = document.createElement("input");
    inp.type = "text"; inp.dataset.role = "text";
    inp.placeholder = t.answer_hint || "answer";
    wrap.appendChild(inp);
  }
  return wrap;
}

function collectAnswer(t, el) {
  if (t.input === "choice") {
    return el.querySelector('[data-role="choice"]').value;
  }
  if (t.input === "choice_with_evidence") {
    return {
      choice: el.querySelector('[data-role="choice"]').value,
      evidence: el.querySelector('[data-role="evidence"]').value,
    };
  }
  if (t.input === "ordered_events") {
    return { order: [...el.querySelectorAll('[data-role="order"]')].map((s) => s.value) };
  }
  return el.querySelector('[data-role="text"]').value;
}

async function submitTask(t, el) {
  const fb = el.querySelector(".feedback");
  const answer = collectAnswer(t, el);
  const res = await fetch(`/api/tasks/${t.id}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answer }),
  });
  const data = await res.json().catch(() => ({}));

  if (res.status === 422) {
    fb.className = "feedback warn"; fb.textContent = `Invalid input: ${data.detail}`; return;
  }
  if (res.status === 429) {
    fb.className = "feedback bad"; fb.textContent = "Attempt limit reached."; return;
  }
  if (!res.ok) {
    fb.className = "feedback bad"; fb.textContent = data.detail || "Submission error."; return;
  }

  if (data.correct) {
    fb.className = "feedback ok";
    fb.textContent = `✓ ${data.message} (+${data.points_awarded} pts)`;
    el.classList.add("solved");
  } else {
    fb.className = "feedback bad";
    const left = data.attempts_remaining;
    fb.textContent = `✗ ${data.message}` + (left !== undefined ? ` (${left} attempts left)` : "");
  }
  updateScore(data);
}

async function refreshSession() {
  const res = await fetch("/api/session");
  if (!res.ok) return;
  const s = await res.json();
  updateScore(s);
  for (const [tid, st] of Object.entries(s.tasks || {})) {
    if (st.solved) document.getElementById(`task-${tid}`)?.classList.add("solved");
  }
}

function updateScore(s) {
  if (s.progress) document.getElementById("progress").textContent =
    `${s.progress.completed}/${s.progress.total}`;
  if (s.score !== undefined) document.getElementById("score").textContent = s.score;
  if (s.max_score !== undefined) document.getElementById("maxscore").textContent = s.max_score;
}

function wireReset() {
  const btn = document.getElementById("resetBtn");
  if (!btn) return;
  btn.addEventListener("click", async () => {
    if (!confirm("Reset all progress for this session?")) return;
    await fetch("/api/session/reset", { method: "POST" });
    document.querySelectorAll(".task").forEach((t) => {
      t.classList.remove("solved");
      t.querySelector(".feedback").textContent = "";
    });
    await refreshSession();
  });
}

// ---- Boot -----------------------------------------------------------------

(async function init() {
  wireViewer();
  await loadEvents();
  if (TASKS_ENABLED) {
    wireReset();
    await loadTasks();
  }
})();
