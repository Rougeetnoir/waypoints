"""
Local admin server for Waypoints.
Run:  venv/bin/python scripts/admin.py
Open: http://localhost:5001
"""

import json
import os
import queue
import re
import subprocess
import threading
from functools import wraps
from pathlib import Path
from urllib.parse import unquote

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, request, session, url_for

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", os.urandom(24))

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "waypoints")
DATA_FILE = Path("japan_places.json")
CATEGORIES = ["food", "cafe", "shopping", "vintage", "sightseeing",
               "hotel", "spa", "neighborhood", "other"]
ROOT = Path(__file__).parent.parent


# ── helpers ───────────────────────────────────────────────────────────────────

def load_data():
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    data["meta"]["total"] = len(data["places"])
    with open(ROOT / DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


def parse_maps_url(url: str) -> dict:
    result = {"name": "", "maps_search": "", "place_id": ""}
    m = re.search(r"ChIJ[A-Za-z0-9_\-]+", url)
    if m:
        result["place_id"] = m.group()
    decoded = unquote(url)
    nm = re.search(r"/maps/place/([^/@?]+)", decoded)
    if nm:
        name = nm.group(1).replace("+", " ").strip()
        result["name"] = name
        result["maps_search"] = f"{name} Tokyo"
    return result


# ── auth ──────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect(url_for("admin_page") if session.get("logged_in") else url_for("login_page"))


@app.route("/login", methods=["GET", "POST"])
def login_page():
    error = ""
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("admin_page"))
        error = "Wrong password."
    return LOGIN_HTML.replace("{{error}}", error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


# ── admin UI ──────────────────────────────────────────────────────────────────

@app.route("/admin")
@require_auth
def admin_page():
    return ADMIN_HTML


# ── REST API ──────────────────────────────────────────────────────────────────

@app.route("/api/places", methods=["GET"])
@require_auth
def api_get_places():
    return jsonify(load_data()["places"])


@app.route("/api/places", methods=["POST"])
@require_auth
def api_add_place():
    body = request.json or {}
    data = load_data()
    next_id = max((p["id"] for p in data["places"]), default=0) + 1
    place = {
        "id": next_id,
        "name": (body.get("name") or "").strip(),
        "category": body.get("category", "other"),
        "type": body.get("type", ""),
        "rating": None,
        "review_count": None,
        "neighborhood": body.get("neighborhood", ""),
        "notes": body.get("notes", ""),
        "place_id": body.get("place_id", ""),
        "coordinates": {"lat": None, "lng": None},
        "photo_url": "",
        "maps_search": body.get("maps_search", body.get("name", "")),
    }
    if not place["name"]:
        return jsonify({"error": "name is required"}), 400
    data["places"].append(place)
    save_data(data)
    return jsonify(place), 201


@app.route("/api/places/<int:pid>", methods=["PATCH"])
@require_auth
def api_update_place(pid):
    body = request.json or {}
    data = load_data()
    place = next((p for p in data["places"] if p["id"] == pid), None)
    if not place:
        return jsonify({"error": "not found"}), 404
    for field in ("category", "notes", "neighborhood", "type", "name"):
        if field in body:
            place[field] = body[field]
    save_data(data)
    return jsonify(place)


@app.route("/api/places/<int:pid>", methods=["DELETE"])
@require_auth
def api_delete_place(pid):
    data = load_data()
    before = len(data["places"])
    data["places"] = [p for p in data["places"] if p["id"] != pid]
    if len(data["places"]) == before:
        return jsonify({"error": "not found"}), 404
    save_data(data)
    return jsonify({"ok": True})


@app.route("/api/parse-url", methods=["POST"])
@require_auth
def api_parse_url():
    url = (request.json or {}).get("url", "")
    return jsonify(parse_maps_url(url))


# ── deploy SSE ────────────────────────────────────────────────────────────────

def run_deploy(msg: str, q: queue.Queue):
    try:
        steps = [
            (["venv/bin/python", "scripts/enrich_places.py"], "Enriching new places..."),
            (["venv/bin/python", "scripts/build_site.py"],    "Building site..."),
            (["git", "add", "."],                              None),
            (["git", "commit", "-m", msg or "admin update"],  "Committing..."),
            (["git", "push"],                                  "Pushing to GitHub..."),
        ]
        for cmd, label in steps:
            if label:
                q.put(f"\n▶ {label}\n")
            proc = subprocess.Popen(
                cmd, cwd=ROOT,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in proc.stdout:
                q.put(line)
            proc.wait()
            if proc.returncode not in (0, 1):
                q.put(f"✗ Failed: {' '.join(cmd)} (exit {proc.returncode})\n")
        q.put("\n✓ Done! Live at: https://rougeetnoir.github.io/waypoints/\n")
    except Exception as e:
        q.put(f"\n✗ Error: {e}\n")
    finally:
        q.put(None)


@app.route("/api/deploy", methods=["POST"])
@require_auth
def api_deploy():
    msg = (request.json or {}).get("message", "admin update")
    q = queue.Queue()
    threading.Thread(target=run_deploy, args=(msg, q), daemon=True).start()

    def stream():
        while True:
            line = q.get()
            if line is None:
                break
            yield f"data: {json.dumps(line)}\n\n"
        yield "data: __done__\n\n"

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── HTML ──────────────────────────────────────────────────────────────────────

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Waypoints — Admin</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;600&family=Cormorant:wght@700&family=DM+Mono:wght@300;400&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#F4F0E8;display:flex;align-items:center;justify-content:center;min-height:100vh;font-family:'DM Mono',monospace}
.card{background:#FDFAF6;border:1px solid #E0D8CC;padding:3rem 2.5rem;width:min(400px,90vw)}
h1{font-family:'Cormorant',serif;font-size:2.5rem;color:#1A1714;margin-bottom:.25rem}
.sub{font-size:.65rem;letter-spacing:.2em;text-transform:uppercase;color:#9C958E;margin-bottom:2rem}
label{font-size:.65rem;letter-spacing:.1em;text-transform:uppercase;color:#5C5650;display:block;margin-bottom:.4rem}
input{width:100%;border:1px solid #E0D8CC;background:#F4F0E8;padding:.7rem .9rem;font-family:'DM Mono',monospace;font-size:.85rem;color:#1A1714;outline:none}
input:focus{border-color:#1A1714}
button{margin-top:1.2rem;width:100%;background:#1A1714;color:#F4F0E8;border:none;padding:.8rem;font-family:'DM Mono',monospace;font-size:.65rem;letter-spacing:.15em;text-transform:uppercase;cursor:pointer}
button:hover{background:#C8251F}
.err{color:#C8251F;font-size:.72rem;margin-top:.75rem}
</style>
</head>
<body>
<div class="card">
  <h1>Waypoints</h1>
  <p class="sub">Admin</p>
  <form method="POST">
    <label>Password</label>
    <input type="password" name="password" autofocus>
    <button type="submit">Enter</button>
    <p class="err">{{error}}</p>
  </form>
</div>
</body>
</html>"""


ADMIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Waypoints — Admin</title>
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300&family=Cormorant:wght@700&family=DM+Mono:wght@300;400&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#F4F0E8;--sur:#FDFAF6;--ink:#1A1714;--mid:#5C5650;--lt:#9C958E;--acc:#C8251F;--bdr:#E0D8CC;--fm:'DM Mono',monospace;--fs:'Cormorant Garamond',serif;--t:.18s ease}
body{background:var(--bg);color:var(--ink);font-family:var(--fs);font-size:16px;-webkit-font-smoothing:antialiased}
/* NAV */
.nav{position:sticky;top:0;z-index:100;background:var(--bg);border-bottom:1px solid var(--bdr);padding:.8rem 1.5rem;display:flex;align-items:center;gap:1rem}
.nav-brand{font-family:var(--fm);font-size:.65rem;letter-spacing:.2em;text-transform:uppercase;color:var(--ink);text-decoration:none;margin-right:auto}
.nav-count{font-family:var(--fm);font-size:.6rem;color:var(--lt)}
.btn{font-family:var(--fm);font-size:.6rem;letter-spacing:.1em;text-transform:uppercase;padding:.4rem .9rem;border:1px solid var(--bdr);background:transparent;color:var(--mid);cursor:pointer;transition:all var(--t);white-space:nowrap}
.btn:hover{border-color:var(--ink);color:var(--ink)}
.btn-primary{background:var(--ink);border-color:var(--ink);color:var(--bg)}
.btn-primary:hover{background:var(--acc);border-color:var(--acc)}
.btn-deploy{background:var(--acc);border-color:var(--acc);color:#fff}
.btn-deploy:hover{opacity:.85}
/* FILTERS */
.filters-wrap{background:var(--bg);border-bottom:1px solid var(--bdr);padding:.5rem 1.5rem}
.filters{display:flex;gap:.4rem;overflow-x:auto;scrollbar-width:none}
.filters::-webkit-scrollbar{display:none}
.fbtn{flex-shrink:0;font-family:var(--fm);font-size:.58rem;letter-spacing:.06em;padding:.25rem .7rem;border:1px solid var(--bdr);border-radius:100px;background:transparent;color:var(--mid);cursor:pointer;transition:all var(--t)}
.fbtn:hover{border-color:var(--ink);color:var(--ink)}
.fbtn.active{background:var(--ink);border-color:var(--ink);color:var(--bg)}
/* GRID */
.grid-wrap{max-width:1400px;margin:0 auto;padding:1.25rem}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.85rem}
@media(max-width:1100px){.grid{grid-template-columns:repeat(3,1fr)}}
@media(max-width:750px){.grid{grid-template-columns:repeat(2,1fr)}}
/* CARD */
.card{background:var(--sur);border:1px solid var(--bdr);display:flex;flex-direction:column;position:relative}
.card.hidden{display:none}
.card-photo{aspect-ratio:16/9;overflow:hidden;background:var(--bdr);flex-shrink:0;position:relative}
.card-photo img{width:100%;height:100%;object-fit:cover;display:block}
.card-photo-ph{width:100%;height:100%;display:flex;align-items:center;justify-content:center;font-size:2rem}
.del-btn{position:absolute;top:.4rem;right:.4rem;width:1.6rem;height:1.6rem;background:rgba(26,23,20,.75);border:none;color:#fff;cursor:pointer;font-size:.9rem;display:flex;align-items:center;justify-content:center;transition:background var(--t);backdrop-filter:blur(4px);border-radius:2px}
.del-btn:hover{background:var(--acc)}
.card-body{padding:.65rem .75rem .8rem;display:flex;flex-direction:column;gap:.4rem;flex:1}
.card-name{font-family:var(--fs);font-weight:600;font-size:.95rem;color:var(--ink);background:transparent;border:none;border-bottom:1px solid transparent;width:100%;outline:none;padding:.1rem 0;transition:border-color var(--t)}
.card-name:focus{border-bottom-color:var(--bdr)}
.card-row{display:flex;gap:.4rem;align-items:center}
select.cat-sel{font-family:var(--fm);font-size:.58rem;letter-spacing:.04em;padding:.25rem .5rem;border:1px solid var(--bdr);background:var(--bg);color:var(--ink);cursor:pointer;outline:none;flex-shrink:0}
select.cat-sel:focus{border-color:var(--ink)}
.nbhd-inp{font-family:var(--fm);font-size:.58rem;color:var(--lt);background:transparent;border:none;border-bottom:1px dashed transparent;outline:none;flex:1;min-width:0;transition:border-color var(--t)}
.nbhd-inp:focus{border-bottom-color:var(--bdr)}
.nbhd-inp::placeholder{color:var(--bdr)}
.rating{font-family:var(--fm);font-size:.58rem;color:var(--lt);flex-shrink:0}
textarea.notes{font-family:var(--fs);font-style:italic;font-size:.82rem;color:var(--mid);background:transparent;border:none;border-top:1px solid var(--bdr);padding-top:.4rem;resize:none;width:100%;outline:none;line-height:1.5;min-height:3rem}
textarea.notes::placeholder{color:var(--bdr)}
.no-ph{color:var(--lt);font-family:var(--fm);font-size:.65rem}
/* MODAL */
.overlay{display:none;position:fixed;inset:0;background:rgba(26,23,20,.55);z-index:200;align-items:center;justify-content:center;backdrop-filter:blur(3px)}
.overlay.open{display:flex}
.modal{background:var(--sur);border:1px solid var(--bdr);padding:2rem;width:min(520px,90vw);max-height:90vh;overflow-y:auto}
.modal h2{font-family:'Cormorant',serif;font-size:1.8rem;margin-bottom:1.25rem}
.field{margin-bottom:1rem}
.field label{display:block;font-family:var(--fm);font-size:.6rem;letter-spacing:.1em;text-transform:uppercase;color:var(--mid);margin-bottom:.35rem}
.field input,.field select,.field textarea{width:100%;border:1px solid var(--bdr);background:var(--bg);padding:.6rem .75rem;font-family:var(--fm);font-size:.8rem;color:var(--ink);outline:none}
.field input:focus,.field select:focus,.field textarea:focus{border-color:var(--ink)}
.field textarea{resize:vertical;min-height:4rem}
.modal-actions{display:flex;gap:.6rem;justify-content:flex-end;margin-top:1.25rem}
/* DEPLOY LOG */
.log-wrap{background:#1A1714;border:1px solid #333;padding:1rem;margin-top:1rem;max-height:280px;overflow-y:auto;border-radius:2px}
pre.log{font-family:var(--fm);font-size:.7rem;color:#d0cbc4;line-height:1.7;white-space:pre-wrap;word-break:break-all}
.log-done{color:#6dbd6d}
/* TOAST */
.toast{position:fixed;bottom:1.5rem;right:1.5rem;background:var(--ink);color:var(--bg);font-family:var(--fm);font-size:.62rem;letter-spacing:.08em;padding:.6rem 1rem;border-radius:2px;opacity:0;transform:translateY(6px);transition:all .22s ease;pointer-events:none;z-index:999}
.toast.show{opacity:1;transform:none}
</style>
</head>
<body>

<!-- NAV -->
<nav class="nav">
  <a href="/admin" class="nav-brand">Waypoints / Admin</a>
  <span class="nav-count" id="count-label"></span>
  <button class="btn btn-primary" onclick="openAddModal()">+ Add Place</button>
  <button class="btn btn-deploy" onclick="openDeployModal()">Build &amp; Deploy</button>
  <a href="/logout" class="btn">Logout</a>
</nav>

<!-- FILTERS -->
<div class="filters-wrap">
  <div class="filters" id="filters"></div>
</div>

<!-- GRID -->
<div class="grid-wrap"><div class="grid" id="grid"></div></div>

<!-- ADD MODAL -->
<div class="overlay" id="add-overlay">
  <div class="modal">
    <h2>Add Place</h2>
    <div class="field">
      <label>Google Maps URL (paste to auto-fill)</label>
      <input type="text" id="add-url" placeholder="https://maps.google.com/maps/place/..." oninput="parseUrl()">
    </div>
    <div class="field">
      <label>Name *</label>
      <input type="text" id="add-name" placeholder="e.g. Ichiran Shimokitazawa">
    </div>
    <div class="field">
      <label>Category *</label>
      <select id="add-cat">
        <option value="food">food</option>
        <option value="cafe">cafe</option>
        <option value="shopping">shopping</option>
        <option value="vintage">vintage</option>
        <option value="sightseeing">sightseeing</option>
        <option value="hotel">hotel</option>
        <option value="spa">spa</option>
        <option value="neighborhood">neighborhood</option>
        <option value="other">other</option>
      </select>
    </div>
    <div class="field">
      <label>Neighborhood</label>
      <input type="text" id="add-nbhd" placeholder="e.g. Shimokitazawa">
    </div>
    <div class="field">
      <label>Type</label>
      <input type="text" id="add-type" placeholder="e.g. Ramen restaurant">
    </div>
    <div class="field">
      <label>Notes</label>
      <textarea id="add-notes" placeholder="Personal notes..."></textarea>
    </div>
    <div class="field">
      <label>Maps search query</label>
      <input type="text" id="add-search" placeholder="Auto-filled from URL">
    </div>
    <div class="modal-actions">
      <button class="btn" onclick="closeAddModal()">Cancel</button>
      <button class="btn btn-primary" onclick="submitAdd()">Add Place</button>
    </div>
  </div>
</div>

<!-- DEPLOY MODAL -->
<div class="overlay" id="deploy-overlay">
  <div class="modal">
    <h2>Build &amp; Deploy</h2>
    <div class="field">
      <label>Commit message</label>
      <input type="text" id="deploy-msg" value="admin update" placeholder="e.g. add Ichiran, remove old hotel">
    </div>
    <div id="log-container" style="display:none">
      <div class="log-wrap"><pre class="log" id="deploy-log"></pre></div>
    </div>
    <div class="modal-actions">
      <button class="btn" onclick="closeDeployModal()">Close</button>
      <button class="btn btn-deploy" id="deploy-btn" onclick="startDeploy()">Deploy Now</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
const CAT_EMOJI = {food:'🍜',cafe:'☕',shopping:'🛍',vintage:'👗',sightseeing:'⛩',hotel:'🏨',spa:'♨️',neighborhood:'🏘',other:'📍'};
const CAT_ORDER = ['food','cafe','shopping','vintage','sightseeing','hotel','spa','neighborhood','other'];
let allPlaces = [];
let activeCat = 'all';
let addParsed = {};

// ── boot ─────────────────────────────────────────────────────────────────────
async function boot() {
  const res = await fetch('/api/places');
  allPlaces = await res.json();
  renderFilters();
  renderGrid();
}

// ── filters ───────────────────────────────────────────────────────────────────
function renderFilters() {
  const counts = {};
  allPlaces.forEach(p => counts[p.category] = (counts[p.category]||0)+1);
  const btns = [`<button class="fbtn active" data-cat="all" onclick="setFilter('all',this)">All <span style="opacity:.5">${allPlaces.length}</span></button>`];
  CAT_ORDER.forEach(c => {
    if (counts[c]) btns.push(`<button class="fbtn" data-cat="${c}" onclick="setFilter('${c}',this)">${CAT_EMOJI[c]||''} ${c} <span style="opacity:.5">${counts[c]}</span></button>`);
  });
  document.getElementById('filters').innerHTML = btns.join('');
}
function setFilter(cat, el) {
  activeCat = cat;
  document.querySelectorAll('.fbtn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  document.querySelectorAll('.card').forEach(card => {
    card.classList.toggle('hidden', cat !== 'all' && card.dataset.cat !== cat);
  });
  const visible = cat === 'all' ? allPlaces.length : allPlaces.filter(p=>p.category===cat).length;
  document.getElementById('count-label').textContent = `${visible} place${visible!==1?'s':''}`;
}

// ── grid ──────────────────────────────────────────────────────────────────────
function renderGrid() {
  const grid = document.getElementById('grid');
  grid.innerHTML = allPlaces.map(p => cardHtml(p)).join('');
  document.getElementById('count-label').textContent = `${allPlaces.length} places`;
}

function cardHtml(p) {
  const photo = p.photo_url
    ? `<img src="/images/places/${p.photo_url.split('/').pop()}" loading="lazy" onerror="this.parentNode.innerHTML='<div class=card-photo-ph>${CAT_EMOJI[p.category]||'📍'}</div>'">`
    : `<div class="card-photo-ph">${CAT_EMOJI[p.category]||'📍'}</div>`;
  const rating = p.rating ? `<span class="rating">${p.rating}★</span>` : '';
  const catOpts = ['food','cafe','shopping','vintage','sightseeing','hotel','spa','neighborhood','other']
    .map(c => `<option value="${c}"${c===p.category?' selected':''}>${c}</option>`).join('');
  const notes = (p.notes||'').replace(/"/g,'&quot;');
  return `<div class="card" data-id="${p.id}" data-cat="${p.category}">
  <div class="card-photo">${photo}
    <button class="del-btn" onclick="deletePlace(${p.id})" title="Delete">×</button>
  </div>
  <div class="card-body">
    <input class="card-name" value="${(p.name||'').replace(/"/g,'&quot;')}" onblur="patchField(${p.id},'name',this.value)" title="Click to edit name">
    <div class="card-row">
      <select class="cat-sel" onchange="patchCat(${p.id},this)">${catOpts}</select>
      <input class="nbhd-inp" value="${(p.neighborhood||'').replace(/"/g,'&quot;')}" placeholder="neighborhood" onblur="patchField(${p.id},'neighborhood',this.value)">
      ${rating}
    </div>
    <textarea class="notes" rows="2" placeholder="Personal notes..." onblur="patchField(${p.id},'notes',this.value)">${p.notes||''}</textarea>
  </div>
</div>`;
}

// ── patch helpers ─────────────────────────────────────────────────────────────
async function patchField(id, field, value) {
  await fetch(`/api/places/${id}`, {
    method:'PATCH', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({[field]: value})
  });
  const idx = allPlaces.findIndex(p=>p.id===id);
  if (idx>-1) allPlaces[idx][field] = value;
  if (field === 'category') { renderFilters(); }
  toast('Saved');
}

async function patchCat(id, sel) {
  const newCat = sel.value;
  const card = sel.closest('.card');
  card.dataset.cat = newCat;
  await patchField(id, 'category', newCat);
  if (activeCat !== 'all' && activeCat !== newCat) card.classList.add('hidden');
}

// ── delete ────────────────────────────────────────────────────────────────────
async function deletePlace(id) {
  const p = allPlaces.find(p=>p.id===id);
  if (!p || !confirm(`Delete "${p.name}"?`)) return;
  const res = await fetch(`/api/places/${id}`, {method:'DELETE'});
  if (!res.ok) return toast('Error deleting');
  allPlaces = allPlaces.filter(p=>p.id!==id);
  document.querySelector(`.card[data-id="${id}"]`)?.remove();
  renderFilters();
  document.getElementById('count-label').textContent = `${allPlaces.length} places`;
  toast('Deleted');
}

// ── add modal ─────────────────────────────────────────────────────────────────
function openAddModal() {
  addParsed = {};
  ['add-url','add-name','add-nbhd','add-type','add-notes','add-search'].forEach(id=>document.getElementById(id).value='');
  document.getElementById('add-cat').value='food';
  document.getElementById('add-overlay').classList.add('open');
  document.getElementById('add-url').focus();
}
function closeAddModal() {
  document.getElementById('add-overlay').classList.remove('open');
}
async function parseUrl() {
  const url = document.getElementById('add-url').value.trim();
  if (!url.includes('google.com/maps') && !url.includes('maps.app.goo')) return;
  const res = await fetch('/api/parse-url',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url})});
  addParsed = await res.json();
  if (addParsed.name && !document.getElementById('add-name').value) {
    document.getElementById('add-name').value = addParsed.name;
    document.getElementById('add-search').value = addParsed.maps_search;
  }
}
async function submitAdd() {
  const name = document.getElementById('add-name').value.trim();
  if (!name) { toast('Name is required'); return; }
  const body = {
    name,
    category: document.getElementById('add-cat').value,
    neighborhood: document.getElementById('add-nbhd').value.trim(),
    type: document.getElementById('add-type').value.trim(),
    notes: document.getElementById('add-notes').value.trim(),
    maps_search: document.getElementById('add-search').value.trim() || name + ' Tokyo',
    place_id: addParsed.place_id || '',
  };
  const res = await fetch('/api/places',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if (!res.ok) { toast('Error adding place'); return; }
  const place = await res.json();
  allPlaces.push(place);
  closeAddModal();
  renderFilters();
  renderGrid();
  toast(`Added "${name}" — run Deploy to publish`);
}

// ── deploy modal ──────────────────────────────────────────────────────────────
function openDeployModal() {
  document.getElementById('log-container').style.display='none';
  document.getElementById('deploy-log').textContent='';
  document.getElementById('deploy-btn').disabled=false;
  document.getElementById('deploy-btn').textContent='Deploy Now';
  document.getElementById('deploy-overlay').classList.add('open');
}
function closeDeployModal() {
  document.getElementById('deploy-overlay').classList.remove('open');
}
async function startDeploy() {
  const msg = document.getElementById('deploy-msg').value.trim() || 'admin update';
  document.getElementById('deploy-btn').disabled=true;
  document.getElementById('deploy-btn').textContent='Deploying...';
  document.getElementById('log-container').style.display='block';
  const logEl = document.getElementById('deploy-log');
  logEl.textContent = '';
  const src = new EventSource('/api/deploy?_='+Date.now());
  // POST first, then listen
  src.close();
  const res = await fetch('/api/deploy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg})});
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    buf += dec.decode(value);
    const parts = buf.split('\\n');
    buf = parts.pop();
    for (const line of parts) {
      if (!line.startsWith('data:')) continue;
      const raw = line.slice(5).trim();
      if (raw === '__done__') { document.getElementById('deploy-btn').textContent='Done ✓'; break; }
      try { logEl.textContent += JSON.parse(raw); } catch { logEl.textContent += raw; }
      logEl.parentNode.scrollTop = logEl.parentNode.scrollHeight;
    }
  }
}

// ── toast ─────────────────────────────────────────────────────────────────────
function toast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(()=>el.classList.remove('show'), 2200);
}

// close modals on overlay click
document.querySelectorAll('.overlay').forEach(o => o.addEventListener('click', e => { if(e.target===o) o.classList.remove('open'); }));

boot();
</script>
</body>
</html>"""

if __name__ == "__main__":
    print("\n  Waypoints Admin")
    print("  ───────────────────────────────")
    print("  http://localhost:5001")
    print(f"  Password: {ADMIN_PASSWORD}")
    print("  ───────────────────────────────\n")
    app.run(port=5001, debug=True)
