#!/usr/bin/env python3
import json, os, urllib.request, html, datetime

USER = os.environ.get("GITHUB_USERNAME", "manthannayaks")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUT = "assets/profile-stats.svg"

def main():
    if not TOKEN:
        raise SystemExit("Missing GH_TOKEN / GITHUB_TOKEN")
    query = '''query($login:String!) {
      user(login:$login) {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount color } }
          }
        }
      }
    }'''
    body = json.dumps({"query": query, "variables": {"login": USER}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
        "User-Agent": "manthannayaks-profile-generator"})
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.loads(response.read())
    user = payload.get("data", {}).get("user")
    if payload.get("errors") or not user:
        raise RuntimeError(f"GitHub GraphQL error: {payload.get('errors', 'user not found')}")
    cal = user["contributionsCollection"]["contributionCalendar"]
    total, weeks = cal["totalContributions"], cal["weeks"][-52:]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="220" viewBox="0 0 1000 220"><rect width="100%" height="100%" rx="14" fill="#0d1117" stroke="#30363d"/><text x="24" y="32" fill="#39d353" font-family="monospace" font-size="14">$ github-contributions --year-to-date</text><text x="24" y="68" fill="#e6edf3" font-family="monospace" font-size="28" font-weight="bold">{total:,}</text><text x="110" y="68" fill="#8b949e" font-family="monospace" font-size="13">contributions in the current calendar year</text>']
    sx, sy, cell, gap = 24, 92, 10, 4
    for wi, week in enumerate(weeks):
        for day in week["contributionDays"]:
            dt = datetime.date.fromisoformat(day["date"])
            x, y = sx + wi*(cell+gap), sy + dt.weekday()*(cell+gap)
            color = day.get("color") or "#161b22"
            tip = html.escape(f'{day["date"]}: {day["contributionCount"]} contributions')
            parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{html.escape(color)}"><title>{tip}</title></rect>')
    parts.append('<text x="24" y="202" fill="#8b949e" font-family="monospace" font-size="11">Less</text>')
    for i, color in enumerate(["#161b22","#0e4429","#006d32","#26a641","#39d353"]):
        parts.append(f'<rect x="{70+i*17}" y="192" width="11" height="11" rx="2" fill="{color}"/>')
    parts.append('<text x="166" y="202" fill="#8b949e" font-family="monospace" font-size="11">More · Live data from GitHub GraphQL</text></svg>')
    os.makedirs("assets", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f: f.write("\n".join(parts))
    print(f"Wrote {OUT} ({total} contributions)")

if __name__ == "__main__": main()
