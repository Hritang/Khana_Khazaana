import os
import re
from typing import Any

import requests

DEFAULT_BASE_URL = "http://192.168.1.92:6969/flavordb"
DEFAULT_AUTH_TOKEN = "5GYS4ukGSZHEICP1lIOQBtzBLmFcDMlq279L2Y-GF159yn5M"
TIMEOUT_SECONDS = float(os.getenv("FLAVORDB_TIMEOUT_SECONDS", "15"))


class FlavorDBClientError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _get_base_url() -> str:
    return DEFAULT_BASE_URL


def _get_auth_token_and_source() -> tuple[str, str]:
    candidates = [
        ("FLAVORDB_AUTH_TOKEN", os.getenv("FLAVORDB_AUTH_TOKEN")),
        ("FOODOSCOPE_API_KEY", os.getenv("FOODOSCOPE_API_KEY")),
        ("FLAVORDB_API_KEY", os.getenv("FLAVORDB_API_KEY")),
        ("AUTH_TOKEN", os.getenv("AUTH_TOKEN")),
        ("DEFAULT_AUTH_TOKEN", DEFAULT_AUTH_TOKEN),
    ]

    token = ""
    source = ""
    for key, value in candidates:
        if value and value.strip():
            token = value
            source = key
            break

    cleaned = token.strip()
    if cleaned.lower().startswith("bearer "):
        cleaned = cleaned[7:].strip()
    return cleaned, source


def _build_headers() -> dict[str, str]:
    auth_token, _ = _get_auth_token_and_source()
    if not auth_token:
        raise FlavorDBClientError(
            (
                "Missing FlavorDB token. Set one of: "
                "FLAVORDB_AUTH_TOKEN, FOODOSCOPE_API_KEY, FLAVORDB_API_KEY, AUTH_TOKEN."
            ),
            status_code=401,
        )

    return {
        "Authorization": f"Bearer {auth_token}",
        "X-API-Key": auth_token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _request(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{_get_base_url()}{path}"

    try:
        response = requests.get(
            url,
            headers=_build_headers(),
            params=params,
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        message = f"FlavorDB request failed for {path}: HTTP {status}."
        if status == 401:
            message += " Unauthorized token."
        raise FlavorDBClientError(message, status_code=status) from exc
    except requests.RequestException as exc:
        raise FlavorDBClientError(
            f"FlavorDB request failed for {path}: {exc}",
            status_code=502,
        ) from exc

    try:
        return response.json()
    except ValueError as exc:
        raise FlavorDBClientError(
            f"FlavorDB returned non-JSON response for {path}.",
            status_code=502,
        ) from exc


def get_molecules_by_common_name(name: str, page: int = 0, size: int = 20) -> dict[str, Any]:
    return _request(
        "/molecules_data/by-commonName",
        params={
            "common_name": name,
            "page": page,
            "size": size,
        },
    )


def get_pairings_by_alias(ingredient: str) -> dict[str, Any]:
    return _request("/food/by-alias", params={"food_pair": ingredient})


def _profile_from_food_pairings(ingredient: str) -> list[str]:
    try:
        payload = get_pairings_by_alias(ingredient)
    except FlavorDBClientError as exc:
        if exc.status_code == 404:
            return []
        raise

    rows = payload.get("topSimilarEntities")
    if not isinstance(rows, list):
        return []

    signature: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue

        entity_name = row.get("entityName")
        category = row.get("category")

        if isinstance(entity_name, str) and entity_name.strip():
            signature.add(f"entity:{entity_name.strip().lower()}")
        if isinstance(category, str) and category.strip():
            signature.add(f"category:{category.strip().lower()}")

    return sorted(signature)


def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        payload.get("data"),
        payload.get("content"),
        payload.get("results"),
    ]
    nested_payload = payload.get("payload")
    if isinstance(nested_payload, dict):
        candidates.extend(
            [
                nested_payload.get("data"),
                nested_payload.get("content"),
                nested_payload.get("results"),
            ]
        )

    for value in candidates:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    return []


def _profile_tokens_from_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, str)]
    if isinstance(value, str):
        return [x.strip() for x in re.split(r"[;,]", value) if x.strip()]
    return []


def get_flavor_profile_by_ingredient(name: str) -> list[str]:
    profile: set[str] = set()

    try:
        data = get_molecules_by_common_name(name=name, page=0, size=50)
    except FlavorDBClientError as exc:
        # Some FlavorDB deployments return 400, others 404 for non-molecule ingredient names.
        # Fall back to entity-based pairing signature in both cases.
        if exc.status_code in (400, 404):
            return _profile_from_food_pairings(name)
        raise

    for item in _extract_items(data):
        tokens = []
        tokens.extend(_profile_tokens_from_value(item.get("flavorProfile")))
        tokens.extend(_profile_tokens_from_value(item.get("flavor_profile")))
        tokens.extend(_profile_tokens_from_value(item.get("fooddb_flavor_profile")))
        tokens.extend(_profile_tokens_from_value(item.get("fema_flavor_profile")))

        for token in tokens:
            if isinstance(token, str):
                cleaned = token.strip().lower()
                if cleaned:
                    profile.add(cleaned)

    if profile:
        return sorted(profile)

    return _profile_from_food_pairings(name)


def extract_pairing_candidates(payload: dict[str, Any], source_ingredient: str) -> list[str]:
    preferred_keys = {
        "food_pair",
        "foodPair",
        "ingredient",
        "pairing",
        "pairings",
        "name",
        "entityName",
        "commonName",
        "common_name",
        "aliasReadable",
        "entityAliasReadable",
    }

    raw_candidates: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in preferred_keys:
                    if isinstance(value, str):
                        raw_candidates.append(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, str):
                                raw_candidates.append(item)

                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)

    source_normalized = source_ingredient.strip().lower()
    seen: set[str] = set()
    parsed: list[str] = []

    for value in raw_candidates:
        for chunk in re.split(r"\|\||,", value):
            candidate = chunk.strip().lower()
            if not candidate:
                continue
            if candidate == source_normalized:
                continue
            if "http://" in candidate or "https://" in candidate:
                continue
            if len(candidate) > 80:
                continue
            if candidate not in seen:
                seen.add(candidate)
                parsed.append(candidate)

    return parsed


def get_runtime_config() -> dict[str, Any]:
    token, token_source = _get_auth_token_and_source()
    return {
        "base_url": _get_base_url(),
        "token_configured": bool(token_source),
        "token_source": token_source or None,
        "token_length": len(token),
        "token_preview": (f"{token[:4]}...{token[-4:]}" if len(token) >= 8 else None),
    }
