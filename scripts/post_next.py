#!/usr/bin/env python3
"""Publish the next due Reel from queue.json to Instagram via the official Graph API.

Env:
  IG_ACCESS_TOKEN   long-lived token (Instagram API with Instagram Login, or a Page token for Facebook Login)
  IG_GRAPH_HOST     default https://graph.instagram.com  (use https://graph.facebook.com for Facebook Login)
  IG_API_VERSION    default v23.0
  IG_USER_ID        optional; looked up from /me when missing
  MEDIA_BASE_URL    public base URL for videos, e.g. https://cdn.jsdelivr.net/gh/<owner>/<repo>@main/videos
  DRY_RUN=1         print what would happen, publish nothing
Posts at most one item per run: the earliest item whose publish_after <= now and status == "queued".
"""
import json, os, sys, time, datetime as dt, urllib.parse, urllib.request

HOST = os.environ.get("IG_GRAPH_HOST", "https://graph.instagram.com").rstrip("/")
VER = os.environ.get("IG_API_VERSION", "v23.0")
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
BASES = [b.strip().rstrip("/") for b in os.environ.get("MEDIA_BASE_URL", "").split(",") if b.strip()]
DRY = os.environ.get("DRY_RUN") == "1"
QUEUE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "queue.json")


def api(method, path, params=None):
    params = dict(params or {}); params["access_token"] = TOKEN
    url = f"{HOST}/{VER}/{path.lstrip('/')}"
    data = None
    if method == "GET":
        url += "?" + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf8", "replace")
        raise SystemExit(f"Graph API {method} {path} failed: HTTP {e.code} {body[:500]}")


def main():
    q = json.load(open(QUEUE))
    now = dt.datetime.now(dt.timezone.utc)
    due = [i for i in q["items"] if i["status"] == "queued" and dt.datetime.fromisoformat(i["publish_after"]) <= now]
    if not due:
        print("Nothing due."); return
    item = sorted(due, key=lambda i: i["publish_after"])[0]
    print(f"Posting {item['id']}")
    if DRY:
        for b in BASES: print("  would try", f"{b}/{item['file']}")
        print("DRY RUN caption:\n" + item["caption"][:300]); return
    if not TOKEN:
        raise SystemExit("IG_ACCESS_TOKEN secret is missing.")
    uid = os.environ.get("IG_USER_ID") or api("GET", "me", {"fields": "user_id,id,username"}).get("user_id") or api("GET", "me", {"fields": "id"})["id"]
    cid, last = None, None
    for b in BASES:
        video_url = f"{b}/{item['file']}"
        print("trying", video_url)
        c = api("POST", f"{uid}/media", {"media_type": "REELS", "video_url": video_url, "caption": item["caption"], "share_to_feed": "true"})
        for attempt in range(40):  # up to ~10 minutes
            s = api("GET", c["id"], {"fields": "status_code,status"})
            code = s.get("status_code"); print("container status:", code)
            if code in ("FINISHED", "ERROR", "EXPIRED"): break
            time.sleep(15)
        if code == "FINISHED":
            cid = c["id"]; break
        last = s
    if not cid:
        item["status"] = "error"; item["error"] = str(last)[:300]
        json.dump(q, open(QUEUE, "w"), indent=1, ensure_ascii=False)
        raise SystemExit(f"Instagram could not process the video: {last}")
    p = api("POST", f"{uid}/media_publish", {"creation_id": cid})
    item.update(status="posted", media_id=p.get("id"), posted_at=now.isoformat())
    json.dump(q, open(QUEUE, "w"), indent=1, ensure_ascii=False)
    print("Published media", p.get("id"))


def run():
    """Run main(); record the outcome in queue.json "health" so failures are visible without Actions logs."""
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    try:
        main()
    except SystemExit as e:
        if e.code in (None, 0):
            raise
        msg = str(e.code)[:400]
        q = json.load(open(QUEUE))
        q["health"] = {"ok": False, "error": msg, "at": now}
        due = [i for i in q["items"] if i["status"] == "queued" and dt.datetime.fromisoformat(i["publish_after"]) <= dt.datetime.now(dt.timezone.utc)]
        if due:
            it = sorted(due, key=lambda i: i["publish_after"])[0]
            it["attempts"] = it.get("attempts", 0) + 1
            it["last_error"] = msg
        json.dump(q, open(QUEUE, "w"), indent=1, ensure_ascii=False)
        print("FAILED:", msg)
        raise
    q = json.load(open(QUEUE))
    q["health"] = {"ok": True, "error": "", "at": now}
    json.dump(q, open(QUEUE, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    run()
