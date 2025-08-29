from flask import Flask, render_template_string
from sqlalchemy import text
from db import conn
# app.py (добавь в начало рядом с остальным кодом)
import os
from sqlalchemy import text
from db import conn, init_schema
from betcity_api import load_score, iter_table_tennis_events_from_score, load_soon, iter_tt_events_from_soon
from model import build_point_skills_from_rows, simulate_match, prob_A_handicap_points, prob_total_points_over
from datetime import date, timedelta
import json

CRON_TOKEN = os.getenv("CRON_TOKEN", "")  # задашь в Render → Environment

def _upsert_match(c, row):
    c.execute(text("""
        INSERT INTO matches(id_ev, date_ev, tour, player_a, player_b, sc_ev, sc_ext_ev)
        VALUES(:id_ev, :date_ev, :tour, :player_a, :player_b, :sc_ev, :sc_ext_ev)
        ON CONFLICT (id_ev) DO UPDATE SET
          date_ev=EXCLUDED.date_ev, tour=EXCLUDED.tour,
          player_a=EXCLUDED.player_a, player_b=EXCLUDED.player_b,
          sc_ev=EXCLUDED.sc_ev, sc_ext_ev=EXCLUDED.sc_ext_ev;
    """), row)

def _fetch_all_matches(c):
    rows = c.execute(text("SELECT date_ev, tour, player_a, player_b, sc_ev, sc_ext_ev FROM matches")).mappings().all()
    return [dict(r) for r in rows]

# Эндпоинт: обновить результаты
@app.route("/cron/results")
def cron_results():
    from flask import request, jsonify
    if request.args.get("token") != CRON_TOKEN:
        return ("forbidden", 403)
    init_schema()
    for d in [date.today(), date.today()-timedelta(days=1)]:
        payload = load_score(d.isoformat())
        with conn() as c:
            for ev in iter_table_tennis_events_from_score(payload, d.isoformat()):
                if ev["player_a"] and ev["player_b"]:
                    _upsert_match(c, ev)
    return jsonify({"ok": True})

# Эндпоинт: посчитать прогнозы на сегодня
@app.route("/cron/predictions")
def cron_predictions():
    from flask import request, jsonify
    if request.args.get("token") != CRON_TOKEN:
        return ("forbidden", 403)
    init_schema()
    with conn() as c:
        hist = _fetch_all_matches(c)
    skills = build_point_skills_from_rows(hist, alpha=80.0)

    payload = load_soon(date.today().isoformat())
    HCP_LINES = (-7.5,-5.5,-3.5,-1.5, +1.5,+3.5,+5.5,+7.5)
    TOT_LINES = (60.5,65.5,70.5,75.5,80.5,85.5)

    for ev in iter_tt_events_from_soon(payload):
        sim = simulate_match(ev["player_a"], ev["player_b"], skills, series_len=ev["series_len"], n_sims=15000)
        hcp = { str(h): prob_A_handicap_points(sim["pm"], h) for h in HCP_LINES }
        tot = { str(t): prob_total_points_over(sim["tp"], t) for t in TOT_LINES }
        with conn() as c:
            c.execute(text("""
                INSERT INTO predictions(id_ev, date_ev, tour, player_a, player_b, series_len, pA, pB, hcp_points, tot_points)
                VALUES(:id_ev, :date_ev, :tour, :player_a, :player_b, :series_len, :pA, :pB, :hcp_points::jsonb, :tot_points::jsonb)
                ON CONFLICT (id_ev) DO UPDATE SET
                    gen_ts = NOW(),
                    date_ev=EXCLUDED.date_ev, tour=EXCLUDED.tour,
                    player_a=EXCLUDED.player_a, player_b=EXCLUDED.player_b,
                    series_len=EXCLUDED.series_len, pA=EXCLUDED.pA, pB=EXCLUDED.pB,
                    hcp_points=EXCLUDED.hcp_points, tot_points=EXCLUDED.tot_points;
            """), dict(
                id_ev=ev["id_ev"], date_ev=ev["date_ev"], tour=ev["tour"],
                player_a=ev["player_a"], player_b=ev["player_b"], series_len=ev["series_len"],
                pA=sim["pA"], pB=sim["pB"],
                hcp_points=json.dumps(hcp), tot_points=json.dumps(tot),
            ))
    return jsonify({"ok": True})

TEMPLATE = """
<!doctype html><html><head>
<meta charset="utf-8"><title>Table Tennis Predictions</title>
<style>
body{font:14px/1.4 system-ui,Arial,sans-serif;padding:20px}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #ddd;padding:6px 8px;text-align:center}
th{background:#f3f4f6}
.small{font-size:12px;color:#666}
</style></head><body>
<h2>Настольный теннис — прогнозы (обновляются каждые 5 минут)</h2>
<p class="small">Вероятности побед (pA/pB), форы по очкам и тоталы по очкам (Over). Для форы линия дана для игрока A (левый в паре).</p>
<table>
  <thead>
    <tr>
      <th>Дата</th><th>Турнир</th><th>Матч</th><th>Формат</th>
      <th>pA</th><th>pB</th>
      <th colspan="6">Фора очки (A)</th>
      <th colspan="6">Тотал очки (Over)</th>
    </tr>
  </thead>
  <tbody>
    {% for r in rows %}
    <tr>
      <td>{{r.date_ev}}</td>
      <td>{{r.tour}}</td>
      <td>{{r.player_a}} vs {{r.player_b}}</td>
      <td>best-of-{{r.series_len}}</td>
      <td>{{"%.3f"|format(r.pA)}}</td>
      <td>{{"%.3f"|format(r.pB)}}</td>
      {% for h in hcp_order %}
        <td>{{"%.3f"|format(r.hcp_points.get(h, None) or 0)}}</td>
      {% endfor %}
      {% for t in tot_order %}
        <td>{{"%.3f"|format(r.tot_points.get(t, None) or 0)}}</td>
      {% endfor %}
    </tr>
    {% endfor %}
  </tbody>
</table>
<p class="small">Сервис Render • БД PostgreSQL.</p>
</body></html>
"""

app = Flask(__name__)

@app.route("/")
def index():
    with conn() as c:
        rows = c.execute(text("""
            SELECT id_ev, date_ev, tour, player_a, player_b, series_len, pA, pB, hcp_points::text, tot_points::text
            FROM predictions
            ORDER BY gen_ts DESC, date_ev ASC
            LIMIT 200
        """)).fetchall()

    import json
    recs = []
    for r in rows:
        recs.append(dict(
            id_ev=r.id_ev, date_ev=r.date_ev, tour=r.tour,
            player_a=r.player_a, player_b=r.player_b,
            series_len=r.series_len, pA=r.pA, pB=r.pB,
            hcp_points=json.loads(r.hcp_points or "{}"),
            tot_points=json.loads(r.tot_points or "{}"),
        ))

    # порядок колонок в таблице:
    hcp_order = [ "-7.5","-5.5","-3.5","-1.5","+1.5","+3.5","+5.5","+7.5" ]
    tot_order = [ "60.5","65.5","70.5","75.5","80.5","85.5" ]
    return render_template_string(TEMPLATE, rows=recs, hcp_order=hcp_order, tot_order=tot_order)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
