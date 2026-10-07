"""Make.com lane for Reels (used while the IG_ACCESS_TOKEN secret is not set).

Each run moves at most one due "queued" item to status "feed" (max one per 20 hours)
and rewrites reels-feed.xml with every "feed" item. A Make.com scenario watches
the feed and publishes each new item as an Instagram Reel:
  Video URL = enclosure url, Caption = description.
post_next.py only posts "queued" items, so the two lanes never post the same Reel.
"""
import datetime as dt
import json
import os
from email.utils import format_datetime
from xml.sax.saxutils import escape

REPO = os.environ.get("GITHUB_REPOSITORY", "QaziIhsanAhmad/frontdesk-flows-content")
BASE = f"https://cdn.jsdelivr.net/gh/{REPO}@main/videos/"
MIN_GAP = dt.timedelta(hours=20)


def main():
    now = dt.datetime.now(dt.timezone.utc)
    with open("queue.json") as f:
        q = json.load(f)
    items = q["items"]
    fed = [dt.datetime.fromisoformat(i["fed_at"]) for i in items if i.get("fed_at")]
    if not fed or now - max(fed) >= MIN_GAP:
        due = sorted(
            (i for i in items if i["status"] == "queued" and dt.datetime.fromisoformat(i["publish_after"]) <= now),
            key=lambda i: i["publish_after"],
        )
        if due:
            due[0].update(status="feed", fed_at=now.isoformat(), media_url=BASE + due[0]["file"])
            print("added to feed:", due[0]["id"])
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<rss version="2.0"><channel>',
           "<title>FrontDesk Flows Reels</title>",
           "<link>https://www.instagram.com/frontdeskflows/</link>",
           "<description>Reels due for @frontdeskflows</description>"]
    for i in sorted((i for i in items if i["status"] == "feed"), key=lambda i: i["fed_at"]):
        url = i.get("media_url") or BASE + i["file"]
        when = format_datetime(dt.datetime.fromisoformat(i["fed_at"]))
        out += ["<item>", f"<title>{escape(i['id'])}</title>",
                f'<guid isPermaLink="false">{escape(i["id"])}</guid>',
                f"<link>{escape(url)}</link>", f"<pubDate>{when}</pubDate>",
                f"<description>{escape(i['caption'])}</description>",
                f'<enclosure url="{escape(url)}" type="video/mp4" length="0"/>', "</item>"]
    out.append("</channel></rss>")
    with open("reels-feed.xml", "w") as f:
        f.write("\n".join(out) + "\n")
    with open("queue.json", "w") as f:
        json.dump(q, f, indent=1, ensure_ascii=False)
        f.write("\n")


if __name__ == "__main__":
    main()
