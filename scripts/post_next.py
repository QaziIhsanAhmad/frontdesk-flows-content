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
import json, os, sys, time, hashlib, subprocess, datetime as dt, urllib.parse, urllib.request

HOST = os.environ.get("IG_GRAPH_HOST", "https://graph.instagram.com").rstrip("/")
VER = os.environ.get("IG_API_VERSION", "v23.0")
TOKEN = os.environ.get("IG_ACCESS_TOKEN", "")
BASES = [b.strip().rstrip("/") for b in os.environ.get("MEDIA_BASE_URL", "").split(",") if b.strip()]
DRY = os.environ.get("DRY_RUN") == "1"
QUEUE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "queue.json")
# Refreshed tokens are kept in the repo ONLY as AES-256 ciphertext. The key is derived from the
# IG_ACCESS_TOKEN secret, which never leaves GitHub secrets, so the public file is useless without it.
# When Qazi replaces the secret, the old file no longer decrypts and the new secret is used instead.
TOKEN_STORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".token", "ig_token.enc")
REFRESH_EVERY_DAYS = 7     # Instagram long-lived tokens last 60 days; refresh well before that
WARN_DAYS_LEFT = 10


def _key(secret):
    return hashlib.sha256(("frontdesk-ig-store:" + secret).encode()).hexdigest()


def load_stored_token(secret):
    if not secret or not os.path.exists(TOKEN_STORE):
        return None
    try:
        r = subprocess.run(["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-a", "-A",
                            "-pass", "env:IG_STORE_KEY", "-in", TOKEN_STORE],
                           capture_output=True, env={**os.environ, "IG_STORE_KEY": _key(secret)})
        if r.returncode != 0:
            return None
        return json.loads(r.stdout.decode("utf8"))
    except Exception:  # wrong key (secret was replaced) or damaged file: fall back to the secret
        return None


def save_stored_token(secret, data):
    os.makedirs(os.path.dirname(TOKEN_STORE), exist_ok=True)
    r = subprocess.run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", "200000", "-salt", "-a", "-A",
                        "-pass", "env:IG_STORE_KEY", "-out", TOKEN_STORE],
                       input=json.dumps(data), capture_output=True, text=True,
                       env={**os.environ, "IG_STORE_KEY": _key(secret)})
    if r.returncode != 0:
        raise RuntimeError("could not encrypt refreshed token: " + r.stderr[:200])


def choose_and_refresh_token(now):
    """Pick the freshest usable token and refresh it when due. Returns (token, info dict for health)."""
    secret = os.environ.get("IG_ACCESS_TOKEN", "")
    if not secret:
        return "", {}
    stored = load_stored_token(secret) or {}
    token = stored.get("token") or secret
    info = {"token_source": "refreshed" if stored.get("token") else "secret"}
    if stored.get("expires_at"):
        info["token_expires_at"] = stored["expires_at"]
    last = stored.get("refreshed_at")
    due = (not last) or (now - dt.datetime.fromisoformat(last)).days >= REFRESH_EVERY_DAYS
    if due and "graph.instagram.com" in HOST and not DRY:
        url = f"{HOST}/refresh_access_token?" + urllib.parse.urlencode({"grant_type": "ig_refresh_token", "access_token": token})
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                d = json.load(r)
            new, secs = d.get("access_token"), int(d.get("expires_in") or 0)
            if new:
                exp = (now + dt.timedelta(seconds=secs)).isoformat() if secs else None
                save_stored_token(secret, {"token": new, "refreshed_at": now.isoformat(), "expires_at": exp})
                token = new
                info.update(token_source="refreshed", token_expires_at=exp, token_refreshed_at=now.isoformat())
                print("Token refreshed; new expiry", exp)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf8", "replace")[:300]
            print("Token refresh failed (will still try to post):", e.code, body)
            info["token_refresh_error"] = f"HTTP {e.code} {body}"
        except Exception as e:  # network etc. - never block posting on a refresh problem
            print("Token refresh failed (will still try to post):", e)
            info["token_refresh_error"] = str(e)[:300]
    return token, info


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
        hint = ""
        if '"code":190' in body.replace(" ", ""):
            hint = " [token invalid or expired: replace the IG_ACCESS_TOKEN secret]"
        raise SystemExit(f"Graph API {method} {path} failed: HTTP {e.code} {body[:500]}{hint}")


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


MIN_GAP_HOURS = 12  # catch-up posts are spread out: never two Reels within 12 hours


def recently_posted(q, now):
    times = [dt.datetime.fromisoformat(i["posted_at"]) for i in q["items"] if i.get("status") == "posted" and i.get("posted_at")]
    return bool(times) and (now - max(times)).total_seconds() < MIN_GAP_HOURS * 3600


def set_health(q, ok, msg, now):
    """Only touch queue.json when health actually changes, so hourly runs don't create noise commits."""
    h = q.get("health") or {}
    if h.get("ok") == ok and h.get("error", "") == msg:
        return False
    q["health"] = {"ok": ok, "error": msg, "since": now.isoformat()}
    return True


def update_token_info(q, tinfo, now):
    """Keep non-secret token facts (expiry, refresh errors) in queue.json so the monitor can warn early."""
    if not tinfo:
        return False
    old = q.get("token") or {}
    new = {k: v for k, v in {**old, **tinfo}.items() if v is not None}
    if "token_refresh_error" not in tinfo:
        new.pop("token_refresh_error", None)
    exp = new.get("token_expires_at")
    if exp:
        days = (dt.datetime.fromisoformat(exp) - now).days
        new["warning"] = (f"Instagram token expires in {days} days and could not be refreshed automatically."
                          if days <= WARN_DAYS_LEFT else "")
    if new == old:
        return False
    q["token"] = new
    return True


def run():
    """Run main(); record the outcome in queue.json "health" so failures are visible without Actions logs."""
    global TOKEN
    now = dt.datetime.now(dt.timezone.utc)
    TOKEN, tinfo = choose_and_refresh_token(now)
    q = json.load(open(QUEUE))
    if update_token_info(q, tinfo, now):
        json.dump(q, open(QUEUE, "w"), indent=1, ensure_ascii=False)
    if recently_posted(q, now):
        print(f"A Reel was posted less than {MIN_GAP_HOURS}h ago; waiting."); return
    try:
        main()
    except SystemExit as e:
        if e.code in (None, 0):
            raise
        msg = str(e.code)[:400]
        q = json.load(open(QUEUE))
        changed = set_health(q, False, msg, now)
        config_problem = "secret is missing" in msg
        if not config_problem:  # count real attempts only, not hourly checks while the token is absent
            due = [i for i in q["items"] if i["status"] == "queued" and dt.datetime.fromisoformat(i["publish_after"]) <= now]
            if due:
                it = sorted(due, key=lambda i: i["publish_after"])[0]
                it["attempts"] = it.get("attempts", 0) + 1
                it["last_error"] = msg
                changed = True
        if changed:
            json.dump(q, open(QUEUE, "w"), indent=1, ensure_ascii=False)
        print("FAILED:", msg)
        if config_problem:
            return  # recorded in health; avoid an hourly failure e-mail until the secret is added
        raise
    q = json.load(open(QUEUE))
    if set_health(q, True, "", now):
        json.dump(q, open(QUEUE, "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    run()
