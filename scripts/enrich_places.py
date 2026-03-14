"""
Enrich japan_places.json with Google Places API (New).
Fills: place_id, coordinates, address, website, opening_hours, photo_url (local path).
Photos are downloaded to public/images/places/.

Usage:
  1. Copy .env.example to .env and add your API key
  2. pip install -r requirements.txt
  3. python scripts/enrich_places.py
"""

import json
import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
if not API_KEY:
    raise EnvironmentError("Missing GOOGLE_PLACES_API_KEY in .env file")

BASE_URL = "https://places.googleapis.com/v1"
INPUT_FILE = Path("japan_places.json")
OUTPUT_FILE = Path("data/places_enriched.json")
PHOTOS_DIR = Path("public/images/places")

PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)


def text_search(query: str) -> dict | None:
    """Search for a place and return the first result."""
    url = f"{BASE_URL}/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.location,places.formattedAddress",
    }
    payload = {
        "textQuery": query,
        "languageCode": "en",
        "maxResultCount": 1,
    }
    resp = requests.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    places = data.get("places", [])
    return places[0] if places else None


def get_place_details(place_id: str) -> dict | None:
    """Fetch detailed info for a place."""
    url = f"{BASE_URL}/places/{place_id}"
    headers = {
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": (
            "id,displayName,location,formattedAddress,"
            "websiteUri,regularOpeningHours,photos,"
            "rating,userRatingCount,primaryType"
        ),
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


def download_photo(photo_name: str, place_id: str) -> str | None:
    """Download the first available photo, return local path relative to public/."""
    url = f"{BASE_URL}/{photo_name}/media"
    params = {
        "maxHeightPx": 800,
        "maxWidthPx": 800,
        "key": API_KEY,
        "skipHttpRedirect": "true",
    }
    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        return None

    data = resp.json()
    photo_uri = data.get("photoUri")
    if not photo_uri:
        return None

    img_resp = requests.get(photo_uri)
    if img_resp.status_code != 200:
        return None

    content_type = img_resp.headers.get("content-type", "image/jpeg")
    ext = "jpg" if "jpeg" in content_type else content_type.split("/")[-1]
    filename = f"{place_id}.{ext}"
    filepath = PHOTOS_DIR / filename

    with open(filepath, "wb") as f:
        f.write(img_resp.content)

    return f"/images/places/{filename}"


def enrich(place: dict) -> dict:
    """Enrich a single place entry. Returns the updated dict."""
    name = place["name"]
    query = place.get("maps_search") or name

    print(f"  [{place['id']:02d}] {name}")

    if place.get("place_id"):
        print(f"       → already enriched, skipping")
        return place

    result = text_search(query)
    if not result:
        print(f"       ✗ not found via text search")
        return place

    place_id = result["id"]
    place["place_id"] = place_id

    loc = result.get("location", {})
    place["coordinates"] = {
        "lat": loc.get("latitude"),
        "lng": loc.get("longitude"),
    }

    details = get_place_details(place_id)
    if details:
        place["address"] = details.get("formattedAddress", place.get("address", ""))
        place["website"] = details.get("websiteUri", "")

        hours_info = details.get("regularOpeningHours", {})
        place["opening_hours"] = hours_info.get("weekdayDescriptions", [])

        if not place.get("rating") and details.get("rating"):
            place["rating"] = details["rating"]
        if not place.get("review_count") and details.get("userRatingCount"):
            place["review_count"] = details["userRatingCount"]

        photos = details.get("photos", [])
        if photos:
            photo_name = photos[0]["name"]
            local_path = download_photo(photo_name, place_id)
            if local_path:
                place["photo_url"] = local_path
                print(f"       ✓ photo saved → {local_path}")
            else:
                print(f"       ✗ photo download failed")
        else:
            print(f"       ✗ no photos available")
    else:
        print(f"       ✗ details fetch failed")

    print(f"       ✓ place_id: {place_id}")
    return place


def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        data = json.load(f)

    places = data["places"]
    total = len(places)
    print(f"\nEnriching {total} places...\n")

    enriched = []
    for i, place in enumerate(places):
        try:
            enriched_place = enrich(place)
            enriched.append(enriched_place)
        except requests.HTTPError as e:
            print(f"       ✗ HTTP error: {e}")
            enriched.append(place)
        except Exception as e:
            print(f"       ✗ unexpected error: {e}")
            enriched.append(place)

        if i < total - 1:
            time.sleep(0.3)

    data["places"] = enriched
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    succeeded = sum(1 for p in enriched if p.get("place_id"))
    print(f"\nDone. {succeeded}/{total} places enriched → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
