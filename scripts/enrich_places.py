"""
Enrich city place data with Google Places API (New).
Fills: place_id, coordinates, address, website, opening_hours, photo_url (local path).
Photos are downloaded to public/images/places/.

Usage:
  python scripts/enrich_places.py                # process all cities
  python scripts/enrich_places.py --city tokyo   # process one city
"""

import argparse
import json
import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

BASE_URL = "https://places.googleapis.com/v1"
CITIES_SRC_DIR = Path("cities")
CITIES_OUT_DIR = Path("data/cities")
PHOTOS_DIR = Path("public/images/places")

PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
CITIES_OUT_DIR.mkdir(parents=True, exist_ok=True)


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


def enrich_city(city_key: str):
    """Enrich all places for a single city."""
    input_file = CITIES_SRC_DIR / f"{city_key}_places.json"
    output_file = CITIES_OUT_DIR / f"{city_key}.json"

    if not input_file.exists():
        print(f"  ✗ {input_file} not found, skipping")
        return

    with open(input_file, encoding="utf-8") as f:
        source = json.load(f)

    cache: dict[int, dict] = {}
    if output_file.exists():
        with open(output_file, encoding="utf-8") as f:
            cached = json.load(f)
        cache = {p["id"]: p for p in cached.get("places", [])}
        print(f"  Loaded cache: {len(cache)} previously enriched places")

    places = source["places"]
    total = len(places)
    new_count = sum(1 for p in places if p["id"] not in cache or not cache[p["id"]].get("place_id"))
    print(f"  Total: {total} places | New/unenriched: {new_count}\n")

    enriched_list = []
    api_calls = 0
    for i, place in enumerate(places):
        if place["id"] in cache and cache[place["id"]].get("place_id"):
            merged = {**place, **{k: v for k, v in cache[place["id"]].items() if k not in place or not place[k]}}
            merged["place_id"] = cache[place["id"]]["place_id"]
            merged["coordinates"] = cache[place["id"]].get("coordinates", place.get("coordinates"))
            merged["photo_url"] = cache[place["id"]].get("photo_url", "")
            merged["address"] = cache[place["id"]].get("address", "")
            merged["website"] = cache[place["id"]].get("website", "")
            merged["opening_hours"] = cache[place["id"]].get("opening_hours", [])
            print(f"  [{place['id']:02d}] {place['name']} → cached ✓")
            enriched_list.append(merged)
            continue

        try:
            enriched_place = enrich(place)
            enriched_list.append(enriched_place)
            api_calls += 1
        except requests.HTTPError as e:
            print(f"       ✗ HTTP error: {e}")
            enriched_list.append(place)
        except Exception as e:
            print(f"       ✗ unexpected error: {e}")
            enriched_list.append(place)

        if api_calls > 0 and i < total - 1:
            time.sleep(0.3)

    source["places"] = enriched_list
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(source, f, ensure_ascii=False, indent=2)

    succeeded = sum(1 for p in enriched_list if p.get("place_id"))
    print(f"\n  Done. {succeeded}/{total} enriched ({api_calls} new API calls) → {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Enrich Waypoints place data via Google Places API")
    parser.add_argument("--city", help="City key to process (e.g. 'tokyo'). Omit to process all cities.")
    args = parser.parse_args()

    if not API_KEY:
        raise EnvironmentError("Missing GOOGLE_PLACES_API_KEY in .env file")

    if args.city:
        print(f"\nEnriching city: {args.city}\n")
        enrich_city(args.city)
    else:
        city_files = sorted(CITIES_SRC_DIR.glob("*_places.json"))
        if not city_files:
            print("No city source files found in cities/. Nothing to enrich.")
            return
        print(f"\nEnriching {len(city_files)} city/cities...\n")
        for cf in city_files:
            city_key = cf.stem.replace("_places", "")
            print(f"── {city_key} ──")
            enrich_city(city_key)
            print()


if __name__ == "__main__":
    main()
