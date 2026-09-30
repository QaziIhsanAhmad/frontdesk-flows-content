# FrontDesk Flows – Instagram content

Automatic Reel publishing for [@frontdeskflows](https://www.instagram.com/frontdeskflows/).

- `videos/` – rendered Reels (1080x1920, captions + voiceover)
- `queue.json` – what posts when (Mon/Wed/Fri/Sun 15:00 UTC = 20:00 PKT) and its status
- `scripts/post_next.py` – posts the next due Reel via the official Instagram Graph API
- `.github/workflows/post-reel.yml` – runs daily; publishes only when an item is due

Setup: add the repository secret `IG_ACCESS_TOKEN` (long-lived token from the Meta app, Instagram API with Instagram login).
Test without posting: Actions → Post next Reel → Run workflow → dry_run = 1.
Tokens last ~60 days: generate a new one and replace the secret before it expires.
