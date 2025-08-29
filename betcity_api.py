import re, requests
from datetime import datetime, timedelta
from typing import Dict, List, Any

PAIR_RE = re.compile(r"(\d{1,2})[:\-](\d{1,2})")

def as_str(x): 
    return x if isinstance(x,str) else ("" if x is None else str(x))

def load_score(date_str: str) -> Dict:
    url = f"https://ad.betcity.ru/d/score?rev=5&date={date_str}&ver=43&csn=ooca9s"
    r = requests.get(url, timeout=30); r.raise_for_status()
    return r.json()

def iter_table_tennis_events_from_score(payload: Dict, date_str: str):
    reply = payload.get("reply") or {}
    sports = reply.get("sports") or {}
    for _, sport in sports.items():
        name_sp = as_str(sport.get("name_sp")).lower()
        if "настоль" not in name_sp and "table tennis" not in name_sp:
            continue
        for _, ch in (sport.get("chmps") or {}).items():
            tour = as_str(ch.get("name_ch"))
            for _, ev in (ch.get("evts") or {}).items():
                yield {
                    "id_ev": ev.get("id_ev"),
                    "date_ev": as_str(ev.get("date_ev")) or date_str,
                    "tour": tour,
                    "player_a": as_str(ev.get("name_ht")),
                    "player_b": as_str(ev.get("name_at")),
                    "sc_ev": as_str(ev.get("sc_ev")),
                    "sc_ext_ev": as_str(ev.get("sc_ext_ev")),
                }

def load_soon(date_str: str) -> Dict:
    url = f"https://ad.betcity.ru/d/on_air/soon?rev=3&add=group%2Cdates&fut=1&date={date_str}&ver=43&csn=ooca9s"
    r = requests.get(url, timeout=30); r.raise_for_status()
    return r.json()

def collect_champs(root: Dict):
    reply = root.get("reply") or root
    # reply->sports->*->chmps
    sports = reply.get("sports") or {}
    for _, sp in sports.items():
        ch = sp.get("chmps") or {}
        for v in ch.values(): yield v
    # reply->chmps (иногда так)
    ch2 = reply.get("chmps") or {}
    for v in ch2.values(): yield v

def iter_tt_events_from_soon(payload: Dict):
    from datetime import timezone
    for ch in collect_champs(payload):
        tour = as_str(ch.get("name_ch"))
        if "настоль" not in tour.lower() and "table tennis" not in tour.lower():
            continue
        for _, ev in (ch.get("evts") or {}).items():
            pa = as_str(ev.get("name_ht")); pb = as_str(ev.get("name_at"))
            if not pa or not pb: 
                continue
            comment = as_str(ev.get("comment_ev")).lower()
            series = 7 if "7" in comment else 5
            ts = ev.get("date_ev")
            if isinstance(ts,(int,float)):
                date_val = datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M UTC")
            else:
                date_val = as_str(ev.get("date_ev_str")) or as_str(ts) or ""
            yield {
                "id_ev": ev.get("id_ev"),
                "date_ev": date_val,
                "tour": tour,
                "player_a": pa,
                "player_b": pb,
                "series_len": series
            }
