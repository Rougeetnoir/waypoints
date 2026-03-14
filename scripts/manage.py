"""
Waypoints place manager — add, delete, list, search places in japan_places.json.

Usage:
  python scripts/manage.py list
  python scripts/manage.py add
  python scripts/manage.py delete "Place Name"
  python scripts/manage.py search "shimokitazawa"
"""

import json
import sys
from pathlib import Path

DATA_FILE = Path("japan_places.json")

CATEGORIES = ["food", "cafe", "shopping", "vintage", "sightseeing", "hotel", "spa", "neighborhood", "other"]


def load() -> dict:
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def save(data: dict) -> None:
    data["meta"]["total"] = len(data["places"])
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved → {DATA_FILE} ({len(data['places'])} places)")


def cmd_list(args: list) -> None:
    data = load()
    places = data["places"]

    filter_cat = args[0] if args else None
    if filter_cat:
        places = [p for p in places if p["category"] == filter_cat]

    col_w = 35
    print(f"\n{'ID':<5} {'Name':<{col_w}} {'Category':<14} {'Neighborhood':<18} {'Rating'}")
    print("─" * 85)
    for p in places:
        rating = f"{p['rating']}★" if p.get("rating") else "—"
        nbhd = p.get("neighborhood") or "—"
        name = p["name"][:col_w - 1] if len(p["name"]) >= col_w else p["name"]
        print(f"{p['id']:<5} {name:<{col_w}} {p['category']:<14} {nbhd:<18} {rating}")
    print(f"\n{len(places)} place(s)")


def cmd_search(args: list) -> None:
    if not args:
        print("Usage: manage.py search <query>")
        return
    query = " ".join(args).lower()
    data = load()
    results = [
        p for p in data["places"]
        if query in p["name"].lower()
        or query in (p.get("neighborhood") or "").lower()
        or query in (p.get("type") or "").lower()
        or query in (p.get("notes") or "").lower()
    ]
    if not results:
        print(f"No results for '{query}'")
        return
    for p in results:
        rating = f"{p['rating']}★" if p.get("rating") else "—"
        print(f"  [{p['id']}] {p['name']} | {p['category']} | {p.get('neighborhood') or '—'} | {rating}")
    print(f"\n{len(results)} result(s)")


def prompt(label: str, default: str = "", required: bool = False) -> str:
    suffix = f" [{default}]" if default else (" (required)" if required else "")
    while True:
        val = input(f"  {label}{suffix}: ").strip()
        if not val and default:
            return default
        if not val and required:
            print("  This field is required.")
            continue
        return val


def cmd_add(_args: list) -> None:
    data = load()
    next_id = max(p["id"] for p in data["places"]) + 1

    print(f"\nAdding new place (id={next_id})")
    print("─" * 40)

    name = prompt("Name", required=True)

    print(f"  Categories: {', '.join(CATEGORIES)}")
    while True:
        category = prompt("Category", required=True).lower()
        if category in CATEGORIES:
            break
        print(f"  Must be one of: {', '.join(CATEGORIES)}")

    place_type = prompt("Type (e.g. Ramen restaurant)")
    neighborhood = prompt("Neighborhood (e.g. Shimokitazawa)")
    rating_str = prompt("Rating (e.g. 4.3, or leave blank)")
    rating = float(rating_str) if rating_str else None
    review_str = prompt("Review count (or leave blank)")
    review_count = int(review_str) if review_str else None
    notes = prompt("Personal notes")
    maps_search = prompt("Maps search query", default=f"{name} Tokyo")

    place = {
        "id": next_id,
        "name": name,
        "category": category,
        "type": place_type,
        "rating": rating,
        "review_count": review_count,
        "neighborhood": neighborhood,
        "notes": notes,
        "place_id": "",
        "coordinates": {"lat": None, "lng": None},
        "photo_url": "",
        "maps_search": maps_search,
    }

    data["places"].append(place)
    save(data)
    print(f"\n✓ Added '{name}' (id={next_id})")
    print("  Run './update.sh' to enrich and publish.")


def cmd_delete(args: list) -> None:
    if not args:
        print("Usage: manage.py delete <name or id>")
        return

    data = load()
    query = " ".join(args).lower()

    matches = [
        p for p in data["places"]
        if query == str(p["id"]) or query in p["name"].lower()
    ]

    if not matches:
        print(f"No place found matching '{query}'")
        return

    if len(matches) > 1:
        print(f"Multiple matches — be more specific:")
        for p in matches:
            print(f"  [{p['id']}] {p['name']} | {p['category']} | {p.get('neighborhood') or '—'}")
        return

    target = matches[0]
    print(f"\nDelete: [{target['id']}] {target['name']} ({target['category']})?")
    confirm = input("  Confirm (y/N): ").strip().lower()
    if confirm != "y":
        print("  Cancelled.")
        return

    data["places"] = [p for p in data["places"] if p["id"] != target["id"]]
    save(data)
    print(f"✓ Deleted '{target['name']}'")
    print("  Run './update.sh' to rebuild and publish.")


COMMANDS = {
    "list": cmd_list,
    "add": cmd_add,
    "delete": cmd_delete,
    "search": cmd_search,
}

HELP = """
Waypoints place manager

Commands:
  list [category]          List all places (optionally filter by category)
  add                      Interactively add a new place
  delete <name or id>      Delete a place by name or id
  search <query>           Search by name, neighborhood, type, or notes

Examples:
  python scripts/manage.py list
  python scripts/manage.py list food
  python scripts/manage.py add
  python scripts/manage.py delete 47
  python scripts/manage.py delete "Ichiran"
  python scripts/manage.py search shimokitazawa
"""

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(HELP)
        sys.exit(0)

    cmd = args[0]
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}\nRun with --help for usage.")
        sys.exit(1)

    COMMANDS[cmd](args[1:])
