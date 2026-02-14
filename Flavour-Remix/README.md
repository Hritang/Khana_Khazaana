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
$env:FLAVORDB_AUTH_TOKEN="your_token_here"
# optional
$env:FLAVORDB_BASE_URL="http://cosylab.iiitd.edu.in:6969/flavordb"
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
