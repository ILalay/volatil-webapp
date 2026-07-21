import json
import os
import time

import requests
from flask import Flask, render_template, request

app = Flask(__name__)

# ============================================================
# Einstellungen
# ============================================================

API_URL = "https://api.volatileskins.com/v1/volatile-shop/26"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MATCH_FILE = os.path.join(BASE_DIR, "iem_cologne_2026_matches_complete.json")

DEFAULT_DISCOUNT = 0.96  # 96 % Rabatt (Startwert / Fallback)
TOKENS_PER_100 = 153     # 100 Tokens = 153 ¥

CACHE_SECONDS = 300  # Wie lange die Tokenpreise zwischengespeichert werden

# History wird über GitHub Gists gespeichert (kostenlos, dauerhaft).
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GIST_ID = os.environ.get("GIST_ID")
HISTORY_FILENAME = "price_history.json"
MAX_HISTORY_POINTS = 500
# History wird immer mit diesem festen Rabatt berechnet, damit die
# Werte über die Zeit vergleichbar bleiben, egal was gerade im
# Rabatt-Regler auf der Seite eingestellt ist.
HISTORY_DISCOUNT = DEFAULT_DISCOUNT

RENAME = {
    "Berlin International Gaming": "BIG",
    "Team Vitality": "Vitality",
    "Team Spirit": "Spirit",
    "G2 Esports": "G2",
    "FURIA Esports": "FURIA",
    "Heroic": "HEROIC",
    "Legacy Esports": "Legacy",
    "Made in Brazil": "MIBR",
    "Tyloo": "TYLOO",
    "NRG Esports": "NRG",
    "B8 Esports": "B8",
    "Sharks Esports": "Sharks",
    "Team Liquid": "Liquid",
    "paiN Gaming": "paiN",
    "Parivision": "PARIVISION",
    "9z Team": "9z",
    "The MongolZ": "The MongolZ",
    "THUNDER dOWNUNDER": "Thunder Logic",
    "Sinners": "SINNERS",
    "mousesports": "MOUZ",
}

# Cache nur für die (teure) API-Abfrage der Tokenpreise.
# Die Rabattrechnung selbst ist billig und wird bei jedem Request neu gemacht,
# damit der Nutzer den Rabatt live ändern kann ohne die API neu zu belasten.
_cache = {"team_tokens": None, "timestamp": 0.0, "error": None, "history": []}


# ============================================================
# Datenbeschaffung
# ============================================================

def load_team_tokens():
    """Lädt alle Gold-Teamsticker von der API und liefert {team: tokens}."""
    team_tokens = {}
    offset = 0
    limit = 48

    while True:
        params = {
            "limit": limit,
            "offset": offset,
            "sortBy": "rank",
            "sortDir": "asc",
            "currency": "EUR",
        }

        response = requests.get(API_URL, params=params, timeout=15)
        response.raise_for_status()

        items = response.json()

        if not items:
            break

        for item in items:
            # Nur Gold-Teamsticker
            if item["rarity"] == 4 and item["isOrg"]:
                if item["teamName"]:
                    team = item["teamName"]
                else:
                    team = (
                        item["name"]
                        .replace("Sticker | ", "")
                        .replace(" (Gold) | Cologne 2026", "")
                    )
                team_tokens[team] = item["tokens"]

        offset += limit

    # Teamnamen an Matchliste anpassen
    for old, new in RENAME.items():
        if old in team_tokens:
            team_tokens[new] = team_tokens.pop(old)

    return team_tokens


def load_matches():
    with open(MATCH_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["matches"]


# ============================================================
# Preisverlauf (History) via GitHub Gist
# ============================================================

def history_enabled():
    return bool(GITHUB_TOKEN and GIST_ID)


def load_history_from_gist():
    if not history_enabled():
        return []

    response = requests.get(
        f"https://api.github.com/gists/{GIST_ID}",
        headers={
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        timeout=10,
    )
    response.raise_for_status()

    gist = response.json()
    file_info = gist.get("files", {}).get(HISTORY_FILENAME)
    if not file_info:
        return []

    try:
        return json.loads(file_info.get("content", "[]"))
    except ValueError:
        return []


def save_history_to_gist(history):
    if not history_enabled():
        return

    trimmed = history[-MAX_HISTORY_POINTS:]

    response = requests.patch(
        f"https://api.github.com/gists/{GIST_ID}",
        headers={
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
        json={"files": {HISTORY_FILENAME: {"content": json.dumps(trimmed)}}},
        timeout=10,
    )
    response.raise_for_status()


def append_history_point(team_tokens):
    """Berechnet den aktuell günstigsten Preis (fixer Referenz-Rabatt) und
    hängt einen Datenpunkt an die Gist-History an."""
    if not history_enabled():
        return []

    results, _ = compute_results(team_tokens, HISTORY_DISCOUNT)
    if not results:
        return load_history_from_gist()

    cheapest = results[0]

    history = load_history_from_gist()
    history.append(
        {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "price": round(cheapest["price_eur"], 2),
            "match": f"{cheapest['team1']} vs {cheapest['team2']}",
        }
    )
    save_history_to_gist(history)
    return history


def get_team_tokens(force=False):
    """Team-Tokens mit Cache laden. Wirft eine Exception, wenn nichts geladen werden kann."""
    now = time.time()
    stale = (now - _cache["timestamp"]) > CACHE_SECONDS

    if force or _cache["team_tokens"] is None or stale:
        try:
            _cache["team_tokens"] = load_team_tokens()
            _cache["error"] = None
            _cache["timestamp"] = now
            try:
                _cache["history"] = append_history_point(_cache["team_tokens"])
            except requests.exceptions.RequestException:
                # History-Update darf die Seite nicht zum Absturz bringen,
                # falls die Gist-API mal nicht erreichbar ist.
                pass
        except (requests.exceptions.RequestException, KeyError, ValueError) as exc:
            _cache["error"] = str(exc)
            if _cache["team_tokens"] is None:
                raise

    return _cache["team_tokens"], _cache["error"]


def compute_results(team_tokens, discount):
    matches = load_matches()

    results = []
    missing = set()

    for match in matches:
        team1 = match["team1"]
        team2 = match["team2"]

        if team1 not in team_tokens:
            missing.add(team1)
            continue
        if team2 not in team_tokens:
            missing.add(team2)
            continue

        total_tokens = team_tokens[team1] + team_tokens[team2]
        discounted_tokens = total_tokens * (1 - discount)
        price = (discounted_tokens / 100) * TOKENS_PER_100

        results.append(
            {
                "team1": team1,
                "team2": team2,
                "tokens": total_tokens,
                "discounted_tokens": discounted_tokens,
                "price_eur": price,
            }
        )

    results.sort(key=lambda x: x["price_eur"])
    return results, sorted(missing)


def parse_discount(raw_value):
    """Erwartet einen Prozentwert als String (z. B. '96' oder '96.5') und
    liefert einen Faktor zwischen 0 und 0.999 zurück. Bei ungültiger Eingabe
    wird der Standardwert genutzt."""
    if raw_value is None or raw_value == "":
        return DEFAULT_DISCOUNT
    try:
        percent = float(raw_value)
    except ValueError:
        return DEFAULT_DISCOUNT

    percent = max(0.0, min(percent, 99.9))
    return percent / 100


def build_page_data(force_token_refresh=False):
    discount = parse_discount(request.args.get("discount"))
    team_tokens, error = get_team_tokens(force=force_token_refresh)
    results, missing = compute_results(team_tokens, discount)

    chart_size = 15
    top_results = results[:chart_size]

    history = _cache["history"]

    return {
        "results": results,
        "missing": missing,
        "team_count": len(team_tokens),
        "generated_at": time.strftime("%d.%m.%Y %H:%M:%S"),
        "error": error,
        "discount_percent": round(discount * 100, 2),
        "chart_labels": [f"{r['team1']} vs {r['team2']}" for r in top_results],
        "chart_prices": [round(r["price_eur"], 2) for r in top_results],
        "history_enabled": history_enabled(),
        "history_labels": [h["timestamp"] for h in history],
        "history_prices": [h["price"] for h in history],
    }


# ============================================================
# Routen
# ============================================================

@app.route("/")
def index():
    try:
        data = build_page_data()
    except Exception as exc:  # noqa: BLE001 - bewusst breit, um Fehlerseite zu zeigen
        return render_template("error.html", message=str(exc)), 500

    return render_template("index.html", **data)


@app.route("/refresh")
def refresh():
    try:
        data = build_page_data(force_token_refresh=True)
    except Exception as exc:  # noqa: BLE001
        return render_template("error.html", message=str(exc)), 500

    return render_template("index.html", **data)


if __name__ == "__main__":
    app.run(debug=True)
