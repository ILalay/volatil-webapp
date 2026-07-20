import json
import os
import time

import requests
from flask import Flask, render_template

app = Flask(__name__)

# ============================================================
# Einstellungen
# ============================================================

API_URL = "https://api.volatileskins.com/v1/volatile-shop/26"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MATCH_FILE = os.path.join(BASE_DIR, "iem_cologne_2026_matches_complete.json")

DISCOUNT = 0.96  # 96 % Rabatt
TOKENS_PER_100 = 153  # 100 Tokens = 153 €

CACHE_SECONDS = 300  # Wie lange die Ergebnisse zwischengespeichert werden

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

# Einfacher In-Memory-Cache, damit nicht bei jedem Seitenaufruf
# die komplette API abgefragt wird.
_cache = {"data": None, "timestamp": 0.0, "error": None}


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


def compute_results():
    team_tokens = load_team_tokens()
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
        discounted_tokens = total_tokens * (1 - DISCOUNT)
        euro_price = (discounted_tokens / 100) * TOKENS_PER_100

        results.append(
            {
                "team1": team1,
                "team2": team2,
                "tokens": total_tokens,
                "discounted_tokens": discounted_tokens,
                "price_eur": euro_price,
            }
        )

    results.sort(key=lambda x: x["price_eur"])

    return {
        "results": results,
        "missing": sorted(missing),
        "team_count": len(team_tokens),
        "generated_at": time.strftime("%d.%m.%Y %H:%M:%S"),
    }


def get_cached_results(force=False):
    now = time.time()
    stale = (now - _cache["timestamp"]) > CACHE_SECONDS

    if force or _cache["data"] is None or stale:
        try:
            _cache["data"] = compute_results()
            _cache["error"] = None
            _cache["timestamp"] = now
        except (requests.exceptions.RequestException, FileNotFoundError, KeyError, ValueError) as exc:
            _cache["error"] = str(exc)
            # Altes Ergebnis behalten, falls vorhanden, statt die Seite abstürzen zu lassen
            if _cache["data"] is None:
                raise

    return _cache["data"], _cache["error"]


# ============================================================
# Routen
# ============================================================

@app.route("/")
def index():
    try:
        data, error = get_cached_results()
    except Exception as exc:  # noqa: BLE001 - bewusst breit, um Fehlerseite zu zeigen
        return render_template("error.html", message=str(exc)), 500

    return render_template("index.html", error=error, **data)


@app.route("/refresh")
def refresh():
    try:
        data, error = get_cached_results(force=True)
    except Exception as exc:  # noqa: BLE001
        return render_template("error.html", message=str(exc)), 500

    return render_template("index.html", error=error, **data)


if __name__ == "__main__":
    app.run(debug=True)
