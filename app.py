import requests
from flask import Flask, jsonify, render_template_string
from datetime import datetime
import config

app = Flask(__name__)

# New logo filename
LOGO_FILENAME = "6fd74d3c-95f0-46e8-ae74-c52a1c873ca2.png"

def get_active_season():
    # Safely get the season from config to prevent Internal Server Errors
    season_key = getattr(config, 'CURRENT_SEASON', None)
    seasons_dict = getattr(config, 'SEASONS', {})
    return seasons_dict.get(season_key)

def get_ebird(endpoint, api_key, params=None):
    url = f"https://api.ebird.org/v2/{endpoint}"
    try:
        r = requests.get(url, headers={"X-eBirdApiToken": api_key}, params=params, timeout=10)
        return r.json() if r.status_code == 200 else []
    except:
        return []

@app.route("/")
def index():
    season = get_active_season()
    # If the config is broken, show a helpful error instead of a crash
    if not season:
        return f"<h1>Config Error</h1><p>Check your Secret File. CURRENT_SEASON ('{getattr(config, 'CURRENT_SEASON', 'None')}') must match a key in your SEASONS dictionary.</p>", 500
    return render_template_string(HTML_UI, title=season.get('title', 'Birding Comp'), logo=LOGO_FILENAME)

@app.route("/api/leaderboard")
def leaderboard():
    season = get_active_season()
    if not season:
        return jsonify({"error": "Season not found"}), 500

    start_dt = season['start'].date()
    end_dt = season['end'].date()
    all_players_data = []

    for user in config.COMPETITORS:
        # NEW ENDPOINT: This pulls YOUR specific observations directly
        # It's much more reliable than the 'recent' feed for new games
        # Fetch the user's recent checklists then pull species from each
        lists = get_ebird(f"product/lists/{user['ebird_username']}", user['api_key'], {
            "maxResults": "200"
        })

        user_birds = {}
        if isinstance(lists, list):
            for cl in lists:
                try:
                    o_dt = datetime.strptime(cl['obsDt'][:10], "%Y-%m-%d").date()
                    if not (start_dt <= o_dt <= end_dt):
                        continue
                    checklist = get_ebird(f"product/checklist/view/{cl['subId']}", user['api_key'])
                    obs = checklist.get('obs', []) if isinstance(checklist, dict) else []
                    for o in obs:
                        code = o.get('speciesCode')
                        if code and code not in user_birds:
                            user_birds[code] = {
                                'speciesCode': code,
                                'comName': o.get('comName', code),
                                'obsDt': cl['obsDt'],
                                'locName': cl.get('loc', {}).get('name', ''),
                                'is_unique': False,
                                'is_first': False,
                            }
                except: continue
        
        all_players_data.append({
            "name": user['real_name'],
            "user": user['ebird_username'],
            "birds": user_birds
        })

    # ... (Keep the rest of your badge and sorting logic the same)
    final_standings = []
    for i, player in enumerate(all_players_data):
        scored_birds = []
        for code, bird in player['birds'].items():
            others = [all_players_data[j]['birds'][code] for j in range(len(all_players_data)) 
                      if i != j and code in all_players_data[j]['birds']]
            
            bird['is_unique'] = len(others) == 0
            if not bird['is_unique']:
                my_time = datetime.strptime(bird['obsDt'], "%Y-%m-%d %H:%M")
                earliest = True
                for ob in others:
                    if datetime.strptime(ob['obsDt'], "%Y-%m-%d %H:%M") < my_time:
                        earliest = False
                bird['is_first'] = earliest
            else:
                bird['is_first'] = True 
            scored_birds.append(bird)

        final_standings.append({
            "name": player['name'],
            "user": player['user'],
            "count": len(scored_birds),
            "birds": sorted(scored_birds, key=lambda x: x['obsDt'], reverse=True)
        })

    return jsonify({
        "start": season['start'].isoformat(),
        "end": season['end'].isoformat(),
        "players": sorted(final_standings, key=lambda x: x['count'], reverse=True)
    })

HTML_UI = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root {
            --ebird-green: #6DB33F; --ebird-blue: #2A7AB0; --ebird-orange: #F4A300;
            --bg-white: #FFFFFF; --panel-gray: #F5F5F5; --border-gray: #E0E0E0; --text-dark: #333;
        }
        body { font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; background: var(--bg-white); color: var(--text-dark); margin: 0; }
        header { border-bottom: 4px solid var(--ebird-green); padding: 20px; text-align: center; }
        .logo { height: 50px; margin-bottom: 10px; }
        .timer-bar { background: var(--panel-gray); border-bottom: 1px solid var(--border-gray); color: var(--ebird-blue); padding: 12px; text-align: center; font-weight: bold; font-size: 0.9rem; text-transform: uppercase; }
        .container { max-width: 800px; margin: auto; padding: 10px; }
        .player-row { display: grid; grid-template-columns: 40px 1fr 100px; align-items: center; padding: 15px; border-bottom: 1px solid var(--border-gray); cursor: pointer; }
        .username { display: block; font-size: 1.2rem; font-weight: 700; color: var(--ebird-blue); text-transform: none !important; }
        .realname { font-size: 0.85rem; color: #666; }
        .count-num { font-size: 1.8rem; font-weight: 700; color: var(--ebird-green); }
        .bird-list { display: none; background: var(--panel-gray); padding: 0 15px; }
        .bird-entry { padding: 12px 0; border-bottom: 1px solid #ddd; }
        .badge { font-size: 0.65rem; padding: 2px 5px; border-radius: 4px; font-weight: 800; margin-left: 5px; vertical-align: middle; }
        .badge-unique { background: #e8f5e9; color: #2e7d32; border: 1px solid #2e7d32; }
        .badge-first { background: #fff3e0; color: #ef6c00; border: 1px solid #ef6c00; }
    </style>
</head>
<body>
    <header>
        <img src="/static/{{ logo }}" class="logo">
        <h1 style="margin:0; font-size: 1.4rem;">{{ title }}</h1>
    </header>
    <div id="timer-bar" class="timer-bar">Loading...</div>
    <div class="container" id="leaderboard"></div>
    <script>
        async function update() {
            const r = await fetch('/api/leaderboard');
            if (!r.ok) return;
            const d = await r.json();
            const now = new Date();
            const start = new Date(d.start);
            const end = new Date(d.end);
            const tBar = document.getElementById('timer-bar');

            if (now < start) {
                const diff = start - now;
                const days = Math.floor(diff / 86400000);
                const hrs = Math.floor((diff % 86400000) / 3600000);
                const mins = Math.floor((diff % 3600000) / 60000);
                const secs = Math.floor((diff % 60000) / 1000);
                tBar.innerHTML = `Starts in: <span style="color:var(--ebird-orange)">${days}d ${hrs}h ${mins}m ${secs}s</span>`;
            } else if (now < end) {
                const diff = end - now;
                tBar.innerHTML = `Time Remaining: ${Math.floor(diff/86400000)} days, ${Math.floor((diff%86400000)/3600000)} hours`;
            } else {
                tBar.innerText = "🏆 COMPETITION COMPLETE";
            }

            let html = "";
            d.players.forEach((p, i) => {
                html += `
                <div class="player-row" onclick="toggle('${p.user}')">
                    <span style="color:#999">${i+1}</span>
                    <div><span class="username">${p.user}</span><span class="realname">${p.name}</span></div>
                    <div style="text-align:right"><span class="count-num">${p.count}</span></div>
                </div>
                <div id="list-${p.user}" class="bird-list">
                    ${p.birds.map(b => `
                        <div class="bird-entry">
                            <strong>${b.comName}</strong>
                            ${b.is_unique ? '<span class="badge badge-unique">ONLY ME</span>' : ''}
                            ${b.is_first ? '<span class="badge badge-first">1ST</span>' : ''}
                            <div style="color:#777; font-size:0.8rem;">${b.obsDt} • ${b.locName}</div>
                        </div>
                    `).join('')}
                </div>`;
            });
            document.getElementById('leaderboard').innerHTML = html;
        }
        function toggle(id) {
            const el = document.getElementById('list-' + id);
            el.style.display = el.style.display === 'block' ? 'none' : 'block';
        }
        setInterval(update, 5000);
        update();
    </script>
</body>
</html>
"""