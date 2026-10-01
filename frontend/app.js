const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", "X-User-Id": "1" },
    ...options,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function card(c) {
  const cost = c.estimated_cost || {};
  const n = (c.nutrition || {}).per_serving || {};
  const missing = (c.pantry || {}).missing || [];
  const el = document.createElement("article");
  el.className = "card";
  el.innerHTML = `
    <h2>${escapeHtml(c.title)}</h2>
    <p class="muted">${escapeHtml(c.cuisine)} · ${escapeHtml(c.region)} · score ${escapeHtml(c.score.score)}</p>
    <p>${escapeHtml(c.explanation)}</p>
    <p>
      <span class="tag">${n.calories || "—"} kcal / serving</span>
      <span class="tag">${n.protein_g || "—"} g protein</span>
      <span class="tag">${cost.amount == null ? "cost unavailable" : `est. ₹${cost.amount}`}</span>
    </p>
    <p class="muted">Shopping: ${missing.map((m) => m.quantity == null ? `${escapeHtml(m.name)} (amount unspecified)` : `${escapeHtml(m.name)} ${escapeHtml(m.quantity)}${escapeHtml(m.unit)}`).join(", ") || "nothing missing"}</p>
    <button data-id="${c.id}">Cook this</button>
  `;
  el.querySelector("button").onclick = () => start(c);
  return el;
}

async function start(c) {
  const session = await api(`/api/recipe/${c.id}/start`, { method: "POST" });
  sessionStorage.setItem("cookai-session", JSON.stringify({ session, card: c }));
  const list = await api("/api/shopping/create", {
    method: "POST",
    body: JSON.stringify({ recipe_id: c.id, items: c.pantry.missing }),
  });
  sessionStorage.setItem("cookai-list", JSON.stringify(list));
  location.href = "/cooking";
}

async function recommend() {
  const data = await api("/api/recipe/generate", {
    method: "POST",
    body: JSON.stringify({ message: $("ask").value, people: 4, budget: 700 }),
  });
  const root = $("results");
  root.innerHTML = "";
  data.candidates.forEach((c) => root.appendChild(card(c)));
}

async function loadToday() {
  if (!$("today")) return;
  const today = await api("/api/food/today");
  $("today").innerHTML = `<strong>Today</strong><p class="muted">${today.calories} kcal · ${today.protein_g} g protein · ₹${today.spend}</p>`;
}

async function cooking() {
  const saved = JSON.parse(sessionStorage.getItem("cookai-session") || "null");
  if (!saved) return;
  const paint = (session) => {
    $("title").textContent = session.title;
    $("step").textContent = `Step ${session.current_step} / ${session.steps.length}`;
    $("instruction").textContent = session.steps[session.current_step - 1]?.instruction || session.instruction || "";
  };
  paint(saved.session);
  const send = async (path, body) => {
    saved.session = await api(path, { method: "POST", body: JSON.stringify(body) });
    sessionStorage.setItem("cookai-session", JSON.stringify(saved));
    paint(saved.session);
  };
  $("next").onclick = () => send(`/api/cooking/${saved.session.id}/message`, { action: "next" });
  $("prev").onclick = () => send(`/api/cooking/${saved.session.id}/message`, { action: "prev" });
  $("vision").onclick = () => send(`/api/cooking/${saved.session.id}/vision`, { visual_state: "light_golden" });
  $("done").onclick = async () => {
    await api("/api/meal/log", {
      method: "POST",
      body: JSON.stringify({
        title: saved.card.title,
        recipe_id: saved.card.id,
        cuisine: saved.card.cuisine,
        nutrition: saved.card.nutrition,
        estimated_cost: saved.card.estimated_cost,
        servings_eaten: 1,
      }),
    });
    location.href = "/app";
  };
}

if ($("go")) {
  $("go").onclick = recommend;
  loadToday();
  recommend();
}
if ($("done")) cooking();
