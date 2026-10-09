# FrontDesk Flows – Instagram content

Automatic Reel publishing for [@frontdeskflows](https://www.instagram.com/frontdeskflows/).

- `videos/` – rendered Reels (1080x1920, captions + voiceover)
- `queue.json` – what posts when (Mon/Wed/Fri/Sun 15:00 UTC = 20:00 PKT) and its status
- `scripts/post_next.py` – posts the next due Reel via the official Instagram Graph API
- `.github/workflows/post-reel.yml` – runs daily; publishes only when an item is due

Setup: add the repository secret `IG_ACCESS_TOKEN` (long-lived token from the Meta app, Instagram API with Instagram login).
Test without posting: Actions → Post next Reel → Run workflow → dry_run = 1.
Token renewal is automatic: every 7 days the poster refreshes the token (Instagram tokens last 60 days) and keeps the refreshed one only as AES-256 ciphertext in `.token/ig_token.enc`, keyed from the `IG_ACCESS_TOKEN` secret (useless without it). Non-secret status (expiry date, refresh errors, warnings) is written to `queue.json` → `token`. A new secret only has to be pasted if the token is revoked or unused for 60 days.

## Batch A (v3 Reels): scheduled in Meta Business Suite on 9 Oct 2026

Each Reel goes to the FrontDesk Flows Facebook Page and @frontdeskflows on Instagram at 20:00 Asia/Karachi (UTC+5). Captions were checked in the Scheduled list. Keep reels-feed.xml empty so the Make/RSS lane doesn't post duplicates.

| Date (PKT) | Reel |
|---|---|
| Fri 9 Oct | c13-honeypot |
| Sat 10 Oct | c16-respond-first |
| Sun 11 Oct | c15-ai-outage |
| Mon 12 Oct | c08-no-show |
| Tue 13 Oct | c12-webhook |
| Wed 14 Oct | c09-reviews |
| Thu 15 Oct | c14-only-your-info |
| Fri 16 Oct | c01-after-hours |
| Sat 17 Oct | c02-urgent |
| Sun 18 Oct | c07-reminders |

Notes:
- The Reel composer often drops a pasted caption. Fix it afterwards via Scheduled → ⋯ → Manage post → Edit Post (FB) or Edit Reel (IG).
- The Story composer stays on "Processing media" while the Chrome window is off-screen.
