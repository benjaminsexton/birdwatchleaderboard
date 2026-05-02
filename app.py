import requests
from flask import Flask, jsonify, render_template_string
from datetime import datetime, timezone
import config

app = Flask(__name__)

def get_data(endpoint, api_key, params=None):
    url = f"https://api.ebird.org/v2/{endpoint}"
    headers = {"X-eBirdApiToken": api_key}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        return r.json() if r.status_code == 200 else []
    except:
        return []

@app.route("/")
def index():
    return render_template_string(HTML_UI)

@app.route("/api/leaderboard")
def leaderboard():
    results = []
    # Dates for filtering sightings
    start_day = config.START_DATE.date()
    end_day = config.END_DATE.date()

    for user in config.COMPETITORS:
        # Get last 30 days of sightings
        raw_obs = get_data(f"data/obs/{user['ebird_username']}/recent", user['api_key'], {"detail": "full"})
        
        # Filter sightings by date and remove duplicates
        unique_list = {}
        for obs in raw_obs:
            obs_dt = datetime.strptime(obs['obsDt'][:10], "%Y-%m-%d").date()
            if start_day <= obs_dt <= end_day:
                code = obs['speciesCode']
                if code not in unique_list:
                    # Get the specific checklist comments for this bird
                    checklist = get_data(f"product/checklist/view/{obs['subId']}", user['api_key'])
                    obs['user_notes'] = checklist.get('comments', '') if isinstance(checklist, dict) else ''
                    unique_list[code] = obs

        results.append({
            "name": user['real_name'],
            "count": len(unique_list),
            "birds": list(unique_list.values())
        })

    return jsonify({
        "title": config.TITLE,
        "start": config.START_DATE.isoformat(),
        "end": config.END_DATE.isoformat(),
        "players": sorted(results, key=lambda x: x['count'], reverse=True)
    })

# The "Face" of your website
HTML_UI = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sexton Birding</title>
    <style>
        body { background: #0d1117; color: #c9d1d9; font-family: -apple-system, sans-serif; text-align: center; padding: 20px; }
        .logo { width: 120px; margin-bottom: 20px; }
        .timer-box { background: #161b22; border: 2px solid #30363d; padding: 20px; border-radius: 15px; margin: 20px auto; max-width: 400px; }
        .timer-val { font-size: 2.5rem; color: #f85149; font-weight: bold; display: block; }
        .player-card { background: #161b22; border: 1px solid #30363d; padding: 15px; border-radius: 10px; margin: 10px auto; max-width: 450px; text-align: left; }
        .score { float: right; font-size: 1.8rem; color: #58a6ff; }
        .notes { font-size: 0.85rem; color: #8b949e; font-style: italic; margin-top: 5px; border-left: 2px solid #30363d; padding-left: 10px; }
    </style>
</head>
<body>
    <img src="/static/image_a23c6a.png" class="logo" alt="Logo">
    <h1 id="main-title">Loading...</h1>
    
    <div class="timer-box">
        <span id="timer-label" style="font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px;">Loading Countdown...</span>
        <span id="timer-display" class="timer-val">00:00:00</span>
    </div>

    <div id="leaderboard"></div>

    <script>
        async function refresh() {
            const r = await fetch('/api/leaderboard');
            const d = await r.json();
            document.getElementById('main-title').innerText = d.title;

            // Timer Logic
            const now = new Date();
            const start = new Date(d.start);
            const end = new Date(d.end);
            const display = document.getElementById('timer-display');
            const label = document.getElementById('timer-label');

            if (now < start) {
                label.innerText = "Competition Starts In";
                const diff = start - now;
                const m = Math.floor(diff / 60000);
                const s = Math.floor((diff % 60000) / 1000);
                display.innerText = m + "m " + s + "s";
            } else if (now < end) {
                label.innerText = "Competition Ends In";
                const diff = end - now;
                const days = Math.floor(diff / 86400000);
                const hrs = Math.floor((diff % 86400000) / 3600000);
                display.innerText = days + "d " + hrs + "h";
            } else {
                label.innerText = "Status";
                display.innerText = "Finished";
            }

            // Players Logic
            let html = "";
            d.players.forEach(p => {
                html += `<div class="player-card">
                    <span class="score">${p.count}</span>
                    <strong style="font-size: 1.2rem;">${p.name}</strong>
                    <div style="margin-top:10px;">
                        ${p.birds.slice(0,3).map(b => `
                            <div style="margin-bottom:8px;">
                                <span>• ${b.comName}</span>
                                ${b.user_notes ? `<div class="notes">"${b.user_notes}"</div>` : ''}
                            </div>
                        `).join('')}
                        ${p.count > 3 ? `<small style="color:#8b949e">...and ${p.count - 3} more</small>` : ''}
                    </div>
                </div>`;
            });
            document.getElementById('leaderboard').innerHTML = html;
        }

        setInterval(refresh, 1000);
        refresh();
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(debug=True)