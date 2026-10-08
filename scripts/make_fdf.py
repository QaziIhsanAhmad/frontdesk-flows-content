"""Read (and optionally act on) the FrontDesk Flows Make.com organisation (eu1, org 9158640).
Token: GitHub secret MAKE_EU1_TOKEN (never printed). Writes make-audit/latest.json (no secrets).
ACTION env: audit (default) | run:<scenarioId> | activate:<scenarioId> | daily:<scenarioId>:<HH:MM>"""
import json, os, urllib.request, urllib.parse, datetime as dt

BASE = "https://eu1.make.com/api/v2"
ORG = 9158640
TOK = os.environ["MAKE_EU1_TOKEN"]

def call(path, method="GET", body=None):
    req = urllib.request.Request(BASE + path, method=method,
        headers={"Authorization": "Token " + TOK, "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) fdf-audit/1.0"},
        data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_body": e.read().decode()[:500]}

def clean(o):
    if isinstance(o, dict):
        return {k: ("<redacted>" if any(s in k.lower() for s in ("token", "password", "secret", "apikey")) else clean(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    return o

out = {"at": dt.datetime.utcnow().isoformat() + "Z", "action": os.environ.get("ACTION", "audit")}
act = out["action"].split(":")
if act[0] == "run":
    out["result"] = call(f"/scenarios/{act[1]}/run", "POST", {"responsive": True})
elif act[0] == "activate":
    out["result"] = call(f"/scenarios/{act[1]}/start", "POST", {})
elif act[0] == "fix":
    # fix:<id>:<intervalSeconds>:<maxResults>  -> correct video_url mapping, throttle, reschedule, start
    sid, interval, maxr = act[1], int(act[2]), int(act[3])
    bp = call(f"/scenarios/{sid}/blueprint")["response"]["blueprint"]
    for m in bp["flow"]:
        if m["module"].startswith("rss:"):
            m["parameters"]["maxResults"] = maxr
        if m["module"] == "instagram-business:CreateAReelPost":
            m["mapper"]["video_url"] = "{{1.url}}"
    # check feed video URLs are reachable before enabling
    import re
    feed = urllib.request.urlopen(urllib.request.Request("https://raw.githubusercontent.com/QaziIhsanAhmad/frontdesk-flows-content/main/reels-feed.xml", headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read().decode()
    links = re.findall(r"<link>(https://cdn[^<]+)</link>", feed)
    checks = []
    for u in links:
        try:
            r = urllib.request.urlopen(urllib.request.Request(u, method="HEAD", headers={"User-Agent": "Mozilla/5.0"}), timeout=30)
            checks.append([u[-40:], r.status, r.headers.get("Content-Length"), r.headers.get("Content-Type")])
        except Exception as e:
            checks.append([u[-40:], str(e)])
    out["feed_checks"] = checks
    out["patch"] = call(f"/scenarios/{sid}", "PATCH", {"blueprint": json.dumps(bp), "scheduling": json.dumps({"type": "indefinitely", "interval": interval})})
    if all(len(c) > 2 and c[1] == 200 for c in checks):
        out["start"] = call(f"/scenarios/{sid}/start", "POST", {})
    else:
        out["start"] = "skipped: feed URL check failed"
elif act[0] == "daily":
    out["result"] = call(f"/scenarios/{act[1]}", "PATCH", {"scheduling": json.dumps({"type": "daily", "time": act[2]})})

teams = call(f"/teams?organizationId={ORG}")
out["teams"] = teams
out["scenarios"] = []
for t in teams.get("teams", []):
    sc = call(f"/scenarios?teamId={t['id']}")
    for s in sc.get("scenarios", []):
        sid = s["id"]
        full = call(f"/scenarios/{sid}/blueprint")
        logs = call(f"/scenarios/{sid}/logs?pg%5Blimit%5D=50&pg%5BsortDir%5D=desc")
        details = []
        for lg in (logs.get("scenarioLogs") or [])[:25]:
            eid = lg.get("id") or lg.get("imtId")
            d = call(f"/scenarios/{sid}/logs/{eid}") if eid else {}
            details.append({"log": lg, "detail": d})
        out["scenarios"].append(clean({"scenario": s, "blueprint": full, "logs": details}))
os.makedirs("make-audit", exist_ok=True)
json.dump(out, open("make-audit/latest.json", "w"), indent=1, default=str)
print("scenarios:", len(out["scenarios"]), "teams error:" , teams.get("_error"))
