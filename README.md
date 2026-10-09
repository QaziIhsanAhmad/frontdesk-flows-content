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

## Stories and Highlights (9 Oct 2026)

- Starter Stories published on 9 Oct, about 11:52–11:56 PKT, to both IG and FB: Demos (st-demos-spam), Bookings (st-bookings-midnight), Reminders (st-reminders-6pm), Free Sample (st-free-sample).
- Instagram Highlights created in Business Suite (Content → Stories → Instagram highlights): Demos, Bookings, Reminders, Free Sample.
- Preview Stories (`rec/story.py` "preview" kind, files `sp-<reel>.mp4`) are scheduled to IG + FB at 20:30 PKT, 30 minutes after each Reel:

| Date | Preview of |
|---|---|
| Sat 10 Oct | c16-respond-first |
| Sun 11 Oct | c15-ai-outage |
| Mon 12 Oct | c08-no-show |
| Tue 13 Oct | c12-webhook |
| Wed 14 Oct | c09-reviews |
| Thu 15 Oct | c14-only-your-info |
| Fri 16 Oct | c01-after-hours |
| Sat 17 Oct | c02-urgent |
| Sun 18 Oct | c07-reminders |

Note: the Story composer only finishes "Processing media" while the Business Suite tab is visible on screen.

## Highlight covers (9 Oct 2026)

Covers are branded title-card Stories (`studio/batch-b/hl.html`), posted to Instagram only and added as the first frame of each Highlight. Business Suite only lets a cover be picked from a Story inside the Highlight. The Highlights are Demos (cyan play icon), Bookings (green calendar), Reminders (amber bell) and Free Sample (violet gift).

## Batch B, part 1 (made 9 Oct 2026)

| Reel | Demo | Simulated parts (labelled) |
|---|---|---|
| c20-redact | Code node strips DOB, NHS no., postcode, phone and email before the AI step | AI answer |
| c23-whatsapp | WhatsApp Cloud API style message in, AI reply out in the same chat | AI answer, WhatsApp API sandbox |
| c19-csv-crm | Each enquiry appended as a row to leads.csv (no Sheet or CRM) | AI answer |
| c22-review-approve | AI drafts a review reply, the owner approves by email, and a Wait node resumes | review trigger, AI draft, Google post |

The workflow builders and reel scripts are in `studio/batch-b/`. Run `python3 studio/batch-b/build_<name>.py` to regenerate a workflow JSON from `studio/clinic-enquiry-ai-triage.json`.

The importable versions were hardened after the recordings were made, following the code review on PR #3:
- **Redaction:** wider rules (written dates such as "14 March 1986", landlines and spaced mobile numbers, +44 numbers).
- **CSV log:** the path is a Settings value (default `/home/node/.n8n-files/leads.csv`, n8n's file folder in Docker). The header is written when the file is first created, and cells are quoted and protected against spreadsheet formulas.
- **WhatsApp:** a "Not Spam?" check runs before sending.
- **Review approval:** the email links to an n8n form, so the workflow only resumes when the owner presses Submit; link scanners can't trigger it. An empty or failed AI draft emails the owner instead of asking for approval.
