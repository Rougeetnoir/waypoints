# Waypoints — Japan

> A personal city guide to my favourite places in Tokyo — restaurants, cafés, vintage shops, sightseeing, and hidden corners.

**🌐 Live site → [rougeetnoir.github.io/waypoints](https://rougeetnoir.github.io/waypoints/)**

---

![Waypoints Preview](docs/images/preview.png)
<!-- Replace with an actual screenshot of the site -->

---

## Features

- **52 curated places** across Tokyo and surrounding areas
- **Category filter** — Food, Café, Shopping, Vintage, Sightseeing, Hotel, Spa
- **Real photos** fetched from Google Places API, stored locally (no external API calls at runtime)
- **Ratings & metadata** — neighbourhood, type, star rating, review count
- **Inline map links** — every card links directly to Google Maps
- **Fully static** — no server, no database, no tracking

## Tech Stack

| Layer | Tool |
|-------|------|
| Data source | Google Takeout + manual curation |
| Data enrichment | Google Places API (New) |
| Site generation | Python build script |
| Styling | Inline CSS — Cormorant Garamond + DM Mono |
| Hosting | GitHub Pages (`/docs` folder) |

## Project Structure

```
waypoints/
  japan_places.json          # Curated source data (52 places)
  scripts/
    enrich_places.py         # Fetches place details & photos via Places API
    build_site.py            # Generates docs/index.html from enriched data
  data/
    places_enriched.json     # API-enriched data (gitignored, generated locally)
  docs/                      # Built site — served by GitHub Pages
    index.html
    images/places/           # Downloaded place photos
  .env.example               # API key template
  requirements.txt
```

## Local Setup

```bash
# 1. Clone
git clone https://github.com/Rougeetnoir/waypoints.git
cd waypoints

# 2. Create virtual environment and install dependencies
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 3. Add your Google Places API key
cp .env.example .env
# Edit .env and add: GOOGLE_PLACES_API_KEY=AIza...

# 4. Enrich data (fetches place details + downloads photos)
venv/bin/python scripts/enrich_places.py

# 5. Build the site
venv/bin/python scripts/build_site.py

# 6. Preview locally
python3 -m http.server 8080 --directory docs
# Open http://localhost:8080
```

## Updating Places

1. Edit `japan_places.json` — add, remove, or update entries
2. Run `venv/bin/python scripts/enrich_places.py` to fetch new place data
3. Run `venv/bin/python scripts/build_site.py` to rebuild the site
4. Commit and push:
   ```bash
   git add . && git commit -m "update places" && git push
   ```
   GitHub Pages will redeploy automatically within 1–2 minutes.

## Google Places API Key

This project requires a **Google Places API (New)** key for data enrichment.

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Enable **Places API (New)**
3. Create an API key under **APIs & Services → Credentials**
4. Add it to `.env` as `GOOGLE_PLACES_API_KEY=...`

The API is only called during the enrichment step — the built site has no API dependency.
Estimated cost for 52 places: ~$2.50, covered by the $200/month free tier.

---

*Part of the [Waylog](https://github.com/Rougeetnoir) personal travel series.*
