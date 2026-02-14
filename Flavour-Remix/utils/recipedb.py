import os
import time
from typing import Any

import requests

DEFAULT_BASE_URL = "http://cosylab.iiitd.edu.in:6969"
TIMEOUT_SECONDS = float(os.getenv("RECIPEDB_TIMEOUT_SECONDS", "20"))


class RecipeDBClientError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _get_base_url() -> str:
    return os.getenv("RECIPEDB_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _get_auth_token_and_source() -> tuple[str, str]:
    candidates = [
        ("RECIPEDB_AUTH_TOKEN", os.getenv("RECIPEDB_AUTH_TOKEN")),
        ("FLAVORDB_AUTH_TOKEN", os.getenv("FLAVORDB_AUTH_TOKEN")),
        ("FOODOSCOPE_API_KEY", os.getenv("FOODOSCOPE_API_KEY")),
        ("FLAVORDB_API_KEY", os.getenv("FLAVORDB_API_KEY")),
        ("AUTH_TOKEN", os.getenv("AUTH_TOKEN")),
    ]

    token = ""
    source = ""
    for key, value in candidates:
        if value and value.strip():
            token = value.strip()
            source = key
            break

    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    return token, source


def _build_headers() -> dict[str, str]:
    token, _ = _get_auth_token_and_source()
    if not token:
        raise RecipeDBClientError(
            (
                "Missing RecipeDB token. Set one of: RECIPEDB_AUTH_TOKEN, "
                "FLAVORDB_AUTH_TOKEN, FOODOSCOPE_API_KEY, FLAVORDB_API_KEY, AUTH_TOKEN."
            ),
            status_code=401,
        )

    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _extract_api_error(response: requests.Response | None) -> str | None:
    if response is None:
        return None

    try:
        payload = response.json()
    except ValueError:
        return None

    if not isinstance(payload, dict):
        return None

    for key in ("error", "message", "detail"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def _looks_like_auth_error(error_text: str | None) -> bool:
    if not error_text:
        return False

    lowered = error_text.lower()
    auth_markers = [
        "invalid api key",
        "api key is not provided",
        "apikey is not provided",
        "only bearer token is allowed",
        "not enough tokens",
        "unauthorized",
        "forbidden",
        "token expired",
    ]
    return any(marker in lowered for marker in auth_markers)


def _request(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{_get_base_url()}{path}"

    response: requests.Response | None = None
    for attempt in range(2):
        try:
            response = requests.get(
                url,
                headers=_build_headers(),
                params=params,
                timeout=TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise RecipeDBClientError(
                f"RecipeDB request failed for {path}: {exc}",
                status_code=502,
            ) from exc

        if response.status_code != 429:
            break

        if attempt == 0:
            retry_after = response.headers.get("Retry-After")
            delay_seconds = 1.0
            if retry_after:
                try:
                    delay_seconds = max(float(retry_after), 0.5)
                except ValueError:
                    delay_seconds = 1.0
            time.sleep(delay_seconds)
            continue

    try:
        if response is None:
            raise RecipeDBClientError(
                f"RecipeDB request failed for {path}: empty response.",
                status_code=502,
            )
        response.raise_for_status()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        api_error = _extract_api_error(exc.response)
        if _looks_like_auth_error(api_error):
            status = 401

        message = f"RecipeDB request failed for {path}: HTTP {status}."
        if api_error:
            message += f" {api_error}"

        raise RecipeDBClientError(
            message,
            status_code=status,
        ) from exc

    try:
        return response.json()
    except ValueError as exc:
        raise RecipeDBClientError(
            f"RecipeDB returned non-JSON response for {path}.",
            status_code=502,
        ) from exc


def search_recipes_by_title(title: str, page: int = 1, limit: int = 10) -> dict[str, Any]:
    return _request(
        "/recipe2-api/recipebyingredient/by-ingredients-categories-title",
        params={"title": title, "page": page, "limit": limit},
    )


def get_recipe_by_id(recipe_id: str) -> dict[str, Any]:
    return _request(f"/recipe2-api/search-recipe/{recipe_id}")


def _extract_recipe_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[Any] = [
        payload.get("recipes"),
        payload.get("data"),
    ]

    nested = payload.get("payload")
    if isinstance(nested, dict):
        candidates.extend([nested.get("data"), nested.get("recipes")])

    for value in candidates:
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]

    return []


def normalize_recipe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("recipe"), dict) and isinstance(payload.get("ingredients"), list):
        recipe = payload.get("recipe", {})
        ingredients = [x for x in payload.get("ingredients", []) if isinstance(x, dict)]
        return {"recipe": recipe, "ingredients": ingredients}

    nested = payload.get("payload")
    if isinstance(nested, dict):
        data = nested.get("data")
        if isinstance(data, dict):
            recipe = dict(data)
            ingredients = recipe.get("ingredients", [])
            if isinstance(ingredients, list):
                ingredients = [x for x in ingredients if isinstance(x, dict)]
            else:
                ingredients = []
            return {"recipe": recipe, "ingredients": ingredients}

    return {"recipe": {}, "ingredients": []}


def get_recipe_with_ingredients(
    recipe_id: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    if not recipe_id and not title:
        raise RecipeDBClientError(
            "Provide at least one of: recipe_id or title.",
            status_code=400,
        )

    if recipe_id:
        detail = get_recipe_by_id(str(recipe_id))
        normalized = normalize_recipe_payload(detail)
        if normalized["recipe"]:
            return normalized
        raise RecipeDBClientError(
            f"Recipe {recipe_id} not found or missing details.",
            status_code=404,
        )

    search_payload = search_recipes_by_title(title=str(title), page=1, limit=1)
    matches = _extract_recipe_list(search_payload)
    if not matches:
        raise RecipeDBClientError(
            f"No recipes found for title '{title}'.",
            status_code=404,
        )

    resolved_id = (
        matches[0].get("Recipe_id")
        or matches[0].get("recipe_id")
        or matches[0].get("id")
    )
    if not resolved_id:
        raise RecipeDBClientError(
            f"Could not resolve recipe id for title '{title}'.",
            status_code=502,
        )

    detail = get_recipe_by_id(str(resolved_id))
    normalized = normalize_recipe_payload(detail)
    normalized["lookup"] = {
        "type": "title",
        "value": title,
        "resolved_recipe_id": str(resolved_id),
    }
    return normalized


def extract_recipe_ingredient_names(recipe_bundle: dict[str, Any]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    def add_name(value: Any) -> None:
        if not isinstance(value, str):
            return
        cleaned = value.strip()
        if not cleaned:
            return
        key = cleaned.lower()
        if key in seen:
            return
        seen.add(key)
        names.append(cleaned)

    for item in recipe_bundle.get("ingredients", []):
        if isinstance(item, dict):
            add_name(
                item.get("ingredient")
                or item.get("name")
                or item.get("ingredient_name")
                or item.get("ingredient_Phrase")
            )
        elif isinstance(item, str):
            add_name(item)

    recipe = recipe_bundle.get("recipe", {})
    if isinstance(recipe, dict):
        for item in recipe.get("ingredients", []):
            if isinstance(item, dict):
                add_name(item.get("ingredient") or item.get("name"))
            elif isinstance(item, str):
                add_name(item)

    return names
