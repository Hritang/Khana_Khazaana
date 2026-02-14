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

const DEFAULT_VISUAL_TITLE = "Flavor Intelligent Substitution";
const DEFAULT_VISUAL_DESCRIPTION =
  "Enter a dish, pick the missing ingredient, apply a dietary constraint, and get ranked replacements based on FlavorDB similarity.";


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


function resetRecipePreview() {
  const visualTitle = document.getElementById("visualTitle");
  const visualDescription = document.getElementById("visualDescription");
  const recipeMeta = document.getElementById("recipeMeta");
  const recipeMetaBadges = document.getElementById("recipeMetaBadges");
  const recipeIngredientPreview = document.getElementById("recipeIngredientPreview");
  const recipeIngredientNote = document.getElementById("recipeIngredientNote");

  if (visualTitle) visualTitle.textContent = DEFAULT_VISUAL_TITLE;
  if (visualDescription) visualDescription.textContent = DEFAULT_VISUAL_DESCRIPTION;
  if (recipeMeta) recipeMeta.style.display = "none";
  if (recipeMetaBadges) recipeMetaBadges.innerHTML = "";
  if (recipeIngredientPreview) recipeIngredientPreview.innerHTML = "";
  if (recipeIngredientNote) recipeIngredientNote.textContent = "";
}


function renderRecipePreview(data) {
  const visualTitle = document.getElementById("visualTitle");
  const visualDescription = document.getElementById("visualDescription");
  const recipeMeta = document.getElementById("recipeMeta");
  const recipeMetaBadges = document.getElementById("recipeMetaBadges");
  const recipeIngredientPreview = document.getElementById("recipeIngredientPreview");
  const recipeIngredientNote = document.getElementById("recipeIngredientNote");

  if (!visualTitle || !visualDescription || !recipeMeta || !recipeMetaBadges || !recipeIngredientPreview || !recipeIngredientNote) {
    return;
  }

  const recipe = data?.recipe || {};
  const ingredients = Array.isArray(data?.ingredients) ? data.ingredients : [];

  const recipeTitle = recipe.Recipe_title || appState.currentTitle || "Selected Recipe";
  visualTitle.textContent = recipeTitle;

  const summaryParts = [];
  if (recipe.Region) summaryParts.push(`Region: ${recipe.Region}`);
  if (recipe.Sub_region) summaryParts.push(`Sub-region: ${recipe.Sub_region}`);
  if (recipe.Continent) summaryParts.push(`Continent: ${recipe.Continent}`);
  if (recipe.Source) summaryParts.push(`Source: ${recipe.Source}`);
  visualDescription.textContent = summaryParts.length
    ? summaryParts.join(" | ")
    : "Recipe metadata loaded from RecipeDB.";

  const badges = [];
  if (recipe.total_time) badges.push(`Total: ${recipe.total_time}`);
  if (recipe.prep_time) badges.push(`Prep: ${recipe.prep_time}`);
  if (recipe.cook_time) badges.push(`Cook: ${recipe.cook_time}`);
  if (recipe.servings) badges.push(`Servings: ${recipe.servings}`);
  if (recipe.Recipe_id) badges.push(`ID: ${recipe.Recipe_id}`);

  recipeMetaBadges.innerHTML = badges
    .slice(0, 6)
    .map((badge) => `<span class="meta-badge">${badge}</span>`)
    .join("");

  const previewCount = 8;
  const previewItems = ingredients.slice(0, previewCount);
  recipeIngredientPreview.innerHTML = previewItems
    .map((item) => `<li class="recipe-ingredient-item">${item}</li>`)
    .join("");

  if (ingredients.length > previewCount) {
    recipeIngredientNote.textContent = `+${ingredients.length - previewCount} more ingredient(s)`;
  } else {
    recipeIngredientNote.textContent = `${ingredients.length} ingredient(s) total`;
  }

  recipeMeta.style.display = "block";
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


function cleanFlavorToken(token) {
  if (typeof token !== "string") return "";
  return token
    .replace(/^category:/i, "")
    .replace(/^entity:/i, "")
    .replace(/_/g, " ")
    .trim();
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
  const resultsPlaceholder = document.getElementById("resultsPlaceholder");

  const suggestions = Array.isArray(data.suggested_replacements)
    ? data.suggested_replacements
    : [];

  if (suggestions.length === 0) {
    resultText.innerHTML = "<p>No substitutes found.</p>";
    resultBox.style.display = "block";
    if (resultsPlaceholder) resultsPlaceholder.style.display = "none";
    return;
  }

  const recipeTitle = data.recipe?.Recipe_title || appState.currentTitle || "Recipe";
  const matched = data.matched_recipe_ingredient || "N/A";
  const score = data.matched_recipe_ingredient_score ?? 0;

  const itemsHtml = suggestions
    .map((item, index) => {
      const jaccard = item.similarity?.jaccard ?? 0;
      const matchPercent = Math.round(jaccard * 100);
      const overlap = item.similarity?.overlap_count ?? 0;
      const why = item.why_recommended || "";
      const overlapTerms = Array.isArray(item.similarity?.overlap_terms)
        ? item.similarity.overlap_terms
        : [];
      const chips = overlapTerms
        .map(cleanFlavorToken)
        .filter(Boolean)
        .slice(0, 4);

      const chipHtml = chips.length
        ? chips.map((chip) => `<span class="flavor-chip">${chip}</span>`).join("")
        : `<span class="flavor-chip">No overlap terms</span>`;

      return `
        <article class="suggestion-card">
          <div class="rank-line">
            <span class="rank-id">#${index + 1}</span>
          </div>
          <h3 class="ingredient-name">${item.ingredient}</h3>
          <p class="match-score">${matchPercent}% Match</p>
          <p class="meta-line">Jaccard: ${jaccard} | Overlap terms: ${overlap}</p>
          <div class="chip-list">${chipHtml}</div>
          <p class="why-line">${why}</p>
        </article>
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
    <div class="suggestion-grid">${itemsHtml}</div>
  `;

  resultBox.style.display = "block";
  if (resultsPlaceholder) resultsPlaceholder.style.display = "none";
}


async function fetchIngredients() {
  const dishInput = document.getElementById("dishInput");
  const dish = dishInput.value.trim();
  const resultBox = document.getElementById("resultBox");
  const resultsPlaceholder = document.getElementById("resultsPlaceholder");

  if (!dish) {
    setStatus("Please enter a dish name.", "error");
    return;
  }

  setStatus("Fetching ingredients...", "info");
  if (resultBox) resultBox.style.display = "none";
  if (resultsPlaceholder) resultsPlaceholder.style.display = "block";
  const visualTitle = document.getElementById("visualTitle");
  const visualDescription = document.getElementById("visualDescription");
  if (visualTitle) visualTitle.textContent = dish || DEFAULT_VISUAL_TITLE;
  if (visualDescription) visualDescription.textContent = "Fetching recipe details...";

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
    renderRecipePreview(data);
    setStatus(`Loaded ${data.ingredients_count || 0} ingredients.`, "success");
  } catch (error) {
    setStatus(`Could not fetch ingredients: ${error.message}`, "error");
    renderIngredients([]);
    resetRecipePreview();
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


function setupConstraintChips() {
  const chips = document.querySelectorAll(".constraint-chip");
  const select = document.getElementById("constraintSelect");
  if (!chips.length || !select) return;

  chips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const value = chip.getAttribute("data-constraint");
      if (!value) return;

      select.value = value;
      chips.forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
    });
  });
}


function setupTopNavActive() {
  const topNavItems = document.querySelectorAll(".top-nav .nav-item");
  if (!topNavItems.length) return;

  topNavItems.forEach((item) => {
    item.addEventListener("click", () => {
      const href = item.getAttribute("href") || "";
      if (href === "#" || href.startsWith("#") || href.endsWith("dashboard.html")) {
        topNavItems.forEach((other) => other.classList.remove("active"));
        item.classList.add("active");
      }
    });
  });
}


window.addEventListener("DOMContentLoaded", () => {
  setupConstraintChips();
  setupTopNavActive();
  resetRecipePreview();
});


window.fetchIngredients = fetchIngredients;
window.findSubstitute = findSubstitute;
