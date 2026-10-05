# FrontDesk Flows – Instagram content

Automatic Reel publishing for [@frontdeskflows](https://www.instagram.com/frontdeskflows/).

- `videos/` – rendered Reels (1080x1920, captions + voiceover)
- `queue.json` – what posts when (Mon/Wed/Fri/Sun 15:00 UTC = 20:00 PKT) and its status
- `scripts/post_next.py` – posts the next due Reel via the official Instagram Graph API
- `.github/workflows/post-reel.yml` – runs daily; publishes only when an item is due

Setup: add the repository secret `IG_ACCESS_TOKEN` (long-lived token from the Meta app, Instagram API with Instagram login).
Test without posting: Actions → Post next Reel → Run workflow → dry_run = 1.
Token renewal is automatic: every 7 days the poster refreshes the token (Instagram tokens last 60 days) and keeps the refreshed one only as AES-256 ciphertext in `.token/ig_token.enc`, keyed from the `IG_ACCESS_TOKEN` secret (useless without it). Non-secret status (expiry date, refresh errors, warnings) is written to `queue.json` → `token`. A new secret only has to be pasted if the token is revoked or unused for 60 days.
