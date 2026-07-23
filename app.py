import json
import os
import time
from datetime import datetime, timedelta

import requests
from flask import Flask, make_response, render_template, request

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
HISTORY_DISCOUNT = DEFAULT_DISCOUNT
SPARKLINE_POINTS = 20

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

# ============================================================
# CS2-Raritätsstufen als Rabatt-Presets
# ============================================================

DISCOUNT_PRESETS = [
    {"name": "Consumer Grade", "color": "#b0c3d9", "discount": 99},
    {"name": "Industrial Grade", "color": "#5e98d9", "discount": 98},
    {"name": "Mil-Spec Grade", "color": "#4b69ff", "discount": 96},
    {"name": "Restricted", "color": "#8847ff", "discount": 93},
    {"name": "Classified", "color": "#d32ce6", "discount": 89},
    {"name": "Covert", "color": "#eb4b4b", "discount": 85},
]

# ============================================================
# Übersetzungen
# ============================================================

SUPPORTED_LANGS = ["de", "en", "zh"]
DEFAULT_LANG = "de"
LANG_LABELS = {"de": "DE", "en": "EN", "zh": "中文"}

TRANSLATIONS = {
    "de": {
        "eyebrow": "Volatile Shop · Gold-Teamsticker",
        "title": "Günstigste Matches",
        "teams_loaded": "{count} Teams geladen",
        "matches_calculated": "{count} Matches berechnet",
        "generated_at": "Stand: {time}",
        "refresh_button": "Preise neu laden",
        "discount_label": "Rabatt %",
        "discount_apply": "Anwenden",
        "presets_label": "Presets",
        "custom_toggle": "Eigener Wert",
        "error_banner": "Aktualisierung fehlgeschlagen, es werden die letzten bekannten Preise angezeigt.",
        "panel_history_title": "Preisverlauf günstigste Kombination",
        "stat_current": "Aktuell",
        "stat_change": "Änderung",
        "stat_change_24h": "Änderung (24h)",
        "stat_min": "Minimum",
        "stat_max": "Maximum",
        "stat_avg": "Durchschnitt",
        "stat_points": "Datenpunkte",
        "history_not_enough": "Noch nicht genug Datenpunkte gesammelt — der Verlauf füllt sich, sobald die Preise ein paar Mal aktualisiert wurden.",
        "panel_match_history_title": "Verlauf pro Match",
        "match_history_empty": "Für dieses Match sind noch keine Verlaufsdaten vorhanden.",
        "panel_top15_title": "Günstigste {n} Matches im Preisvergleich",
        "table_match": "Match",
        "table_history": "Verlauf",
        "table_tokens": "Tokens",
        "table_price": "Preis",
        "missing_label": "Nicht gefunden:",
        "footer_text": "Rabatt {percent} % · Kurs: 100 Tokens = 153 ¥",
        "price_dataset_label": "Preis (¥)",
        "cheapest_dataset_label": "Günstigster Preis (¥)",
        "facts_title": "Fakten",
        "loading_text": "Lade Preise …",
        "fact_never_changed": "Der Preis von {match} hat sich seit {duration} nicht verändert.",
        "fact_longest_expensive": "{match} ist seit {duration} durchgehend das teuerste Match ({price} ¥).",
        "fact_longest_cheapest": "{match} ist seit {duration} durchgehend das günstigste Match ({price} ¥).",
        "fact_mover_up": "{match} ist in den letzten 24h am stärksten gestiegen: +{percent}%.",
        "fact_mover_down": "{match} ist in den letzten 24h am stärksten gefallen: {percent}%.",
        "duration_days": "{n} Tagen",
        "duration_hours": "{n} Stunden",
        "duration_minutes": "{n} Minuten",
        "duration_moment": "gerade eben",
        "prediction_dataset_label": "Prognose (Modell)",
        "prediction_optimistic_label": "Optimistisch (günstig)",
        "prediction_conservative_label": "Konservativ",
        "prediction_disclaimer": "Prognosen sind unsicher und können vom tatsächlichen Verlauf abweichen.",
        "prediction_deviation": "Prognose (24h): {percent} gegenüber dem aktuellen Preis.",
    },
    "en": {
        "eyebrow": "Volatile Shop · Gold Team Stickers",
        "title": "Cheapest Matches",
        "teams_loaded": "{count} teams loaded",
        "matches_calculated": "{count} matches calculated",
        "generated_at": "As of: {time}",
        "refresh_button": "Reload prices",
        "discount_label": "Discount %",
        "discount_apply": "Apply",
        "presets_label": "Presets",
        "custom_toggle": "Custom",
        "error_banner": "Update failed — showing the last known prices.",
        "panel_history_title": "Price history — cheapest combination",
        "stat_current": "Current",
        "stat_change": "Change",
        "stat_change_24h": "Change (24h)",
        "stat_min": "Minimum",
        "stat_max": "Maximum",
        "stat_avg": "Average",
        "stat_points": "Data points",
        "history_not_enough": "Not enough data points yet — the chart fills in as prices get refreshed a few more times.",
        "panel_match_history_title": "Per-match history",
        "match_history_empty": "No history data available yet for this match.",
        "panel_top15_title": "Cheapest {n} matches compared",
        "table_match": "Match",
        "table_history": "Trend",
        "table_tokens": "Tokens",
        "table_price": "Price",
        "missing_label": "Not found:",
        "footer_text": "Discount {percent}% · Rate: 100 tokens = ¥153",
        "price_dataset_label": "Price (¥)",
        "cheapest_dataset_label": "Cheapest price (¥)",
        "facts_title": "Facts",
        "loading_text": "Loading prices …",
        "fact_never_changed": "The price of {match} hasn't changed in {duration}.",
        "fact_longest_expensive": "{match} has been the most expensive match for {duration} ({price} ¥).",
        "fact_longest_cheapest": "{match} has been the cheapest match for {duration} ({price} ¥).",
        "fact_mover_up": "{match} rose the most in the last 24h: +{percent}%.",
        "fact_mover_down": "{match} fell the most in the last 24h: {percent}%.",
        "duration_days": "{n} days",
        "duration_hours": "{n} hours",
        "duration_minutes": "{n} minutes",
        "duration_moment": "just now",
        "prediction_dataset_label": "Forecast (model)",
        "prediction_optimistic_label": "Optimistic (cheaper)",
        "prediction_conservative_label": "Conservative",
        "prediction_disclaimer": "Forecasts are uncertain and may deviate from actual prices.",
        "prediction_deviation": "Forecast (24h): {percent} vs. the current price.",
    },
    "zh": {
        "eyebrow": "Volatile Shop · 金色战队贴纸",
        "title": "最便宜的比赛",
        "teams_loaded": "已加载 {count} 支战队",
        "matches_calculated": "已计算 {count} 场比赛",
        "generated_at": "更新时间：{time}",
        "refresh_button": "刷新价格",
        "discount_label": "折扣 %",
        "discount_apply": "应用",
        "presets_label": "预设",
        "custom_toggle": "自定义",
        "error_banner": "更新失败，当前显示的是最近一次已知价格。",
        "panel_history_title": "最便宜组合的价格走势",
        "stat_current": "当前",
        "stat_change": "变化",
        "stat_change_24h": "24小时变化",
        "stat_min": "最低",
        "stat_max": "最高",
        "stat_avg": "平均",
        "stat_points": "数据点",
        "history_not_enough": "数据点还不够——价格多刷新几次后走势图就会填满。",
        "panel_match_history_title": "单场比赛走势",
        "match_history_empty": "该场比赛暂无历史数据。",
        "panel_top15_title": "最便宜的 {n} 场比赛对比",
        "table_match": "比赛",
        "table_history": "走势",
        "table_tokens": "代币",
        "table_price": "价格",
        "missing_label": "未找到：",
        "footer_text": "折扣 {percent}% · 汇率：100代币 = ¥153",
        "price_dataset_label": "价格 (¥)",
        "cheapest_dataset_label": "最低价格 (¥)",
        "facts_title": "趣味数据",
        "loading_text": "正在加载价格 …",
        "fact_never_changed": "{match} 的价格已经 {duration} 没有变化了。",
        "fact_longest_expensive": "{match} 已经连续 {duration} 是最贵的比赛（{price} ¥）。",
        "fact_longest_cheapest": "{match} 已经连续 {duration} 是最便宜的比赛（{price} ¥）。",
        "fact_mover_up": "{match} 在过去24小时内涨幅最大：+{percent}%。",
        "fact_mover_down": "{match} 在过去24小时内跌幅最大：{percent}%。",
        "duration_days": "{n} 天",
        "duration_hours": "{n} 小时",
        "duration_minutes": "{n} 分钟",
        "duration_moment": "刚刚",
        "prediction_dataset_label": "预测（模型）",
        "prediction_optimistic_label": "乐观（更便宜）",
        "prediction_conservative_label": "保守",
        "prediction_disclaimer": "预测存在不确定性，可能与实际价格不符。",
        "prediction_deviation": "预测（24小时）：与当前价格相比 {percent}。",
    },
}

# Cache nur für die (teure) API-Abfrage der Tokenpreise.
_cache = {"team_tokens": None, "timestamp": 0.0, "error": None, "history": []}


# ============================================================
# Sprachauflösung
# ============================================================

def resolve_lang():
    """Bestimmt die Sprache: expliziter ?lang= Parameter > Cookie > Browsersprache > Standard."""
    requested = request.args.get("lang")
    if requested in SUPPORTED_LANGS:
        return requested

    cookie_lang = request.cookies.get("lang")
    if cookie_lang in SUPPORTED_LANGS:
        return cookie_lang

    best = request.accept_languages.best_match(SUPPORTED_LANGS)
    return best or DEFAULT_LANG


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
        raw_history = json.loads(file_info.get("content", "[]"))
    except ValueError:
        return []

    normalized = []
    for entry in raw_history:
        entry.setdefault("cheapest_price", entry.get("price"))
        entry.setdefault("cheapest_match", entry.get("match"))
        entry.setdefault("prices", {})
        normalized.append(entry)

    return normalized


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
    """Berechnet die Preise aller Matches (fixer Referenz-Rabatt) und hängt
    einen vollständigen Snapshot an die Gist-History an."""
    if not history_enabled():
        return []

    results, _ = compute_results(team_tokens, HISTORY_DISCOUNT)
    history = load_history_from_gist()

    if not results:
        return history

    cheapest = results[0]

    history.append(
        {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "cheapest_price": round(cheapest["price_eur"], 2),
            "cheapest_match": f"{cheapest['team1']} vs {cheapest['team2']}",
            "prices": {str(r["match_index"]): round(r["price_eur"], 2) for r in results},
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

    for idx, match in enumerate(matches):
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
                "match_index": idx,
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
    """Erwartet einen Prozentwert als String und liefert einen Faktor
    zwischen 0 und 0.999 zurück. Bei ungültiger Eingabe wird der
    Standardwert genutzt."""
    if raw_value is None or raw_value == "":
        return DEFAULT_DISCOUNT
    try:
        percent = float(raw_value)
    except ValueError:
        return DEFAULT_DISCOUNT

    percent = max(0.0, min(percent, 99.9))
    return percent / 100


def compute_history_stats(history):
    if not history:
        return None

    prices = [h["cheapest_price"] for h in history]
    timestamps = [h["timestamp"] for h in history]
    current = prices[-1]

    # "Änderung": letzte tatsächliche Preisbewegung — überspringt Wiederholungen,
    # bei denen sich der Preis zwischen zwei Aktualisierungen nicht bewegt hat.
    previous = None
    for p in reversed(prices[:-1]):
        if p != current:
            previous = p
            break

    change_abs = round(current - previous, 2) if previous is not None else None
    change_pct = (
        round((current - previous) / previous * 100, 1)
        if previous not in (None, 0)
        else None
    )

    # Zusätzlich: Änderung über die letzten ~24 Stunden, falls genug History vorhanden.
    change_24h_abs = None
    change_24h_pct = None
    if len(prices) > 1:
        try:
            current_dt = datetime.strptime(timestamps[-1], "%Y-%m-%dT%H:%M:%S")
            target_dt = current_dt - timedelta(hours=24)

            ref_price = prices[0]  # Fallback: ältester verfügbarer Punkt
            for ts, p in zip(timestamps, prices):
                dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
                if dt <= target_dt:
                    ref_price = p
                else:
                    break

            change_24h_abs = round(current - ref_price, 2)
            if ref_price:
                change_24h_pct = round((current - ref_price) / ref_price * 100, 1)
        except ValueError:
            pass

    return {
        "current": round(current, 2),
        "change_abs": change_abs,
        "change_pct": change_pct,
        "change_24h_abs": change_24h_abs,
        "change_24h_pct": change_24h_pct,
        "min": round(min(prices), 2),
        "max": round(max(prices), 2),
        "avg": round(sum(prices) / len(prices), 2),
        "count": len(prices),
    }


def build_sparkline_svg(prices, width=90, height=26):
    """Baut eine winzige Inline-SVG-Sparkline aus einer Preisliste (chronologisch)."""
    if len(prices) < 2:
        return ""

    min_p, max_p = min(prices), max(prices)
    price_range = (max_p - min_p) or 1
    n = len(prices)
    pad = 2

    points = []
    for i, p in enumerate(prices):
        x = pad + (i / (n - 1)) * (width - 2 * pad)
        y = height - pad - ((p - min_p) / price_range) * (height - 2 * pad)
        points.append(f"{x:.1f},{y:.1f}")

    stroke = "#e8607a" if prices[-1] > prices[0] else "#6ee7a8"
    poly = " ".join(points)

    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'class="sparkline" preserveAspectRatio="none">'
        f'<polyline fill="none" stroke="{stroke}" stroke-width="1.6" '
        f'stroke-linejoin="round" stroke-linecap="round" points="{poly}" />'
        f"</svg>"
    )


def _parse_ts(ts):
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")


def _holt_damped_fit(ys, alpha, beta, phi):
    """Gedämpftes Holt-Verfahren (Level + Trend) über eine als gleichabständig
    behandelte Serie. Liefert (level, trend, residuals) — die Residuen sind die
    Fehler der einschrittigen Vorhersagen und dienen Backtest + Konfidenzband."""
    level = ys[0]
    trend = ys[1] - ys[0]
    residuals = []
    for y in ys[1:]:
        forecast = level + phi * trend
        residuals.append(y - forecast)
        new_level = alpha * y + (1 - alpha) * (level + phi * trend)
        trend = beta * (new_level - level) + (1 - beta) * phi * trend
        level = new_level
    return level, trend, residuals


def _holt_damped_best(ys, phi=0.9):
    """Kleiner Grid-Search über Glättungsparameter, minimiert den MAE der
    einschrittigen Vorhersagen."""
    best = None
    for alpha in (0.2, 0.4, 0.6):
        for beta in (0.05, 0.15, 0.3):
            level, trend, residuals = _holt_damped_fit(ys, alpha, beta, phi)
            mae = sum(abs(r) for r in residuals) / len(residuals)
            if best is None or mae < best["mae"]:
                best = {
                    "level": level,
                    "trend": trend,
                    "residuals": residuals,
                    "mae": mae,
                    "phi": phi,
                }
    return best


def _seasonal_slot(dt):
    """3-Stunden-Block der Tageszeit (0-7)."""
    return dt.hour // 3


def _seasonal_profile(timestamps, prices):
    """Additives Tageszeitprofil: Preise werden mit einem zentrierten gleitenden
    Tagesmittel detrended, die Abweichungen pro 3h-Block gesammelt und je Block
    der Median gebildet. Blöcke mit < 2 Beobachtungen erhalten 0 (neutral)."""
    n = len(prices)
    span_h = (timestamps[-1] - timestamps[0]).total_seconds() / 3600.0
    if span_h <= 0:
        return None
    avg_interval_h = span_h / (n - 1)
    window = max(3, round(24.0 / avg_interval_h))  # ~1 Tag an Punkten
    half = window // 2

    deviations = {}
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        local_mean = sum(prices[lo:hi]) / (hi - lo)
        slot = _seasonal_slot(timestamps[i])
        deviations.setdefault(slot, []).append(prices[i] - local_mean)

    profile = {}
    for slot in range(8):
        vals = sorted(deviations.get(slot, []))
        if len(vals) < 2:
            profile[slot] = 0.0
            continue
        m = len(vals)
        profile[slot] = (
            vals[m // 2] if m % 2 else (vals[m // 2 - 1] + vals[m // 2]) / 2
        )
    return profile


def _quantile(sorted_vals, q):
    """Empirisches Quantil (lineare Interpolation) einer sortierten Liste."""
    if not sorted_vals:
        return 0.0
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def compute_price_prediction(history, future_points=6, horizon_hours=24):
    """Prognose der günstigsten Kombination: gedämpftes Holt-Verfahren
    (Level + Trend) plus optionales additives Tageszeitprofil (3h-Blöcke).

    Das Profil wird nur angewendet, wenn es im Backtest den mittleren
    einschrittigen Fehler (MAE) um mindestens 5 % senkt — sonst fällt das
    Modell automatisch auf reines Level+Trend zurück.

    Zusätzlich werden zwei Szenarien aus den empirischen Residuen-Quantilen
    abgeleitet: optimistisch (20 %-Quantil, aus Käufersicht = günstiger) und
    konservativ (80 %-Quantil). Die Spreizung wächst mit dem Horizont.
    Keine verlässliche Vorhersage — nur eine statistische Fortschreibung."""
    if len(history) < 5:
        return None

    try:
        timestamps = [_parse_ts(h["timestamp"]) for h in history]
        prices = [float(h["cheapest_price"]) for h in history]
    except (KeyError, TypeError, ValueError):
        return None

    # --- Variante A: reines Level+Trend auf den Rohpreisen -----------------
    model_plain = _holt_damped_best(prices)

    # --- Variante B: Level+Trend auf saisonbereinigter Serie ---------------
    profile = _seasonal_profile(timestamps, prices)
    model_seasonal = None
    if profile is not None:
        adjusted = [
            p - profile[_seasonal_slot(ts)] for ts, p in zip(timestamps, prices)
        ]
        fitted = _holt_damped_best(adjusted)
        # Backtest-Residuen zurück auf die Originalskala: der einschrittige
        # Fehler in der bereinigten Serie entspricht dem Fehler der
        # Gesamtvorhersage (Holt + Profil) gegen den echten Preis.
        model_seasonal = fitted

    # --- Signifikanz-Check: Profil nur bei >= 5 % MAE-Verbesserung ---------
    seasonality_used = (
        model_seasonal is not None
        and model_seasonal["mae"] <= 0.95 * model_plain["mae"]
    )
    model = model_seasonal if seasonality_used else model_plain

    # --- Punktprognose ------------------------------------------------------
    phi = model["phi"]
    step = horizon_hours / future_points
    last_ts = timestamps[-1]

    future_labels = []
    central = []
    damp_sum = 0.0
    for i in range(1, future_points + 1):
        damp_sum += phi ** i
        base = model["level"] + model["trend"] * damp_sum
        future_ts = last_ts + timedelta(hours=step * i)
        if seasonality_used:
            base += profile[_seasonal_slot(future_ts)]
        future_labels.append(future_ts.strftime("%Y-%m-%dT%H:%M:%S"))
        central.append(max(base, 0.0))

    # --- Szenarien aus Residuen-Quantilen ----------------------------------
    sorted_res = sorted(model["residuals"])
    q_low = _quantile(sorted_res, 0.2)   # typischerweise negativ
    q_high = _quantile(sorted_res, 0.8)  # typischerweise positiv
    # Anzahl einschrittiger Intervalle, die ein Prognoseschritt abdeckt —
    # die Unsicherheit wächst näherungsweise mit der Wurzel des Horizonts.
    span_h = (timestamps[-1] - timestamps[0]).total_seconds() / 3600.0
    avg_interval_h = max(span_h / (len(prices) - 1), 1e-6)
    steps_per_point = step / avg_interval_h

    optimistic = []
    conservative = []
    for i, base in enumerate(central, start=1):
        scale = (i * steps_per_point) ** 0.5
        optimistic.append(max(base + q_low * scale, 0.0))
        conservative.append(max(base + q_high * scale, 0.0))

    return {
        "labels": future_labels,
        "prices": [round(p, 2) for p in central],
        "optimistic": [round(p, 2) for p in optimistic],
        "conservative": [round(p, 2) for p in conservative],
        "seasonality_used": seasonality_used,
        "mae": round(model_plain["mae"], 3),
        "mae_seasonal": (
            round(model_seasonal["mae"], 3) if model_seasonal else None
        ),
    }


def compute_facts(history):
    """Berechnet ein paar kurze, 'Twitter-artige' Fakten aus der History.
    Liefert strukturierte Daten (sprachneutral) — Formatierung passiert im
    Frontend anhand der aktuellen Sprache."""
    if len(history) < 3:
        return []

    matches = load_matches()

    def label_for(idx):
        m = matches[int(idx)]
        return f"{m['team1']} vs {m['team2']}"

    series = {}
    for snap in history:
        for idx, price in snap.get("prices", {}).items():
            series.setdefault(idx, []).append((snap["timestamp"], price))

    now_dt = _parse_ts(history[-1]["timestamp"])

    def duration_seconds(ts_start):
        return (now_dt - _parse_ts(ts_start)).total_seconds()

    facts = []

    # Fakt: Preis hat sich nie verändert (längste Serie mit min. 3 Punkten)
    unchanged = [
        (idx, pts) for idx, pts in series.items()
        if len(pts) >= 3 and len({p for _, p in pts}) == 1
    ]
    if unchanged:
        idx, pts = max(unchanged, key=lambda x: len(x[1]))
        facts.append({
            "type": "never_changed",
            "match": label_for(idx),
            "duration_seconds": duration_seconds(pts[0][0]),
            "price": pts[-1][1],
        })

    # Fakten: aktuelle Serie als teuerstes / günstigstes Match
    expensive_seq = []
    cheap_seq = []
    for snap in history:
        prices = snap.get("prices", {})
        if not prices:
            continue
        max_idx = max(prices, key=lambda k: prices[k])
        min_idx = min(prices, key=lambda k: prices[k])
        expensive_seq.append((snap["timestamp"], max_idx, prices[max_idx]))
        cheap_seq.append((snap["timestamp"], min_idx, prices[min_idx]))

    def current_streak(seq):
        if not seq:
            return None
        last_idx = seq[-1][1]
        streak = [seq[-1]]
        for item in reversed(seq[:-1]):
            if item[1] == last_idx:
                streak.append(item)
            else:
                break
        streak.reverse()
        return last_idx, streak

    result = current_streak(expensive_seq)
    if result:
        idx, streak = result
        if len(streak) >= 2:
            facts.append({
                "type": "longest_expensive",
                "match": label_for(idx),
                "duration_seconds": duration_seconds(streak[0][0]),
                "price": streak[-1][2],
            })

    result = current_streak(cheap_seq)
    if result:
        idx, streak = result
        if len(streak) >= 2:
            facts.append({
                "type": "longest_cheapest",
                "match": label_for(idx),
                "duration_seconds": duration_seconds(streak[0][0]),
                "price": streak[-1][2],
            })

    # Fakt: größter Ausschlag in ~24h
    target_dt = now_dt - timedelta(hours=24)
    best_idx, best_pct, best_current = None, 0, None
    for idx, pts in series.items():
        current_price = pts[-1][1]
        ref_price = pts[0][1]
        for ts, p in pts:
            if _parse_ts(ts) <= target_dt:
                ref_price = p
            else:
                break
        if ref_price:
            pct = (current_price - ref_price) / ref_price * 100
            if abs(pct) > abs(best_pct):
                best_pct, best_idx, best_current = pct, idx, current_price

    if best_idx is not None and abs(best_pct) >= 0.5:
        facts.append({
            "type": "mover_up" if best_pct > 0 else "mover_down",
            "match": label_for(best_idx),
            "percent": round(best_pct, 1),
            "price": best_current,
        })

    return facts[:4]


def build_sparklines(results, history):
    if not history:
        return {}

    match_indices = {r["match_index"] for r in results}
    series = {idx: [] for idx in match_indices}

    for snapshot in history:
        snapshot_prices = snapshot.get("prices", {})
        for idx in match_indices:
            value = snapshot_prices.get(str(idx))
            if value is not None:
                series[idx].append(value)

    return {
        idx: build_sparkline_svg(prices[-SPARKLINE_POINTS:])
        for idx, prices in series.items()
        if len(prices) >= 2
    }


def build_page_data(force_token_refresh=False, lang=DEFAULT_LANG):
    discount = parse_discount(request.args.get("discount"))
    team_tokens, error = get_team_tokens(force=force_token_refresh)
    results, missing = compute_results(team_tokens, discount)

    chart_size = 15
    top_results = results[:chart_size]

    history = _cache["history"]

    sparklines = build_sparklines(results, history)
    for r in results:
        r["sparkline_svg"] = sparklines.get(r["match_index"], "")

    match_options = sorted(
        (
            {"index": r["match_index"], "label": f"{r['team1']} vs {r['team2']}"}
            for r in results
        ),
        key=lambda x: x["label"],
    )

    discount_percent = round(discount * 100, 2)
    preset_values = {p["discount"] for p in DISCOUNT_PRESETS}
    is_custom_discount = discount_percent not in preset_values

    return {
        "results": results,
        "missing": missing,
        "team_count": len(team_tokens),
        "generated_at": time.strftime("%d.%m.%Y %H:%M:%S"),
        "error": error,
        "discount_percent": discount_percent,
        "is_custom_discount": is_custom_discount,
        "chart_labels": [f"{r['team1']} vs {r['team2']}" for r in top_results],
        "chart_prices": [round(r["price_eur"], 2) for r in top_results],
        "history_enabled": history_enabled(),
        "history_labels": [h["timestamp"] for h in history],
        "history_prices": [h["cheapest_price"] for h in history],
        "history_stats": compute_history_stats(history),
        "history_prediction": compute_price_prediction(history),
        "match_options": match_options,
        "facts": compute_facts(history),
        "t": TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANG]),
        "current_lang": lang,
        "supported_langs": SUPPORTED_LANGS,
        "lang_labels": LANG_LABELS,
        "discount_presets": DISCOUNT_PRESETS,
    }


def render_with_lang(force_token_refresh=False):
    lang = resolve_lang()
    discount = parse_discount(request.args.get("discount"))
    discount_percent = round(discount * 100, 2)
    preset_values = {p["discount"] for p in DISCOUNT_PRESETS}
    is_custom_discount = discount_percent not in preset_values

    resp = make_response(
        render_template(
            "index.html",
            t=TRANSLATIONS.get(lang, TRANSLATIONS[DEFAULT_LANG]),
            current_lang=lang,
            supported_langs=SUPPORTED_LANGS,
            lang_labels=LANG_LABELS,
            discount_presets=DISCOUNT_PRESETS,
            discount_percent=discount_percent,
            is_custom_discount=is_custom_discount,
            history_enabled=history_enabled(),
        )
    )
    resp.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365)
    return resp


# ============================================================
# Routen
# ============================================================

@app.route("/")
def index():
    # Rendert die Seite SOFORT (Shell + Skeleton), ohne auf die externe
    # Preis-API zu warten. Die eigentlichen Daten lädt der Browser danach
    # per /api/page-data nach — dadurch hängt die Seite auch bei einem
    # Render-Kaltstart oder einer langsamen Volatile-Shop-API nicht.
    return render_with_lang()


@app.route("/api/page-data")
def api_page_data():
    lang = resolve_lang()
    try:
        data = build_page_data(lang=lang)
    except Exception as exc:  # noqa: BLE001 - Fehler ans Frontend durchreichen statt 500
        return {"error": str(exc)}

    data.pop("t", None)
    data.pop("supported_langs", None)
    data.pop("lang_labels", None)
    data.pop("discount_presets", None)
    data.pop("current_lang", None)
    return data


@app.route("/api/history/<int:match_index>")
def api_match_history(match_index):
    history = _cache["history"]

    labels = []
    prices = []
    for snapshot in history:
        value = snapshot.get("prices", {}).get(str(match_index))
        if value is not None:
            labels.append(snapshot["timestamp"])
            prices.append(value)

    return {"labels": labels, "prices": prices}


@app.route("/refresh")
def refresh():
    # Leichtgewichtiger Endpunkt, gedacht für einen externen Cron-Dienst
    # (z. B. cron-job.org), der die Preise auch ohne offenen Browser-Tab
    # periodisch aktualisiert.
    try:
        get_team_tokens(force=True)
        return {"status": "ok", "generated_at": time.strftime("%d.%m.%Y %H:%M:%S")}
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": str(exc)}, 500


if __name__ == "__main__":
    app.run(debug=True)
