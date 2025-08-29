from flask import Flask, render_template_string
from sqlalchemy import text
from db import conn

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
