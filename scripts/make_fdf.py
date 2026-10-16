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
elif act[0] == "yt_conns":
    c = call("/connections?teamId=3012165")
    out["connections"] = [{k: x.get(k) for k in ("id","name","accountName","accountLabel","scopes","expire","metadata")} for x in c.get("connections", []) if x.get("accountName") in ("youtube", "google")]
elif act[0] in ("yt_setup", "yt_run", "yt_status", "ig_export", "fb_export", "yt_seed"):
    # yt_setup:<ytConnId>:backfill[:<shortcode,shortcode,...>]  -> on-demand run that uploads only the listed Reels (curated meta)
    # yt_setup:<ytConnId>:live                                  -> every 6 h: new Instagram Reels after now -> YouTube Shorts
    # yt_run  -> run the scenario now and wait; yt_status -> write youtube/uploads.json from the data store
    import time
    def yt_store():
        for d in call("/data-stores?teamId=3012165").get("dataStores", []):
            if d.get("name") == "FDF YouTube uploads": return d
        st = call("/data-structures", "POST", {"name": "FDF YouTube upload", "teamId": 3012165, "strict": False, "spec": [
            {"name": "yt_id", "type": "text"}, {"name": "title", "type": "text"}, {"name": "ig_permalink", "type": "text"},
            {"name": "ig_timestamp", "type": "text"}, {"name": "source", "type": "text"}, {"name": "uploaded", "type": "text"},
            {"name": "media_url", "type": "text"}, {"name": "caption", "type": "text"}]})
        out["structure"] = st
        return call("/data-stores", "POST", {"name": "FDF YouTube uploads", "teamId": 3012165,
                    "datastructureId": (st.get("dataStructure") or {}).get("id"), "maxSizeMB": 1}).get("dataStore")
    def yt_scenario():
        return ([s for s in call("/scenarios?teamId=3012165").get("scenarios", []) if s.get("name") == "FDF Instagram to YouTube Shorts"] or [None])[0]
    if act[0] == "yt_setup":
        conn, mode = int(act[1]), act[2]
        ds = yt_store(); out["datastore"] = ds
        IGC, IGA = 11476468, "17841416945478586"
        M = "get(1.data; 2.shortcode)"
        if mode == "backfill":
            allow = act[3] if len(act) > 3 else ""
            gate = [[{"a": "{{2.media_product_type}}", "o": "text:equal", "b": "REELS"},
                     {"a": "{{split(\"" + allow + "\"; \",\")}}", "o": "array:contain", "b": "{{2.shortcode}}"}]]
            limit, sched = 25, {"type": "on-demand"}
        else:
            since = dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            gate = [[{"a": "{{2.media_product_type}}", "o": "text:equal", "b": "REELS"},
                     {"a": "{{2.timestamp}}", "o": "date:greater", "b": since}]]
            pending = act[3] if len(act) > 3 else ""
            if pending:  # older Reels still to upload (e.g. held back by YouTube's daily limit); retried every run until stored
                gate.append([{"a": "{{2.media_product_type}}", "o": "text:equal", "b": "REELS"},
                             {"a": "{{split(\"" + pending + "\"; \",\")}}", "o": "array:contain", "b": "{{2.shortcode}}"}])
            limit, sched = 10, {"type": "indefinitely", "interval": 21600}
            out["since"] = since
        footer = ("\n\nFree clinic workflow: send the word FLOW in a DM on Instagram → https://www.instagram.com/frontdeskflows/"
                  "\n\n—\nFrontDesk Flows: ready-to-import n8n automations for clinics (AI replies, reminders, review requests). "
                  "For clinics, agencies and freelancers.\nInstagram: https://www.instagram.com/frontdeskflows/\n\n#Shorts #n8n #automation")
        cap = "replace(replace(replace(2.caption; \"see the link in bio, or DM me FLOW\"; \"send the word FLOW in a DM on Instagram\"); \"DM me FLOW\"; \"send the word FLOW in a DM on Instagram\"); \"/[<>]/g\"; emptystring)"
        default_tags = ["n8n", "n8n tutorial", "automation", "AI automation", "no code", "clinic automation", "clinic marketing", "workflow automation", "FrontDesk Flows", "shorts"]
        def upload(mid, src_mod, rec_id, source):
            return [
                {"id": mid, "module": "youtube:uploadVideo", "version": 4, "parameters": {"__IMTCONN__": conn},
                 "mapper": {"title": "{{12.title}}", "description": "{{12.description}}", "tags": "{{12.tags}}",
                            "fileName": "{{2.shortcode}}.mp4", "data": "{{" + str(src_mod) + ".data}}", "categoryId": "28",
                            "privacyStatus": "public", "selfDeclaredMadeForKids": False, "containsSyntheticMedia": False,
                            "license": "youtube", "embeddable": True},
                 "metadata": {"designer": {"x": 1500, "y": 0}},
                 "onerror": [{"id": mid + 50, "module": "builtin:Ignore", "version": 1, "mapper": {}, "metadata": {"designer": {"x": 1500, "y": 300}}}]},
                {"id": rec_id, "module": "datastore:AddRecord", "version": 1, "parameters": {"datastore": ds["id"]},
                 "mapper": {"key": "{{2.shortcode}}", "overwrite": True, "data": {"yt_id": "{{" + str(mid) + ".id}}", "title": "{{12.title}}",
                            "ig_permalink": "{{2.permalink}}", "ig_timestamp": "{{2.timestamp}}", "source": source, "uploaded": "{{now}}"}},
                 "metadata": {"designer": {"x": 1800, "y": 0}}}]
        bp = {"name": "FDF Instagram to YouTube Shorts", "flow": [
            {"id": 1, "module": "http:MakeRequest", "version": 4, "parameters": {"authenticationType": "noAuth"},
             "mapper": {"url": "https://cdn.jsdelivr.net/gh/QaziIhsanAhmad/frontdesk-flows-content@main/youtube/meta.json", "method": "get", "parseResponse": True},
             "metadata": {"designer": {"x": 0, "y": 0}}},
            {"id": 2, "module": "instagram-business:GetUserMedia", "version": 1, "parameters": {"__IMTCONN__": IGC},
             "mapper": {"accountId": IGA, "limit": limit}, "metadata": {"designer": {"x": 300, "y": 0}}},
            {"id": 3, "module": "datastore:ExistRecord", "version": 1, "parameters": {"datastore": ds["id"]},
             "mapper": {"key": "{{2.shortcode}}"}, "filter": {"name": "New Reel", "conditions": gate},
             "metadata": {"designer": {"x": 600, "y": 0}}},
            {"id": 4, "module": "util:SetVariables", "version": 1, "parameters": {},
             "mapper": {"scope": "roundtrip", "variables": [
                 {"name": "auto_title", "value": "{{substring(replace(first(split(2.caption; newline)); \"/[<>]/g\"; emptystring); 0; 88)}} #Shorts"},
                 {"name": "auto_description", "value": "{{" + cap + "}}" + footer}]},
             "filter": {"name": "Not uploaded yet", "conditions": [[{"a": "{{3.exist}}", "o": "boolean:equal", "b": "false"}]]},
             "metadata": {"designer": {"x": 900, "y": 0}}},
            {"id": 12, "module": "util:SetVariables", "version": 1, "parameters": {},
             "mapper": {"scope": "roundtrip", "variables": [
                 {"name": "title", "value": "{{ifempty(get(" + M + "; \"title\"); 4.auto_title)}}"},
                 {"name": "description", "value": "{{ifempty(get(" + M + "; \"description\"); 4.auto_description)}}"},
                 {"name": "tags", "value": "{{ifempty(get(" + M + "; \"tags\"); split(\"" + ",".join(default_tags) + "\"; \",\"))}}"},
                 {"name": "source_url", "value": "{{get(" + M + "; \"source_url\")}}"}]},
             "metadata": {"designer": {"x": 1050, "y": 0}}},
            {"id": 5, "module": "builtin:BasicRouter", "version": 1, "mapper": None, "metadata": {"designer": {"x": 1200, "y": 0}}, "routes": [
                {"flow": [{"id": 6, "module": "http:DownloadFile", "version": 4, "parameters": {"authenticationType": "noAuth"},
                           "mapper": {"url": "{{12.source_url}}"},
                           "filter": {"name": "Original file in repo", "conditions": [[{"a": "{{12.source_url}}", "o": "exist"}]]},
                           "metadata": {"designer": {"x": 1200, "y": -200}}}] + upload(7, 6, 8, "repo original")},
                {"flow": [{"id": 9, "module": "instagram-business:DownloadMedia", "version": 1, "parameters": {"__IMTCONN__": IGC},
                           "mapper": {"id": "{{2.id}}"},
                           "filter": {"name": "Instagram copy", "conditions": [[{"a": "{{12.source_url}}", "o": "notexist"}]]},
                           "metadata": {"designer": {"x": 1200, "y": 200}}}] + upload(10, 9, 11, "instagram")}]}],
            "metadata": {"version": 1, "scenario": {"roundtrips": 1, "maxErrors": 3, "autoCommit": True, "autoCommitTriggerLast": True,
                                                    "sequential": True, "confidential": False, "dataloss": False, "dlq": False}}}
        ex = yt_scenario()
        if ex:
            out["scenario"] = call(f"/scenarios/{ex['id']}", "PATCH", {"blueprint": json.dumps(bp), "scheduling": json.dumps(sched)})
            sid = ex["id"]
        else:
            out["scenario"] = call("/scenarios?confirmed=true", "POST", {"teamId": 3012165, "blueprint": json.dumps(bp), "scheduling": json.dumps(sched)})
            sid = (out["scenario"].get("scenario") or {}).get("id")
        out["start"] = call(f"/scenarios/{sid}/start", "POST", {}) if sid else "no scenario id"
    if act[0] == "ig_export":
        # ig_export:<shortcode,shortcode,...> -> download Instagram's copy of those Reels into videos/ig/ (no YouTube involved)
        want = set(act[1].split(",")) if len(act) > 1 and act[1] else set()
        ds = yt_store(); out["datastore"] = ds
        bp = {"name": "FDF IG reel export", "flow": [
            {"id": 1, "module": "instagram-business:GetUserMedia", "version": 1, "parameters": {"__IMTCONN__": 11476468},
             "mapper": {"accountId": "17841416945478586", "limit": 25}, "metadata": {"designer": {"x": 0, "y": 0}}},
            {"id": 2, "module": "datastore:AddRecord", "version": 1, "parameters": {"datastore": ds["id"]},
             "filter": {"name": "Reels", "conditions": [[{"a": "{{1.media_product_type}}", "o": "text:equal", "b": "REELS"}]]},
             "mapper": {"key": "media_{{1.shortcode}}", "overwrite": True, "data": {"media_url": "{{1.media_url}}", "caption": "{{1.caption}}",
                        "ig_permalink": "{{1.permalink}}", "ig_timestamp": "{{1.timestamp}}"}},
             "metadata": {"designer": {"x": 300, "y": 0}}}],
            "metadata": {"version": 1, "scenario": {"roundtrips": 1, "maxErrors": 3, "autoCommit": True, "sequential": False, "confidential": False, "dataloss": False, "dlq": False}}}
        ex = ([s for s in call("/scenarios?teamId=3012165").get("scenarios", []) if s.get("name") == "FDF IG reel export"] or [None])[0]
        if ex:
            call(f"/scenarios/{ex['id']}", "PATCH", {"blueprint": json.dumps(bp)}); sid = ex["id"]
        else:
            r = call("/scenarios?confirmed=true", "POST", {"teamId": 3012165, "blueprint": json.dumps(bp), "scheduling": json.dumps({"type": "on-demand"})})
            out["export_create"] = r; sid = (r.get("scenario") or {}).get("id")
        out["export_start"] = call(f"/scenarios/{sid}/start", "POST", {})
        out["export_run"] = call(f"/scenarios/{sid}/run", "POST", {"responsive": True})
        out["export_stop"] = call(f"/scenarios/{sid}/stop", "POST", {})
        recs = call(f"/data-stores/{ds['id']}/data?pg%5Blimit%5D=100").get("records", [])
        os.makedirs("videos/ig", exist_ok=True)
        got = []
        for r in recs:
            k, d = r.get("key", ""), r.get("data", {})
            if not k.startswith("media_"): continue
            sc = k[6:]
            if want and sc not in want: continue
            try:
                blob = urllib.request.urlopen(urllib.request.Request(d["media_url"], headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read()
                open(f"videos/ig/{sc}.mp4", "wb").write(blob); got.append([sc, len(blob), d.get("ig_timestamp")])
            except Exception as e:
                got.append([sc, "error " + str(e)[:120]])
        out["export_files"] = got
    if act[0] == "fb_export":
        # fb_export:<YYYY-MM-DD>:<YYYY-MM-DD> -> download the Facebook Page copies (often higher resolution) of Reels created in that range into videos/fb/
        lo, hi = act[1], act[2]
        ds = yt_store()
        bp = {"name": "FDF FB reel export", "flow": [
            {"id": 1, "module": "facebook-pages:ListVideos", "version": 6, "parameters": {"__IMTCONN__": 11476526},
             "mapper": {"page_id": "1354185007779555", "type": "uploaded", "limit": 40}, "metadata": {"designer": {"x": 0, "y": 0}}},
            {"id": 2, "module": "datastore:AddRecord", "version": 1, "parameters": {"datastore": ds["id"]},
             "mapper": {"key": "fb_{{1.id}}", "overwrite": True, "data": {"media_url": "{{1.source}}", "caption": "{{substring(1.description; 0; 120)}}",
                        "ig_permalink": "{{1.permalink_url}}", "ig_timestamp": "{{1.created_time}}"}},
             "metadata": {"designer": {"x": 300, "y": 0}}}],
            "metadata": {"version": 1, "scenario": {"roundtrips": 1, "maxErrors": 3, "autoCommit": True, "sequential": False, "confidential": False, "dataloss": False, "dlq": False}}}
        ex = ([s for s in call("/scenarios?teamId=3012165").get("scenarios", []) if s.get("name") in ("FDF IG reel export", "FDF FB reel export")] or [None])[0]
        if ex:
            out["patch"] = call(f"/scenarios/{ex['id']}", "PATCH", {"blueprint": json.dumps(bp), "name": "FDF FB reel export"}); sid = ex["id"]
        else:
            r = call("/scenarios?confirmed=true", "POST", {"teamId": 3012165, "blueprint": json.dumps(bp), "scheduling": json.dumps({"type": "on-demand"})})
            sid = (r.get("scenario") or {}).get("id")
        out["export_start"] = call(f"/scenarios/{sid}/start", "POST", {})
        out["export_run"] = call(f"/scenarios/{sid}/run", "POST", {"responsive": True})
        out["export_stop"] = call(f"/scenarios/{sid}/stop", "POST", {})
        recs = call(f"/data-stores/{ds['id']}/data?pg%5Blimit%5D=100").get("records", [])
        os.makedirs("videos/fb", exist_ok=True)
        got = []
        for r in recs:
            k, d = r.get("key", ""), r.get("data", {})
            ts = (d.get("ig_timestamp") or "")[:10]
            if not k.startswith("fb_") or not (lo <= ts <= hi) or not d.get("media_url"): continue
            try:
                blob = urllib.request.urlopen(urllib.request.Request(d["media_url"], headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read()
                fn = f"videos/fb/{d.get('ig_timestamp','')[:16].replace(':','')}_{k[3:]}.mp4"
                open(fn, "wb").write(blob); got.append([fn, len(blob), d.get("caption", "")[:50]])
            except Exception as e:
                got.append([k, "error " + str(e)[:120]])
        out["export_files"] = got
    if act[0] == "yt_seed":
        # record Reels already uploaded by hand (youtube/uploads.json) so the scenario never uploads them again
        ds = yt_store(); seeded = []
        for r in json.load(open("youtube/uploads.json")):
            res = call(f"/data-stores/{ds['id']}/data", "POST", {"key": r["shortcode"], "overwrite": True, "data": {
                "yt_id": r["yt_id"], "title": r["title"], "ig_permalink": r["ig_permalink"], "source": r.get("source", ""), "uploaded": r.get("uploaded", "")}})
            seeded.append([r["shortcode"], "ok" if "_error" not in res else res])
        out["seeded"] = seeded
    if act[0] == "yt_run":
        sc = yt_scenario()
        out["run"] = call(f"/scenarios/{sc['id']}/run", "POST", {"responsive": True})
        eid = (out["run"] or {}).get("executionId")
        for _ in range(40):
            st = call(f"/scenarios/{sc['id']}/executions/{eid}") if eid else {}
            out["execution"] = st
            if st.get("status") not in ("RUNNING", None) or not eid: break
            time.sleep(15)
    ds = [d for d in call("/data-stores?teamId=3012165").get("dataStores", []) if d.get("name") == "FDF YouTube uploads"]
    if ds and act[0] not in ("ig_export", "fb_export"):
        recs = [r for r in call(f"/data-stores/{ds[0]['id']}/data?pg%5Blimit%5D=100").get("records", []) if not r.get("key", "").startswith(("media_", "fb_"))]
        os.makedirs("youtube", exist_ok=True)
        json.dump(sorted([dict(r.get("data", {}), shortcode=r.get("key")) for r in recs], key=lambda r: r.get("ig_timestamp") or ""),
                  open("youtube/store.json", "w"), indent=1, ensure_ascii=False)
        out["uploads"] = len(recs)
elif act[0] == "yt_credreq":
    # creates a Make credential request; its public link lets the owner authorise YouTube without a Make login
    conn = {"type": "youtube", "nameOverride": "FrontDesk Flows YouTube",
            "scope": ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube"],
            "description": "Sign in with the Google account that owns the FrontDesk Flows channel."}
    base = {"teamId": 3012165, "name": "FrontDesk Flows YouTube", "description": "Authorise the FrontDesk Flows YouTube channel so new Instagram Reels are uploaded as Shorts."}
    tries = [("/credential-requests/requests", dict(base, provider={"connections": [conn]})),
             ("/credential-requests/requests", dict(base, connections=[conn])),
             ("/credential-requests/requests", dict(base, provider={"type": "credentials", "connections": [conn]})),
             ("/credential-requests/requests/create-by-credentials", dict(base, connections=[conn]))]
    for path, body in tries:
        r = call(path, "POST", body)
        out.setdefault("credreq", []).append({"path": path, "keys": list(body), "result": r})
        if "_error" not in r: break
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
