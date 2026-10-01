const $ = (id) => document.getElementById(id);
let activePreview = null;

async function api(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-User-Id": "1" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(payload.detail || "The recipe could not be imported.");
  }
  return res.json();
}

function previewText(data) {
  const recipe = data.recipe;
  activePreview = data;
  $("preview-card").hidden = false;
  $("saved").hidden = true;
  $("title").value = recipe.canonical_name || "";
  $("cuisine").value = recipe.cuisine || "";
  $("servings").value = recipe.servings || 2;
  $("prep").value = recipe.prep_minutes || 0;
  $("cook").value = recipe.cook_minutes || 0;
  $("ingredients").value = (recipe.ingredients || []).map((item) => {
    const quantity = Number(item.quantity);
    const amount = Number.isFinite(quantity) && quantity > 0 ? `${quantity} ${item.unit || ""} ` : "";
    const notes = item.notes ? `, ${item.notes}` : "";
    return `${amount}${item.name || ""}${notes}`.trim();
  }).join("\n");
  $("steps").value = (recipe.steps || []).map((step) => step.instruction || "").join("\n");
  const decision = data.decision || {};
  const signals = decision.signals || {};
  const kind = signals.content_kind || {};
  const score = signals.completeness || {};
  $("decision").textContent = `Status: ${decision.status || "review"} · check: ${data.decision_provider || "local"} · content: ${kind.choice || "unknown"} · completeness: ${score.score ?? "—"}/3. A person must review and save.`;
  const warnings = [...(data.warnings || [])];
  if (decision.warning && !warnings.includes(decision.warning)) warnings.push(decision.warning);
  const list = $("warnings");
  list.replaceChildren();
  warnings.forEach((warning) => {
    const li = document.createElement("li");
    li.textContent = warning;
    list.appendChild(li);
  });
}

$("preview").onclick = async () => {
  $("message").textContent = "Parsing your recipe…";
  $("preview-card").hidden = true;
  try {
    const data = await api("/api/recipes/import/preview", { text: $("source").value });
    previewText(data);
    $("message").textContent = "Check the parsed fields and correct anything that needs it.";
  } catch (error) {
    $("message").textContent = error.message;
  }
};

$("save").onclick = async () => {
  if (!activePreview) return;
  if (!$("confirm").checked) {
    $("message").textContent = "Confirm that you reviewed the recipe before saving.";
    return;
  }
  $("message").textContent = "Saving your recipe…";
  try {
    const result = await api("/api/recipes/import/commit", {
      preview_id: activePreview.preview_id,
      title: $("title").value,
      cuisine: $("cuisine").value,
      servings: Number($("servings").value || 2),
      prep_minutes: Number($("prep").value || 0),
      cook_minutes: Number($("cook").value || 0),
      ingredients_text: $("ingredients").value,
      steps_text: $("steps").value,
      confirm_review: true,
    });
    activePreview = null;
    $("preview-card").hidden = true;
    $("saved").hidden = false;
    $("saved").replaceChildren();
    const heading = document.createElement("h2");
    heading.textContent = `${result.recipe.canonical_name} saved`;
    const message = document.createElement("p");
    message.textContent = result.note;
    const link = document.createElement("a");
    link.href = "/app";
    link.textContent = "Find recipes for tonight";
    $("saved").append(heading, message, link);
    $("message").textContent = "";
  } catch (error) {
    $("message").textContent = error.message;
  }
};
