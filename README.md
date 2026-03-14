# Waypoints — Japan

> A personal city guide to my favourite places in Tokyo — restaurants, cafés, vintage shops, sightseeing, and hidden corners.

**🌐 Live site → [rougeetnoir.github.io/waypoints](https://rougeetnoir.github.io/waypoints/)**

---

![Waypoints Preview](docs/images/preview.png)
<!-- Replace with an actual screenshot of the site -->

---

## Features

- **53 curated places** across Tokyo and surrounding areas
- **Category filter** — Food, Café, Shopping, Vintage, Sightseeing, Hotel, Spa
- **Real photos** fetched from Google Places API, stored locally (no external API calls at runtime)
- **Ratings & metadata** — neighbourhood, type, star rating, review count
- **Inline map links** — every card links directly to Google Maps
- **Fully static** — no server, no database, no tracking
- **Local admin UI** — browser-based interface to add/delete/edit places and deploy in one click

## Tech Stack

| Layer | Tool |
|-------|------|
| Data source | Google Takeout + manual curation |
| Data enrichment | Google Places API (New) |
| Site generation | Python build script |
| Admin UI | Flask (local only, `localhost:5001`) |
| Styling | Inline CSS — Cormorant Garamond + DM Mono |
| Hosting | GitHub Pages (`/docs` folder) |

## Project Structure

```
waypoints/
  japan_places.json          # Curated source data
  scripts/
    enrich_places.py         # Fetches place details & photos via Places API (incremental)
    build_site.py            # Generates docs/index.html from enriched data
    manage.py                # CLI: add / delete / list / search places
    admin.py                 # Local admin web UI (Flask, localhost:5001)
  data/
    places_enriched.json     # API-enriched data cache
  docs/                      # Built site — served by GitHub Pages
    index.html
    images/places/           # Downloaded place photos
  update.sh                  # One-command: enrich → build → commit → push
  .env.example               # API key + admin password template
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

### Option A — Admin UI (recommended)

```bash
venv/bin/python scripts/admin.py
# Open http://localhost:5001  (default password: waypoints)
```

- Add places by pasting a Google Maps URL — name is auto-extracted
- Delete or edit category/notes/neighborhood inline
- Click **Build & Deploy** to enrich, rebuild, and push in one step

### Option B — One-click script

```bash
./update.sh "add new cafe in Shimokitazawa"
```

### Option C — Manual

```bash
venv/bin/python scripts/manage.py add          # interactive CLI
venv/bin/python scripts/enrich_places.py       # incremental — only new places call the API
venv/bin/python scripts/build_site.py
git add . && git commit -m "update" && git push
```

GitHub Pages redeploys automatically within 1–2 minutes of each push.

## Google Places API Key

This project requires a **Google Places API (New)** key for data enrichment.

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Enable **Places API (New)**
3. Create an API key under **APIs & Services → Credentials**
4. Add it to `.env` as `GOOGLE_PLACES_API_KEY=...`

The API is only called during the enrichment step — the built site has no API dependency.
Estimated cost for 53 places: ~$2.50, covered by the $200/month free tier.
The enrichment script is incremental — only newly added places trigger API calls.

---

*Part of the [Waylog](https://github.com/Rougeetnoir) personal travel series.*
