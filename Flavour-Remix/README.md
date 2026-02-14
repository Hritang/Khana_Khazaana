# Flavour Remix Backend

FastAPI backend for ingredient comparison and replacement using FlavorDB.

## 1. Setup

```powershell
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Set environment variables:

```powershell
$env:FLAVORDB_AUTH_TOKEN="your_flavordb_token"
$env:RECIPEDB_AUTH_TOKEN="your_recipedb_token"
# optional overrides
$env:FLAVORDB_BASE_URL="http://192.168.1.92:6969/flavordb"
$env:RECIPEDB_BASE_URL="http://cosylab.iiitd.edu.in:6969"
# optional: comma-separated frontend origins for CORS
$env:CORS_ALLOW_ORIGINS="http://localhost:5173,http://localhost:3000"
```

## 2. Run

```powershell
uvicorn main:app --reload
```

Swagger UI:

```text
http://127.0.0.1:8000/docs
```

## 3. Endpoints

- `GET /flavor?name=ginger`
- `GET /compare?ingredient1=ginger&ingredient2=galangal`
- `GET /replace?ingredient=butter&limit=5`
- `GET /replace?ingredient=butter&candidates=olive oil,ghee,yogurt&limit=3`
- `GET /recipe-ingredients?title=Egyptian Lentil Soup`
- `GET /recipe-ingredients?recipe_id=2610`
- `POST /dish-replace`
- `POST /replace-in-recipe`

Example request body for `POST /replace-in-recipe`:

```json
{
  "recipe_id": "2610",
  "ingredient_to_replace": "cumin",
  "limit": 5
}
```

Or with title lookup:

```json
{
  "title": "Egyptian Lentil Soup",
  "ingredient_to_replace": "cumin",
  "limit": 5
}
```

Typical two-step flow:

1. Get dish ingredients:

```text
GET /recipe-ingredients?title=Egyptian Lentil Soup
```

2. Replace missing ingredient in that recipe:

```json
{
  "recipe_id": "2610",
  "ingredient_to_replace": "cumin",
  "limit": 5
}
```

Single-step flow (frontend-friendly):

```json
{
  "title": "Egyptian Lentil Soup",
  "ingredient_to_replace": "cumin",
  "limit": 5
}
```

Send this body to:

```text
POST /dish-replace
```

## 4. Frontend Integration

Set frontend API base URL:

- Vite: `VITE_API_BASE_URL=http://127.0.0.1:8000`
- React CRA: `REACT_APP_API_BASE_URL=http://127.0.0.1:8000`
- Next.js: `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`

Example API helper (`fetch`):

```javascript
const API_BASE =
  import.meta?.env?.VITE_API_BASE_URL ||
  process.env.REACT_APP_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  "http://127.0.0.1:8000";

export async function getRecipeIngredientsByTitle(title) {
  const url = new URL(`${API_BASE}/recipe-ingredients`);
  url.searchParams.set("title", title);
  const res = await fetch(url, { headers: { Accept: "application/json" } });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getDishReplacements(payload) {
  const res = await fetch(`${API_BASE}/dish-replace`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

Frontend flow:

1. Call `getRecipeIngredientsByTitle(dishName)` and show `ingredients`.
2. User picks missing ingredient.
3. Call `getDishReplacements({ title: dishName, ingredient_to_replace, limit: 5 })`.
4. Render `suggested_replacements`.

For static `frontend/dashboard.html`, API base defaults to same-origin (or `http://127.0.0.1:8000` when opened as file). You can override in browser console:

```javascript
localStorage.setItem("FLAVOUR_REMIX_API_BASE", "http://127.0.0.1:8010");
```
