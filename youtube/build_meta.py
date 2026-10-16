"""Builds youtube/meta.json: curated YouTube Shorts metadata for Instagram Reels, keyed by IG shortcode.
`source_url` = original render in this repo (used instead of Instagram's re-encoded copy when present)."""
import json
RAW = "https://raw.githubusercontent.com/QaziIhsanAhmad/frontdesk-flows-content/main/videos/"
CTA = "Free clinic workflow: send the word FLOW in a DM on Instagram → https://www.instagram.com/frontdeskflows/"
FOOT = ("\n\n—\nFrontDesk Flows: ready-to-import n8n automations for clinics (AI replies, reminders, review requests). "
        "For clinics, agencies and freelancers.\nInstagram: https://www.instagram.com/frontdeskflows/")
BASE_TAGS = ["n8n", "n8n tutorial", "automation", "AI automation", "no code", "clinic automation", "clinic marketing",
             "workflow automation", "FrontDesk Flows", "shorts"]
items = [
 ("Dd_6DZSkQk4", "reel-01-front-desk.mp4", "After-hours clinic enquiries answered in seconds with n8n #Shorts",
  ["after hours enquiries", "AI receptionist", "google sheets crm"],
  "Clinic enquiries sent at 11pm usually wait until morning. By then, the patient may have booked somewhere else.\n\nThis n8n workflow replies in seconds, using only the clinic's own details, logs every lead in Google Sheets and flags urgent ones for staff."),
 ("DePB39eiMxQ", "reel-02-urgent.mp4", "An AI front desk should never play doctor: urgent messages in n8n #Shorts",
  ["AI agents", "healthtech", "physiotherapy", "AI safety"],
  "An AI assistant should never play doctor.\n\nWhen a message sounds urgent, this workflow tells the person to contact emergency services and emails the front desk at the same moment, so a human calls back. Tested with real runs, not just a diagram."),
 ("DePB9ZUjZXR", "reel-03-spam-outage.mp4", "2 things AI chatbot tutorials skip: spam bots and AI outages #Shorts",
  ["AI chatbot", "spam protection", "honeypot", "error handling"],
  "Most AI chatbot tutorials skip these two:\n1. Spam: a hidden honeypot and link checks stop bots before they cost an AI call.\n2. Outages: if the AI provider is down, the patient still gets a polite reply."),
 ("DePGIXmAlAO", "reel-04-one-node.mp4", "Stop rebuilding n8n automations for every client: one Settings node #Shorts",
  ["freelancer", "agency automation", "reusable workflow"],
  "Stop rebuilding automations for every client.\n\nPut everything client-specific in one Settings node: business name, hours, services, booking link, staff email. Then a new clinic is: duplicate, edit one node, connect their accounts, test."),
 ("DePGPBnDWwD", "reel-05-almost-free.mp4", "The cheapest way to run an AI enquiry assistant with n8n #Shorts",
  ["self hosted", "open source", "Ollama", "Groq"],
  "The cheapest way to run an AI enquiry assistant:\n• n8n Community Edition (self-hosted)\n• Groq free tier or a local model via Ollama\n• the clinic's own mailbox (SMTP)\n• Google Sheets as the CRM\n\nJust be upfront about rate limits and hosting."),
 ("DePT276FAsQ", "reel-06-pack-coming.mp4", "6 n8n automations every clinic can use: the FrontDesk Flows pack #Shorts",
  ["clinic workflows", "appointment reminders", "review requests"],
  "The full FrontDesk Flows clinic pack:\n1. Enquiry triage with AI replies (+ WhatsApp version)\n2. Appointment reminders\n3. No-show follow-up\n4. Review requests\n5. FAQ assistant from clinic documents\n6. Weekly owner summary\n\nEach with a setup guide, test data and a video walkthrough."),
 ("DePT964lRho", "reel-07-reminders.mp4", "Appointment reminders: the easiest automation to sell to a clinic #Shorts",
  ["appointment reminders", "dental practice", "physiotherapy"],
  "Appointment reminders are the easiest automation to sell to a clinic.\n\nHourly check → 24-hour reminder → 2-hour nudge → reply to cancel frees the slot. Store 'reminder sent' in the booking row so nothing goes out twice."),
 ("DeRyHpZjbAz", None, "Stop form spam bots in n8n without a CAPTCHA (honeypot field) #Shorts",
  ["honeypot", "spam bots", "website form", "web development"],
  "This clinic's form just got hit by a spam bot. n8n caught it in one step.\n\nThe trick: a hidden 'website' field humans never see. Many bots fill every field, so the workflow marks it invalid and stops at 'Is Valid?' before any AI call or email. No CAPTCHA needed.\n\nReal n8n run on a demo clinic site. Nothing simulated in this one."),
 ("DeUW0shjQ1z", None, "Respond to Webhook first: no spinner while your AI thinks (n8n) #Shorts",
  ["respond to webhook", "webhook", "website form", "user experience"],
  "Don't make website visitors watch a spinner while your AI thinks.\n\nPut 'Respond to Webhook' straight after validation: the browser gets a thank-you in a fraction of a second, and the AI reply, email and logging carry on in the background. No double submissions.\n\nReal n8n run on a demo clinic site. The AI answer (with a 4.5s delay) and the Sheet row are simulated, and labelled."),
 ("DeW7oXpERrs", None, "What happens to your AI workflow when the AI provider goes down? #Shorts",
  ["error handling", "AI outage", "fallback", "try catch"],
  "What happens to your AI workflow when the AI provider goes down?\n\nThis one keeps going: the AI step continues on error, a Code node parses the answer inside try/catch, and if anything is off the patient gets a polite holding reply instead of silence.\n\nReal n8n run on a demo clinic site. The outage (503) is simulated and labelled; the fallback and email are real."),
 ("DeZgZETibyE", None, "Clinic no-shows: a kind rebook message, automated with n8n #Shorts",
  ["no show", "patient follow up", "physiotherapy", "booking"],
  "14:30. Daniel didn't show up. Reception taps 'No-show' and n8n does the rest:\n\n1. Checks it really is a no-show\n2. Sends a kind message with a rebook link (no guilt, no fees)\n3. Waits 3 days, then one gentle follow-up\n\nReal n8n run with a demo booking screen and a demo inbox."),
 ("DecFM5vDGUn", None, "Website form to n8n with one Webhook node (Test vs Production URL) #Shorts",
  ["webhook", "n8n webhook", "website form", "beginner"],
  "How a website form talks to n8n: one Webhook node. The browser POSTs the form as JSON and the workflow runs.\n\nMost common mistake: pasting the Test URL on the live site. Use the Production URL and activate the workflow.\n\nReal n8n run on a demo clinic site. The AI answer and Sheet row are simulated and labelled."),
 ("DeeqAcJDVKU", None, "Review gating isn't allowed: ask every patient for a review the same way #Shorts",
  ["google reviews", "review requests", "review gating", "reputation"],
  "Myth: only ask happy patients for reviews. Fact: that's review gating, and Google's review policy doesn't allow it.\n\nThis n8n workflow sends every patient the same thank-you after their visit, with the Google review link plus a separate private feedback link.\n\nReal n8n run with a demo booking screen and a demo inbox."),
 ("DehO47fjEm_", None, "Stop your AI assistant inventing prices: one prompt rule in n8n #Shorts",
  ["prompt engineering", "chatgpt", "AI hallucination", "AI receptionist"],
  "Quiz: would your AI assistant invent a price if a patient asked? Left alone, many will.\n\nThis n8n workflow sends the AI a BUSINESS INFO block plus one rule: use only those facts, never promise prices or availability that aren't listed, and hand off to a human when unsure.\n\nReal n8n run on a demo clinic site. The AI answer is simulated and labelled; the rule shown is the real prompt n8n sent."),
]
meta = {}
for sc, src, title, extra, body in items:
    assert len(title) <= 100 and "<" not in title, title
    desc = f"{body}\n\n{CTA}{FOOT}\n\n#Shorts #n8n #automation"
    tags = extra + BASE_TAGS
    meta[sc] = {"title": title, "description": desc, "tags": tags, "source_url": (RAW + src) if src else ""}
json.dump(meta, open("youtube/meta.json", "w"), indent=1, ensure_ascii=False)
print(len(meta), "items")
