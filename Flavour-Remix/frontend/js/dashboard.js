const API_BASE =
  window.FLAVOUR_REMIX_API_BASE ||
  window.localStorage.getItem("FLAVOUR_REMIX_API_BASE") ||
  ((window.location.protocol === "http:" || window.location.protocol === "https:")
    ? window.location.origin
    : "http://127.0.0.1:8000");

const appState = {
  currentTitle: "",
  resolvedRecipeId: "",
};


function setStatus(message, type = "info") {
  const statusEl = document.getElementById("statusText");
  if (!statusEl) return;
  statusEl.textContent = message;
  if (type === "error") {
    statusEl.style.color = "#a94442";
    return;
  }
  if (type === "success") {
    statusEl.style.color = "#184d3b";
    return;
  }
  statusEl.style.color = "#333";
}


function renderIngredients(ingredients) {
  const select = document.getElementById("ingredientSelect");
  select.innerHTML = "";

  if (!Array.isArray(ingredients) || ingredients.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.text = "No ingredients found";
    select.appendChild(option);
    return;
  }

  ingredients.forEach((ingredient) => {
    const option = document.createElement("option");
    option.value = ingredient;
    option.text = ingredient;
    select.appendChild(option);
  });
}


function normalizeErrorDetail(detail) {
  if (!detail) return "Request failed.";
  if (typeof detail === "string") return detail;
  if (typeof detail.message === "string") return detail.message;
  try {
    return JSON.stringify(detail);
  } catch {
    return "Request failed.";
  }
}


async function parseErrorMessage(response) {
  try {
    const payload = await response.json();
    return normalizeErrorDetail(payload.detail || payload.error || payload.message);
  } catch {
    return `HTTP ${response.status}`;
  }
}


function renderSubstituteResult(data, constraint) {
  const resultBox = document.getElementById("resultBox");
  const resultText = document.getElementById("resultText");

  const suggestions = Array.isArray(data.suggested_replacements)
    ? data.suggested_replacements
    : [];

  if (suggestions.length === 0) {
    resultText.innerHTML = "<p>No substitutes found.</p>";
    resultBox.style.display = "block";
    return;
  }

  const recipeTitle = data.recipe?.Recipe_title || appState.currentTitle || "Recipe";
  const matched = data.matched_recipe_ingredient || "N/A";
  const score = data.matched_recipe_ingredient_score ?? 0;

  const itemsHtml = suggestions
    .map((item) => {
      const jaccard = item.similarity?.jaccard ?? 0;
      const overlap = item.similarity?.overlap_count ?? 0;
      const why = item.why_recommended || "";

      return `
        <li style="margin-bottom: 10px;">
          <strong>${item.ingredient}</strong>
          <div>Jaccard: ${jaccard} | Overlap terms: ${overlap}</div>
          <div style="font-size: 13px; color: #555;">${why}</div>
        </li>
      `;
    })
    .join("");

  const appliedConstraint = data.applied_constraint || constraint || "none";
  const constraintNote =
    appliedConstraint && appliedConstraint !== "none"
      ? `<p style="font-size: 13px; color: #666;">Applied constraint: <strong>${appliedConstraint}</strong> (filtered out ${data.constraint_filtered_out || 0} candidate(s)).</p>`
      : "";

  resultText.innerHTML = `
    <p><strong>Dish:</strong> ${recipeTitle}</p>
    <p><strong>Matched ingredient:</strong> ${matched} (score: ${score})</p>
    ${constraintNote}
    <ol style="margin-top: 12px; padding-left: 18px;">${itemsHtml}</ol>
  `;

  resultBox.style.display = "block";
}


async function fetchIngredients() {
  const dishInput = document.getElementById("dishInput");
  const dish = dishInput.value.trim();

  if (!dish) {
    setStatus("Please enter a dish name.", "error");
    return;
  }

  setStatus("Fetching ingredients...", "info");

  try {
    const url = new URL(`${API_BASE}/recipe-ingredients`);
    url.searchParams.set("title", dish);

    const response = await fetch(url.toString(), {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      const message = await parseErrorMessage(response);
      throw new Error(message);
    }

    const data = await response.json();

    appState.currentTitle = dish;
    appState.resolvedRecipeId =
      String(data.recipe?.Recipe_id || data.lookup?.resolved_recipe_id || "");

    renderIngredients(data.ingredients || []);
    setStatus(`Loaded ${data.ingredients_count || 0} ingredients.`, "success");
  } catch (error) {
    setStatus(`Could not fetch ingredients: ${error.message}`, "error");
    renderIngredients([]);
  }
}


async function findSubstitute() {
  const selectedIngredient = document.getElementById("ingredientSelect").value;
  const constraint = document.getElementById("constraintSelect").value;
  const dishInput = document.getElementById("dishInput");
  const title = (appState.currentTitle || dishInput.value || "").trim();

  if (!title) {
    setStatus("Please enter a dish name first.", "error");
    return;
  }

  if (!selectedIngredient) {
    setStatus("Please select an ingredient to replace.", "error");
    return;
  }

  setStatus("Finding substitutions...", "info");

  const payload = {
    title,
    ingredient_to_replace: selectedIngredient,
    limit: 5,
    constraint,
  };

  if (appState.resolvedRecipeId) {
    payload.recipe_id = appState.resolvedRecipeId;
  }

  try {
    const response = await fetch(`${API_BASE}/dish-replace`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const message = await parseErrorMessage(response);
      throw new Error(message);
    }

    const data = await response.json();
    renderSubstituteResult(data, constraint);
    setStatus("Substitute suggestions ready.", "success");
  } catch (error) {
    setStatus(`Could not fetch substitutes: ${error.message}`, "error");
  }
}


window.fetchIngredients = fetchIngredients;
window.findSubstitute = findSubstitute;
