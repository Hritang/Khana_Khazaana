from fastapi import FastAPI
import requests

app = FastAPI()

# Replace with your real base URL
FLAVOR_BASE_URL = "PASTE_FLAVORDB_BASE_URL"
AUTH_TOKEN = "PASTE_YOUR_BEARER_TOKEN"

@app.get("/")
def root():
    return {"message": "Flavor Remix Backend Running"}

@app.get("/flavor")
def get_flavor(ingredient: str):
    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}"
    }

    response = requests.get(
        f"{FLAVOR_BASE_URL}/YOUR_ENDPOINT_PATH",
        headers=headers,
        params={"name": ingredient}
    )

    return response.json()
