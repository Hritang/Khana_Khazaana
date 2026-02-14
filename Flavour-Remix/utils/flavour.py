import requests
import os

# Replace with your real base URL (from Postman environment)
BASE_URL = "{{baseUrl}}/molecules_data/by-commonName?commonName=vanillin&page=0&size=20"

# Store token in environment variable (recommended)
AUTH_TOKEN = "PASTE_YOUR_REAL_TOKEN_HERE"

def get_molecules_by_common_name(ingredient):
    url = f"{BASE_URL}/molecules_data/by-commonName"

    headers = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    params = {
        "commonName": ingredient,
        "page": 0,
        "size": 20
    }

    response = requests.get(url, headers=headers, params=params)

    return response.json()
