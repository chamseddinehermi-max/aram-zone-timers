"""Posts the Aram Zone Halloween event ads through Discord webhooks, every 3 hours.

Each ad keeps ONE copy in its channel: a fresh copy deletes the one before it.
At its end time an ad stops and its last copy is deleted.
Webhook links come from environment variables (GitHub secrets), never from this repo.
Standard library only, so the workflow needs no install step.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")

GUILD = "683693724521463839"
EVERY = 3 * 3600
# The workflow wakes every 30 minutes and GitHub can start it late, so an ad is due
# a little before 3 hours have passed. Otherwise it would slip to 3h30 each time.
EARLY = 10 * 60
ORANGE = 0xF28A2E

JEOPARDY_AT = 1793386800        # Fri 30 Oct 2026 19:00 UTC = 20:00 CET
JEOPARDY_SIGNUP = "1562873127946559599"
CUP_AT = 1794070800             # Sat 7 Nov 2026 17:00 UTC = 18:00 Tunisia
CUP_CHECKIN = CUP_AT - 15 * 60
CUP_SIGNUP = "861952017752129547"      # #tournaments, where Elobby's Register team post lives
CUP_TEAMMATES = "1561780940345311263"  # #lf-tournament-euw

UA = "DiscordBot (https://github.com/chamseddinehermi-max/aram-zone-timers, 1.0)"


def channel_url(channel_id):
    return f"https://discord.com/channels/{GUILD}/{channel_id}"


def text(content):
    return {"type": 10, "content": content}


def divider(big=True):
    return {"type": 14, "divider": True, "spacing": 2 if big else 1}


def signup_button(channel_id):
    return {"type": 1, "components": [
        {"type": 2, "style": 5, "label": "Sign up", "url": channel_url(channel_id)}]}


def jeopardy():
    return {
        "flags": 32768,
        "components": [{
            "type": 17, "accent_color": ORANGE, "components": [
                text(f"## Aram Zone Jeopardy is this Friday\n"
                     f"**<t:{JEOPARDY_AT}:F>** · starts <t:{JEOPARDY_AT}:R>"),
                divider(big=False),
                text("- **Teams of 2**, so bring a teammate\n"
                     "- **Every player gets 10 million** to spend in the casino\n"
                     "- **The questions are about you.** We build them around the people who "
                     "sign up: your inside jokes, your voice lines, your moments in the server.\n"
                     "- Plus the hardest Halloween questions we could find\n\n"
                     f"It's going to be a lot of fun. Sign up in <#{JEOPARDY_SIGNUP}>."),
                signup_button(JEOPARDY_SIGNUP),
            ]}],
        "allowed_mentions": {"parse": []},
    }, []


def cup():
    return {
        "flags": 32768,
        "components": [
            {"type": 12, "items": [{"media": {"url": "attachment://cup-banner.png"}}]},
            {"type": 17, "accent_color": ORANGE, "components": [
                text("# Halloween Mayhem Cup\n**ARAM Mayhem** · 3v3 · EUW"),
                divider(),
                text(f"### When\n**<t:{CUP_AT}:F>**\n"
                     f"-# Starts <t:{CUP_AT}:R> · check-in opens at <t:{CUP_CHECKIN}:t>"),
                divider(),
                text("### Prizes\n"
                     "- **1st:** 2 epic skins each + the champion role\n"
                     "- **2nd:** 1 epic skin each\n"
                     "- **3rd:** 1 mystery skin each"),
                divider(),
                text("### How to sign up\n"
                     "Team up with two friends. Your captain presses **Register team** on the "
                     f"cup's post in <#{CUP_SIGNUP}> before check-in opens.\n"
                     f"No team yet? Find teammates in <#{CUP_TEAMMATES}>."),
                signup_button(CUP_SIGNUP),
                divider(big=False),
                text("-# Aram Zone Halloween Events"),
            ]}],
        "attachments": [{"id": 0, "filename": "cup-banner.png"}],
        "allowed_mentions": {"parse": []},
    }, [os.path.join(HERE, "assets", "cup-banner.png")]


ADS = [
    {"key": "jeopardy-genchat", "webhook": "WEBHOOK_GENCHAT", "ends": JEOPARDY_AT, "build": jeopardy},
    {"key": "cup-lfmayhem", "webhook": "WEBHOOK_LFMAYHEM", "ends": CUP_CHECKIN, "build": cup},
]


def call(method, url, body=None, content_type=None):
    """One Discord request, retried once on a rate limit. Never prints the url (it is a secret)."""
    for attempt in range(2):
        req = urllib.request.Request(url, data=body, method=method, headers={"User-Agent": UA})
        if content_type:
            req.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                return resp.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            raw = e.read()
            if e.code == 429 and attempt == 0:
                time.sleep(float(json.loads(raw or b"{}").get("retry_after", 2)) + 0.5)
                continue
            return e.code, raw.decode("utf-8", "replace")
    return 429, "rate limited twice"


def send(webhook, payload, files):
    url = f"{webhook}?wait=true&with_components=true"
    if not files:
        return call("POST", url, json.dumps(payload).encode(), "application/json")
    boundary = uuid.uuid4().hex
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="payload_json"\r\n'
             f"Content-Type: application/json\r\n\r\n".encode() + json.dumps(payload).encode()]
    for i, path in enumerate(files):
        with open(path, "rb") as f:
            data = f.read()
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="files[{i}]"; '
                     f'filename="{os.path.basename(path)}"\r\nContent-Type: image/png\r\n\r\n'
                     .encode() + data)
    body = b"\r\n".join(parts) + f"\r\n--{boundary}--\r\n".encode()
    return call("POST", url, body, f"multipart/form-data; boundary={boundary}")


def delete(webhook, message_id):
    status, body = call("DELETE", f"{webhook}/messages/{message_id}")
    # 404: someone already deleted it by hand, which is fine.
    return status in (200, 204, 404), status, body


def main():
    with open(STATE) as f:
        state = json.load(f)
    now = time.time()
    failed = False
    for ad in ADS:
        key, webhook = ad["key"], os.environ.get(ad["webhook"], "").strip()
        last = state.get(key)
        if not webhook:
            print(f"{key}: no webhook yet, skipped")
            continue
        if now >= ad["ends"]:
            if last:
                ok, status, body = delete(webhook, last["id"])
                print(f"{key}: ended, last copy deleted ({status})")
                if ok:
                    state.pop(key)
                else:
                    failed = True
                    print(f"  {body}")
            continue
        built = ad["build"]()
        if built is None:
            print(f"{key}: not ready yet, skipped")
            continue
        if last and now - last["at"] < EVERY - EARLY:
            print(f"{key}: next copy in {int((last['at'] + EVERY - EARLY - now) / 60)} min")
            continue
        payload, files = built
        status, body = send(webhook, payload, files)
        if status != 200:
            failed = True
            print(f"{key}: post failed ({status}) {body}")
            continue
        if last:
            ok, dstatus, dbody = delete(webhook, last["id"])
            if not ok:
                print(f"{key}: old copy {last['id']} not deleted ({dstatus}) {dbody}")
        state[key] = {"id": body["id"], "at": int(now)}
        print(f"{key}: posted {body['id']}")
    with open(STATE, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")
    done = now >= max(ad["ends"] for ad in ADS) and not state
    if done:
        open(os.path.join(HERE, "DONE"), "w").close()
        print("every ad has ended")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
