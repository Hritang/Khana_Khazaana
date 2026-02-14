import os
import re
from difflib import SequenceMatcher
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from utils.flavour import (
    FlavorDBClientError,
    extract_pairing_candidates,
    get_flavor_profile_by_ingredient,
    get_molecules_by_common_name,
    get_pairings_by_alias,
    get_runtime_config,
)
from utils.recipedb import (
    RecipeDBClientError,
    extract_recipe_ingredient_names,
    get_recipe_with_ingredients,
)
from utils.scoring import calculate_similarity

app = FastAPI(title="Flavor Remix Backend", version="0.1.0")


def _get_cors_origins() -> list[str]:
    raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if raw_origins:
        return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]

    return [
        "null",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReplaceInRecipeRequest(BaseModel):
    recipe_id: str | None = Field(
        default=None,
        description="RecipeDB Recipe_id value (e.g., 2610).",
    )
    title: str | None = Field(
        default=None,
        description="Recipe title fallback lookup when recipe_id is not provided.",
    )
    ingredient_to_replace: str = Field(
        ...,
        min_length=1,
        description="Ingredient in recipe to replace.",
    )
    limit: int = Field(default=5, ge=1, le=20)
    candidates: list[str] | None = Field(
        default=None,
        description="Optional explicit candidate ingredients.",
    )


class DishReplaceRequest(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        description="Recipe title to search in RecipeDB.",
    )
    ingredient_to_replace: str = Field(
        ...,
        min_length=1,
        description="Ingredient in recipe to replace.",
    )
    limit: int = Field(default=5, ge=1, le=20)
    candidates: list[str] | None = Field(
        default=None,
        description="Optional explicit candidate ingredients.",
    )
    recipe_id: str | None = Field(
        default=None,
        description="Optional RecipeDB Recipe_id override.",
    )


def _normalize_ingredient_name(value: str) -> str:
    lowered = value.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(cleaned.split())


def _match_recipe_ingredient(target: str, recipe_ingredients: list[str]) -> tuple[str | None, float]:
    target_norm = _normalize_ingredient_name(target)
    if not target_norm:
        return None, 0.0

    for name in recipe_ingredients:
        if _normalize_ingredient_name(name) == target_norm:
            return name, 1.0

    for name in recipe_ingredients:
        name_norm = _normalize_ingredient_name(name)
        if target_norm in name_norm or name_norm in target_norm:
            return name, 0.9

    best_name: str | None = None
    best_score = 0.0
    target_tokens = set(target_norm.split())

    for name in recipe_ingredients:
        candidate_norm = _normalize_ingredient_name(name)
        if not candidate_norm:
            continue

        candidate_tokens = set(candidate_norm.split())
        overlap = len(target_tokens.intersection(candidate_tokens))
        token_score = overlap / max(len(target_tokens), len(candidate_tokens), 1)
        sequence_score = SequenceMatcher(None, target_norm, candidate_norm).ratio()
        score = max(token_score, sequence_score)

        if score > best_score:
            best_score = score
            best_name = name

    if best_name and best_score >= 0.72:
        return best_name, round(best_score, 4)

    return None, 0.0


def _build_why_recommended(similarity: dict[str, Any]) -> str:
    overlap_count = int(similarity.get("overlap_count", 0))
    jaccard = similarity.get("jaccard", 0.0)
    overlap_terms = similarity.get("overlap_terms", [])

    if overlap_count <= 0:
        return f"Low confidence: no shared flavor terms (Jaccard {jaccard})."

    if isinstance(overlap_terms, list) and overlap_terms:
        top_terms = ", ".join(str(x) for x in overlap_terms[:3])
        return (
            f"Shared {overlap_count} flavor terms (Jaccard {jaccard}), "
            f"including: {top_terms}."
        )

    return f"Shared {overlap_count} flavor terms (Jaccard {jaccard})."


def _rank_replacements(
    target_profile: list[str],
    candidate_pool: list[str],
    *,
    skip_ingredient: str | None = None,
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    skip_norm = skip_ingredient.strip().lower() if isinstance(skip_ingredient, str) else ""

    for candidate in candidate_pool:
        candidate_norm = candidate.strip().lower()
        if skip_norm and candidate_norm == skip_norm:
            continue

        try:
            candidate_profile = get_flavor_profile_by_ingredient(candidate)
        except FlavorDBClientError:
            continue

        if not candidate_profile:
            continue

        similarity = calculate_similarity(target_profile, candidate_profile)
        ranked.append(
            {
                "ingredient": candidate,
                "similarity": similarity,
                "candidate_profile_size": len(candidate_profile),
                "why_recommended": _build_why_recommended(similarity),
            }
        )

    ranked.sort(
        key=lambda x: (x["similarity"]["jaccard"], x["similarity"]["overlap_count"]),
        reverse=True,
    )
    return ranked


@app.get("/")
def root() -> dict:
    return {"message": "Flavor Remix Backend Running"}


@app.get("/flavor")
def flavor(name: str = Query(..., min_length=1)) -> dict:
    try:
        data = get_molecules_by_common_name(name)
    except FlavorDBClientError as exc:
        if exc.status_code == 404:
            fallback_profile = get_flavor_profile_by_ingredient(name)
            if fallback_profile:
                return {
                    "ingredient": name,
                    "results": [
                        {
                            "common_name": name,
                            "flavor_profile": fallback_profile,
                            "source": "food_pairings_fallback",
                        }
                    ],
                }
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    items = data.get("data")
    if not isinstance(items, list):
        items = data.get("content")
    if not isinstance(items, list):
        items = []

    results = []
    for item in items:
        results.append(
            {
                "common_name": item.get("commonName") or item.get("common_name"),
                "flavor_profile": (
                    item.get("flavorProfile")
                    or item.get("flavor_profile")
                    or item.get("fooddb_flavor_profile")
                    or []
                ),
            }
        )

    return {"ingredient": name, "results": results}


@app.get("/compare")
def compare(
    ingredient1: str = Query(..., min_length=1),
    ingredient2: str = Query(..., min_length=1),
) -> dict:
    try:
        profile1 = get_flavor_profile_by_ingredient(ingredient1)
        profile2 = get_flavor_profile_by_ingredient(ingredient2)
    except FlavorDBClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    similarity = calculate_similarity(profile1, profile2)

    return {
        "ingredient1": ingredient1,
        "ingredient2": ingredient2,
        "profile1": profile1,
        "profile2": profile2,
        "similarity": similarity,
    }


@app.get("/replace")
def suggest_replacements(
    ingredient: str = Query(..., min_length=1),
    limit: int = Query(5, ge=1, le=20),
    candidates: str | None = Query(
        default=None,
        description="Optional comma-separated candidate ingredients.",
    ),
) -> dict:
    try:
        target_profile = get_flavor_profile_by_ingredient(ingredient)
    except FlavorDBClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    if not target_profile:
        raise HTTPException(
            status_code=404,
            detail=f"No flavor profile found for ingredient '{ingredient}'.",
        )

    manual_candidates: list[str] = []
    if candidates:
        manual_candidates = [x.strip() for x in candidates.split(",") if x.strip()]

    api_candidates: list[str] = []
    if not manual_candidates:
        try:
            raw_pairings = get_pairings_by_alias(ingredient)
            api_candidates = extract_pairing_candidates(raw_pairings, ingredient)
        except FlavorDBClientError:
            api_candidates = []

    candidate_pool = manual_candidates or api_candidates
    if not candidate_pool:
        raise HTTPException(
            status_code=404,
            detail=(
                "No replacement candidates were found. "
                "Try adding 'candidates=ginger,galangal,...' in query."
            ),
        )

    ranked = _rank_replacements(target_profile, candidate_pool)

    return {
        "target_ingredient": ingredient,
        "target_profile_size": len(target_profile),
        "candidates_evaluated": len(ranked),
        "suggested_replacements": ranked[:limit],
    }


@app.get("/recipe-ingredients")
def recipe_ingredients(
    title: str | None = Query(
        default=None,
        min_length=1,
        description="Recipe title to search in RecipeDB.",
    ),
    recipe_id: str | None = Query(
        default=None,
        min_length=1,
        description="RecipeDB Recipe_id value (e.g., 2610).",
    ),
) -> dict:
    if not recipe_id and not title:
        raise HTTPException(status_code=400, detail="Provide recipe_id or title.")

    try:
        recipe_bundle = get_recipe_with_ingredients(recipe_id=recipe_id, title=title)
    except RecipeDBClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    recipe_ingredients = extract_recipe_ingredient_names(recipe_bundle)
    if not recipe_ingredients:
        raise HTTPException(
            status_code=404,
            detail="Could not extract ingredients from recipe.",
        )

    recipe = recipe_bundle.get("recipe", {})
    return {
        "recipe": {
            "Recipe_id": recipe.get("Recipe_id"),
            "Recipe_title": recipe.get("Recipe_title"),
            "Region": recipe.get("Region"),
            "total_time": recipe.get("total_time"),
        },
        "lookup": recipe_bundle.get("lookup"),
        "ingredients_count": len(recipe_ingredients),
        "ingredients": recipe_ingredients,
    }


@app.post("/dish-replace")
def dish_replace(payload: DishReplaceRequest) -> dict:
    replace_payload = ReplaceInRecipeRequest(
        recipe_id=payload.recipe_id,
        title=payload.title,
        ingredient_to_replace=payload.ingredient_to_replace,
        limit=payload.limit,
        candidates=payload.candidates,
    )
    return replace_in_recipe(replace_payload)


@app.post("/replace-in-recipe")
def replace_in_recipe(payload: ReplaceInRecipeRequest) -> dict:
    if not payload.recipe_id and not payload.title:
        raise HTTPException(status_code=400, detail="Provide recipe_id or title.")

    try:
        recipe_bundle = get_recipe_with_ingredients(
            recipe_id=payload.recipe_id,
            title=payload.title,
        )
    except RecipeDBClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    recipe_ingredients = extract_recipe_ingredient_names(recipe_bundle)
    if not recipe_ingredients:
        raise HTTPException(
            status_code=404,
            detail="Could not extract ingredients from recipe.",
        )

    matched_ingredient, matched_score = _match_recipe_ingredient(
        payload.ingredient_to_replace,
        recipe_ingredients,
    )
    if not matched_ingredient:
        raise HTTPException(
            status_code=404,
            detail={
                "message": (
                    f"Ingredient '{payload.ingredient_to_replace}' not found in recipe."
                ),
                "recipe_ingredients": recipe_ingredients,
            },
        )

    try:
        target_profile = get_flavor_profile_by_ingredient(matched_ingredient)
    except FlavorDBClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    if not target_profile:
        raise HTTPException(
            status_code=404,
            detail=f"No flavor profile found for ingredient '{matched_ingredient}'.",
        )

    manual_candidates: list[str] = []
    if payload.candidates:
        manual_candidates = [x.strip() for x in payload.candidates if x and x.strip()]

    api_candidates: list[str] = []
    if not manual_candidates:
        try:
            raw_pairings = get_pairings_by_alias(matched_ingredient)
            api_candidates = extract_pairing_candidates(raw_pairings, matched_ingredient)
        except FlavorDBClientError:
            api_candidates = []

    candidate_pool = manual_candidates or api_candidates
    if not candidate_pool:
        raise HTTPException(
            status_code=404,
            detail="No replacement candidates were found.",
        )

    ranked = _rank_replacements(
        target_profile,
        candidate_pool,
        skip_ingredient=matched_ingredient,
    )

    recipe = recipe_bundle.get("recipe", {})
    return {
        "recipe": {
            "Recipe_id": recipe.get("Recipe_id"),
            "Recipe_title": recipe.get("Recipe_title"),
            "Region": recipe.get("Region"),
            "total_time": recipe.get("total_time"),
        },
        "lookup": recipe_bundle.get("lookup"),
        "ingredient_to_replace": payload.ingredient_to_replace,
        "matched_recipe_ingredient": matched_ingredient,
        "matched_recipe_ingredient_score": matched_score,
        "recipe_ingredients": recipe_ingredients,
        "target_profile_size": len(target_profile),
        "candidates_evaluated": len(ranked),
        "suggested_replacements": ranked[: payload.limit],
    }


@app.get("/health/flavordb")
def flavordb_health() -> dict:
    config = get_runtime_config()
    probe_ingredient = "maltose"
    try:
        sample = get_molecules_by_common_name(probe_ingredient, size=1)
    except FlavorDBClientError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "message": str(exc),
                "config": config,
                "probe_ingredient": probe_ingredient,
            },
        ) from exc

    sample_items = sample.get("data")
    if not isinstance(sample_items, list):
        sample_items = sample.get("content")
    if not isinstance(sample_items, list):
        sample_items = []

    return {
        "message": "FlavorDB connection is healthy.",
        "config": config,
        "probe_ingredient": probe_ingredient,
        "sample_items": len(sample_items),
    }
