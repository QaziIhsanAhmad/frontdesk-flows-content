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
elif act[0] == "conns":
    c = call("/connections?teamId=3012165")
    out["connections"] = [{k: x.get(k) for k in ("id","name","accountName","accountLabel","scoped","scopes","expire","editable","metadata")} for x in c.get("connections", [])]
elif act[0] == "rpc":
    # rpc:<app>:<version>:<rpcName>:<connId>  -> option list (e.g. facebook-pages Pages)
    out["result"] = call(f"/rpcs/{act[1]}/{act[2]}/{act[3]}?teamId=3012165", "POST", {"data": {"__IMTCONN__": int(act[4])}})
elif act[0] == "fbreel":
    # fbreel:<scenarioId>:<connId>  -> add/refresh Facebook Page Reel step after the IG step (same RSS item, so no duplicates)
    sid, conn = act[1], int(act[2])
    out["pages_rpc"] = call(f"/rpcs/facebook-pages/6/Pages?teamId=3012165", "POST", {"data": {"__IMTCONN__": conn}})
    bp = call(f"/scenarios/{sid}/blueprint")["response"]["blueprint"]
    bp["flow"] = [m for m in bp["flow"] if m["module"] != "facebook-pages:uploadAReel"]
    bp["flow"].append({"id": 4, "module": "facebook-pages:uploadAReel", "version": 6,
        "parameters": {"__IMTCONN__": conn},
        "mapper": {"page_id": "1354185007779555", "uploadMethod": "url", "url": "{{1.url}}",
                   "description": "{{replace(replace(1.description; \"see the link in bio, or DM me FLOW\"; \"message this Page with the word FLOW\"); \"link in bio\"; \"message this Page\")}}"},
        "metadata": {"designer": {"x": 600, "y": 0}},
        "onerror": [{"id": 5, "module": "builtin:Resume", "version": 1, "mapper": {}, "metadata": {"designer": {"x": 600, "y": 300}}}]})
    out["patch"] = call(f"/scenarios/{sid}", "PATCH", {"blueprint": json.dumps(bp)})
elif act[0] == "insights_setup":
    # insights_setup:<igConnId>  -> data store + weekly scenario that stores per-post Instagram insights
    conn = int(act[1])
    ds = None
    for d in call("/data-stores?teamId=3012165").get("dataStores", []):
        if d.get("name") == "FDF insights": ds = d
    if not ds:
        st = call("/data-structures", "POST", {"name": "FDF insight row", "teamId": 3012165, "strict": False, "spec": [
            {"name": "post", "type": "text"}, {"name": "permalink", "type": "text"}, {"name": "ts", "type": "text"},
            {"name": "caption", "type": "text"}, {"name": "metric", "type": "text"}, {"name": "value", "type": "number"},
            {"name": "likes", "type": "number"}, {"name": "comments", "type": "number"}, {"name": "pulled", "type": "text"}]})
        out["structure"] = st
        sid_ = (st.get("dataStructure") or {}).get("id")
        ds = call("/data-stores", "POST", {"name": "FDF insights", "teamId": 3012165, "datastructureId": sid_, "maxSizeMB": 1}).get("dataStore")
    out["datastore"] = ds
    bp = {"name": "FDF weekly insights", "flow": [
        {"id": 1, "module": "instagram-business:GetUserMedia", "version": 1, "parameters": {"__IMTCONN__": conn},
         "mapper": {"accountId": "17841416945478586", "limit": 40}, "metadata": {"designer": {"x": 0, "y": 0}}},
        {"id": 2, "module": "instagram-business:GetMediaInsights", "version": 1, "parameters": {"__IMTCONN__": conn},
         "mapper": {"accountId": "17841416945478586", "id": "{{1.id}}", "metrics": ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions"]},
         "metadata": {"designer": {"x": 300, "y": 0}},
         "onerror": [{"id": 4, "module": "builtin:Ignore", "version": 1, "mapper": {}, "metadata": {"designer": {"x": 300, "y": 300}}}]},
        {"id": 3, "module": "datastore:AddRecord", "version": 1, "parameters": {"datastore": ds["id"]},
         "mapper": {"key": "{{1.id}}_{{2.name}}", "overwrite": True, "data": {"post": "{{1.id}}", "permalink": "{{1.permalink}}", "ts": "{{1.timestamp}}",
                    "caption": "{{substring(1.caption; 0; 80)}}", "metric": "{{2.name}}", "value": "{{first(map(2.values; \"value\"))}}",
                    "likes": "{{1.like_count}}", "comments": "{{1.comments_count}}", "pulled": "{{now}}"}},
         "metadata": {"designer": {"x": 600, "y": 0}}}],
        "metadata": {"version": 1, "scenario": {"roundtrips": 1, "maxErrors": 3, "autoCommit": True, "sequential": False, "confidential": False, "dataloss": False, "dlq": False}}}
    existing = [s for s in call("/scenarios?teamId=3012165").get("scenarios", []) if s.get("name") == "FDF weekly insights"]
    if existing:
        out["insights_scenario"] = call(f"/scenarios/{existing[0]['id']}", "PATCH", {"blueprint": json.dumps(bp)})
    else:
        out["insights_scenario"] = call("/scenarios", "POST", {"teamId": 3012165, "blueprint": json.dumps(bp),
            "scheduling": json.dumps({"type": "weekly", "days": [1], "time": "06:00"})})
elif act[0] == "insights_pull":
    # insights_pull[:<scenarioId to run first>] -> insights/latest.json (no secrets)
    if len(act) > 1 and act[1]:
        out["run"] = call(f"/scenarios/{act[1]}/run", "POST", {"responsive": True})
    ds = [d for d in call("/data-stores?teamId=3012165").get("dataStores", []) if d.get("name") == "FDF insights"]
    rows = []
    if ds:
        pg = 0
        while True:
            r = call(f"/data-stores/{ds[0]['id']}/data?pg%5Blimit%5D=100&pg%5Boffset%5D={pg}")
            recs = r.get("records", [])
            rows += [x.get("data", {}) for x in recs]
            if len(recs) < 100: break
            pg += 100
    posts = {}
    for x in rows:
        p = posts.setdefault(x.get("post"), {"permalink": x.get("permalink"), "ts": x.get("ts"), "caption": x.get("caption"), "likes": x.get("likes"), "comments": x.get("comments")})
        p[x.get("metric")] = x.get("value")
    os.makedirs("insights", exist_ok=True)
    json.dump({"pulled": dt.datetime.utcnow().isoformat() + "Z", "posts": sorted(posts.values(), key=lambda p: p.get("ts") or "", reverse=True)},
              open("insights/latest.json", "w"), indent=1)
    out["insights_rows"] = len(rows)
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
