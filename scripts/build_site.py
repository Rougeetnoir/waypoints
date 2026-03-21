"""
Build the Waypoints static site from enriched places data.
Outputs to docs/ folder — ready for GitHub Pages.

Usage: python scripts/build_site.py
"""

import json
import shutil
from pathlib import Path
from collections import Counter

CITIES_DIR = Path("data/cities")
PHOTOS_SRC = Path("public/images/places")
OUTPUT_DIR = Path("docs")
PHOTOS_DST = OUTPUT_DIR / "images" / "places"

EMOJIS = {
    "food": "🍜", "cafe": "☕", "shopping": "🛍", "vintage": "👗",
    "sightseeing": "⛩", "hotel": "🏨", "spa": "♨️", "neighborhood": "🏘", "other": "📍",
}
CAT_ORDER = ["food", "cafe", "shopping", "vintage", "sightseeing", "hotel", "spa", "neighborhood", "other"]

CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#F7F3ED;--surface:#FEFCF9;--ink:#1A1612;--ink-mid:#5C5650;
  --ink-light:#9C958E;--accent:#C4432A;--border:rgba(200,185,168,0.4);
  --font-d:'Cormorant',serif;--font-b:'Cormorant Garamond',serif;
  --font-m:'DM Sans','Noto Sans JP',sans-serif;--t:.22s ease;
}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--ink);font-family:var(--font-b);
  font-size:18px;line-height:1.6;-webkit-font-smoothing:antialiased}
/* STICKY HEADER */
.sticky-header{position:sticky;top:0;z-index:100;background:var(--bg)}
/* NAV */
.nav{background:var(--bg);
  border-bottom:1px solid var(--border);padding:.85rem 2rem;
  display:flex;align-items:center;gap:.6rem;flex-wrap:wrap}
.nav-brand{font-family:var(--font-m);font-size:.7rem;letter-spacing:.18em;
  text-transform:uppercase;color:var(--ink);text-decoration:none;margin-right:.6rem}
.city-switcher{display:flex;gap:.35rem;overflow-x:auto;scrollbar-width:none;flex:1;min-width:0}
.city-switcher::-webkit-scrollbar{display:none}
.city-btn{flex-shrink:0;font-family:var(--font-m);font-size:.6rem;letter-spacing:.08em;
  text-transform:uppercase;padding:.28rem .75rem;border:1px solid var(--border);
  border-radius:100px;background:transparent;color:var(--ink-mid);
  cursor:pointer;transition:all var(--t);white-space:nowrap}
.city-btn:hover{border-color:var(--ink);color:var(--ink)}
.city-btn.active{background:var(--ink);border-color:var(--ink);color:var(--bg)}
.nav-right{font-family:var(--font-m);font-size:.65rem;color:var(--ink-light);
  white-space:nowrap;margin-left:auto}
/* HERO */
.hero{padding:3.5rem 2rem 2.5rem;max-width:1400px;margin:0 auto;
  border-bottom:1px solid var(--border)}
.hero-eye{font-family:var(--font-m);font-size:.65rem;letter-spacing:.22em;
  text-transform:uppercase;color:var(--ink-light);margin-bottom:.4rem}
.hero-title{font-family:var(--font-d);font-weight:700;
  font-size:clamp(5.5rem,16vw,15rem);letter-spacing:-.025em;
  line-height:.88;color:var(--ink);margin-bottom:1.2rem}
.hero-title em{color:var(--accent);font-style:normal}
.hero-sub{font-family:var(--font-b);font-weight:300;font-style:italic;
  font-size:clamp(1rem,1.8vw,1.3rem);color:var(--ink-mid);max-width:38ch}
/* FILTERS */
.filters-wrap{background:var(--bg);
  border-bottom:1px solid var(--border)}
.filters{max-width:1400px;margin:0 auto;padding:.65rem 2rem;
  display:flex;gap:.45rem;overflow-x:auto;scrollbar-width:none}
.filters::-webkit-scrollbar{display:none}
.filter-btn{flex-shrink:0;font-family:var(--font-m);font-size:.65rem;
  letter-spacing:.06em;padding:.3rem .8rem;border:1px solid var(--border);
  border-radius:100px;background:transparent;color:var(--ink-mid);
  cursor:pointer;transition:all var(--t);white-space:nowrap}
.filter-btn:hover{border-color:var(--ink);color:var(--ink)}
.filter-btn.active{background:var(--ink);border-color:var(--ink);color:var(--bg)}
.count{opacity:.55;margin-left:.25em}
/* GRID */
.grid-wrap{max-width:1400px;margin:0 auto;padding:1.5rem;background:var(--bg)}
.grid{display:grid;grid-template-columns:repeat(5,1fr);gap:1rem}
@media(max-width:1200px){.grid{grid-template-columns:repeat(4,1fr)}}
@media(max-width:900px){.grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:640px){.grid{grid-template-columns:repeat(2,1fr)}.grid-wrap{padding:.75rem}}
@media(max-width:400px){.grid{grid-template-columns:1fr}}
/* CARD */
.place-card{background:var(--surface);border:1px solid var(--border);
  overflow:hidden;display:flex;flex-direction:column;
  transition:transform var(--t),box-shadow var(--t)}
.place-card:hover{transform:translateY(-4px);
  box-shadow:0 10px 28px rgba(26,23,20,.09)}
.place-card.hidden{display:none!important}
.card-photo{position:relative;aspect-ratio:16/9;overflow:hidden;background:var(--border)}
.card-photo img{width:100%;height:100%;object-fit:cover;display:block;
  transition:transform .45s ease}
.place-card:hover .card-photo img{transform:scale(1.04)}
.photo-ph{width:100%;height:100%;display:flex;align-items:center;
  justify-content:center;font-size:3rem;background:var(--border)}
.card-tag{position:absolute;bottom:.7rem;left:.7rem;font-family:var(--font-m);
  font-size:.58rem;letter-spacing:.1em;text-transform:uppercase;
  background:rgba(26,23,20,.88);color:var(--bg);
  padding:.22rem .6rem;border-radius:2px;backdrop-filter:blur(4px)}
.card-body{padding:.75rem .85rem .9rem;display:flex;flex-direction:column;
  gap:.25rem;flex:1}
.card-name{font-family:var(--font-b);font-weight:600;font-size:.95rem;
  line-height:1.3;color:var(--ink)}
.card-meta{font-family:var(--font-m);font-size:.55rem;letter-spacing:.06em;
  color:var(--ink-light);text-transform:uppercase}
.card-rating{display:flex;align-items:center;gap:.3rem}
.stars{color:var(--accent);font-size:.75rem;letter-spacing:-.05em}
.rnum{font-family:var(--font-m);font-size:.6rem;color:var(--ink)}
.rcnt{font-family:var(--font-m);font-size:.55rem;color:var(--ink-light)}
.card-notes{font-style:italic;font-size:.8rem;color:var(--ink-mid);
  margin-top:auto;padding-top:.25rem;border-top:1px solid var(--border)}
.maps-icon{display:inline-flex;align-items:center;justify-content:center;
  width:1.1em;height:1.1em;margin-left:.3em;vertical-align:middle;
  color:var(--ink-light);opacity:.6;transition:opacity var(--t);flex-shrink:0}
.maps-icon:hover{opacity:1;color:var(--accent)}
.maps-icon svg{width:100%;height:100%}
/* FOOTER */
footer{border-top:1px solid var(--border);padding:2.5rem 2rem;
  text-align:center;font-family:var(--font-m);font-size:.6rem;
  letter-spacing:.14em;text-transform:uppercase;color:var(--ink-light)}
/* ANIMATIONS */
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
.hero{animation:fadeIn .55s ease both}
.place-card{animation:fadeIn .4s ease both}
"""


def stars(rating):
    if not rating:
        return ""
    n = int(round(float(rating)))
    return "★" * n + "☆" * (5 - n)


def card_html(p, emojis, city_key):
    cat = p.get("category", "other")
    emoji = emojis.get(cat, "📍")
    name = p.get("name", "")
    neighborhood = p.get("neighborhood", "")
    ptype = p.get("type", "")
    rating = p.get("rating")
    rcnt = p.get("review_count")
    notes = p.get("notes", "")
    photo = p.get("photo_url", "").lstrip("/")
    pid = p.get("place_id", "")
    maps_url = f"https://www.google.com/maps/place/?q=place_id:{pid}" if pid else ""

    photo_block = (
        f'<img src="{photo}" alt="{name}" loading="lazy">'
        if photo else f'<div class="photo-ph">{emoji}</div>'
    )
    meta_parts = [x for x in [neighborhood, ptype] if x]
    meta = f'<div class="card-meta">{" · ".join(meta_parts)}</div>' if meta_parts else ""
    rating_html = ""
    if rating:
        cnt_str = f" ({rcnt:,})" if rcnt else ""
        rating_html = (
            f'<div class="card-rating">'
            f'<span class="stars">{stars(rating)}</span>'
            f'<span class="rnum">{rating}</span>'
            f'<span class="rcnt">{cnt_str}</span>'
            f'</div>'
        )
    notes_html = f'<p class="card-notes">{notes}</p>' if notes else ""
    link_icon = (
        f'<a href="{maps_url}" target="_blank" rel="noopener" class="maps-icon" title="Open in Google Maps">'
        f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>'
        f'<circle cx="12" cy="9" r="2.5"/>'
        f'</svg></a>'
    ) if maps_url else ""

    return (
        f'\n    <article class="place-card" data-category="{cat}" data-city="{city_key}">'
        f'\n      <div class="card-photo">{photo_block}'
        f'<span class="card-tag">{emoji} {cat}</span></div>'
        f'\n      <div class="card-body">'
        f'\n        <h3 class="card-name">{name}{link_icon}</h3>'
        f'\n        {meta}{rating_html}{notes_html}'
        f'\n      </div>'
        f'\n    </article>'
    )


def build_filter_btns(places, emojis):
    counts = Counter(p["category"] for p in places)
    total = len(places)
    btns = [f'<button class="filter-btn active" data-filter="all" onclick="filterCards(\'all\',this)">All<span class="count">{total}</span></button>']
    for cat in CAT_ORDER:
        if cat in counts:
            e = emojis.get(cat, "📍")
            btns.append(
                f'<button class="filter-btn" data-filter="{cat}" onclick="filterCards(\'{cat}\',this)">'
                f'{e} {cat.title()}<span class="count">{counts[cat]}</span></button>'
            )
    return "\n      ".join(btns)


def hero_parts(city_name: str) -> tuple[str, str]:
    """Return (hero_title_html, hero_sub_text) for a city."""
    name = city_name.upper()
    mid = len(name) // 2
    mid_chars = name[mid - 1: mid + 1] if len(name) >= 2 else name[0]
    prefix = name[: max(0, mid - 1)]
    suffix = name[mid + 1:]
    title = f"{prefix}<em>{mid_chars}</em>{suffix}"
    sub = f"A curated collection of places I love — restaurants, cafés, shops, and hidden corners across the city."
    return title, sub


def build():
    CITIES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    PHOTOS_DST.mkdir(parents=True, exist_ok=True)

    if PHOTOS_SRC.exists():
        copied = 0
        for img in PHOTOS_SRC.iterdir():
            shutil.copy2(img, PHOTOS_DST / img.name)
            copied += 1
        if copied:
            print(f"Copied {copied} photos → {PHOTOS_DST}")

    city_files = sorted(CITIES_DIR.glob("*.json"))
    if not city_files:
        print("No city JSON files found in data/cities/. Nothing to build.")
        return

    cities = []
    all_cards = []
    city_meta_js = {}

    for cf in city_files:
        with open(cf, encoding="utf-8") as f:
            data = json.load(f)

        places = data.get("places", [])
        meta = data.get("meta", {})
        city_key = meta.get("city_key") or cf.stem
        city_name = meta.get("city") or city_key.title()
        emojis = data.get("categories", EMOJIS)

        counts = Counter(p.get("category", "other") for p in places)
        city_meta_js[city_key] = {
            "name": city_name,
            "total": len(places),
            "counts": dict(counts),
        }
        cities.append((city_key, city_name, len(places)))

        for p in places:
            all_cards.append(card_html(p, emojis, city_key))

        print(f"  Loaded {len(places):3d} places ← {cf.name}")

    first_key, first_name, first_total = cities[0]

    city_btns = "\n      ".join(
        f'<button class="city-btn{"  active" if i == 0 else ""}" '
        f'data-city="{key}" onclick="switchCity(\'{key}\')">{name}</button>'
        for i, (key, name, _) in enumerate(cities)
    )

    first_title, first_sub = hero_parts(first_name)

    first_data = json.loads(open(city_files[0], encoding="utf-8").read())
    initial_filters_html = build_filter_btns(
        first_data.get("places", []),
        first_data.get("categories", EMOJIS),
    )

    city_meta_json = json.dumps(city_meta_js, ensure_ascii=False)

    js = f"""
const CITY_META = {city_meta_json};
const CAT_EMOJI = {json.dumps(EMOJIS)};
const CAT_ORDER = {json.dumps(CAT_ORDER)};
let activeCity = '{first_key}';
let activeCat = 'all';

function switchCity(key) {{
  if (key === activeCity) return;
  activeCity = key;
  activeCat = 'all';

  document.querySelectorAll('.city-btn').forEach(b => b.classList.toggle('active', b.dataset.city === key));

  const meta = CITY_META[key];
  const name = meta.name.toUpperCase();
  const mid = Math.floor(name.length / 2);
  const midChars = name.length >= 2 ? name.slice(Math.max(0, mid-1), mid+1) : name[0];
  const prefix = name.slice(0, Math.max(0, mid-1));
  const suffix = name.slice(mid+1);
  document.getElementById('hero-title').innerHTML = prefix + '<em>' + midChars + '</em>' + suffix;

  document.getElementById('nav-count').textContent = meta.name + ' · ' + meta.total + ' places';

  rebuildFilters(key);

  document.querySelectorAll('.place-card').forEach(c => {{
    c.classList.toggle('hidden', c.dataset.city !== key);
  }});
}}

function rebuildFilters(cityKey) {{
  const meta = CITY_META[cityKey];
  const counts = meta.counts;
  const total = meta.total;
  const wrap = document.getElementById('filter-list');
  let html = '<button class="filter-btn active" data-filter="all" onclick="filterCards(\\'all\\',this)">All<span class="count">' + total + '</span></button>';
  CAT_ORDER.forEach(cat => {{
    if (counts[cat]) {{
      const e = CAT_EMOJI[cat] || '📍';
      html += '<button class="filter-btn" data-filter="' + cat + '" onclick="filterCards(\\'' + cat + '\\',this)">' + e + ' ' + cat.charAt(0).toUpperCase() + cat.slice(1) + '<span class="count">' + counts[cat] + '</span></button>';
    }}
  }});
  wrap.innerHTML = html;
}}

function filterCards(f, btn) {{
  activeCat = f;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.place-card').forEach(c => {{
    if (c.dataset.city !== activeCity) {{ c.classList.add('hidden'); return; }}
    c.classList.toggle('hidden', f !== 'all' && c.dataset.category !== f);
  }});
}}
"""

    cards_html = "\n".join(all_cards)
    total_all = sum(t for _, _, t in cities)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="A personal guide to my favorite places around the world.">
  <title>Waypoints</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300&family=Cormorant:wght@700&family=DM+Sans:wght@300;400;500&family=Noto+Sans+JP:wght@300;400&display=swap" rel="stylesheet">
  <style>{CSS}</style>
</head>
<body>
  <div class="sticky-header">
    <nav class="nav">
      <a class="nav-brand" href="#">Waypoints</a>
      <div class="city-switcher">
        {city_btns}
      </div>
      <span class="nav-right" id="nav-count">{first_name} · {first_total} places</span>
    </nav>
    <div class="filters-wrap">
      <div class="filters" id="filter-list">
        {initial_filters_html}
      </div>
    </div>
  </div>
  <section class="hero">
    <p class="hero-eye">Personal City Guide</p>
    <h1 class="hero-title" id="hero-title">{first_title}</h1>
    <p class="hero-sub">{first_sub}</p>
  </section>
  <div class="grid-wrap">
    <div class="grid">
      {cards_html}
    </div>
  </div>
  <footer>Waypoints · Built with love · {total_all} places across {len(cities)} {'city' if len(cities) == 1 else 'cities'}</footer>
  <script>
    {js}
  </script>
</body>
</html>"""

    out = OUTPUT_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"Built → {out}  ({out.stat().st_size // 1024}KB, {len(cities)} {'city' if len(cities) == 1 else 'cities'})")


if __name__ == "__main__":
    build()
