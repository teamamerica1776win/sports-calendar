#!/usr/bin/env python3
"""
Merged sports calendar -> single ICS file.

Sources:
  1. ESPN's public schedule API for the configured teams (no API key needed).
  2. Any plain ICS feed URLs you add to ICS_FEEDS (merged in verbatim).

Output is a single ICS file. Run it on a schedule (see
.github/workflows/update.yml) and host the output file at a stable URL
(e.g. GitHub Pages) for a continuously-updating subscription calendar.

Stdlib only -- no pip dependencies.
"""

import datetime
import json
import os
import re
import sys
import urllib.request

# ---------------------------------------------------------------- config ---

CALENDAR_NAME = "Charlie's Sports"

# Teams pulled from ESPN. `sport` is the ESPN API path, `id` the ESPN team id.
# label/tag are only used to build readable event titles.
ESPN_TEAMS = [
    {"label": "Bears",    "tag": "NFL", "sport": "football/nfl",                    "id": "3",  "hours": 3.0},
    {"label": "Bulls",    "tag": "NBA", "sport": "basketball/nba",                  "id": "4",  "hours": 2.5},
    {"label": "Colorado", "tag": "CFB", "sport": "football/college-football",       "id": "38", "hours": 3.5},
    {"label": "Indiana",  "tag": "CFB", "sport": "football/college-football",       "id": "84", "hours": 3.5},
    {"label": "Colorado", "tag": "CBB", "sport": "basketball/mens-college-basketball", "id": "38", "hours": 2.5},
    {"label": "Indiana",  "tag": "CBB", "sport": "basketball/mens-college-basketball", "id": "84", "hours": 2.5},
]

# Plain ICS feeds to merge in as-is. Example:
# ICS_FEEDS = [
#     {"name": "US Holidays", "url": "https://www.officeholidays.com/ics/usa"},
# ]
ICS_FEEDS = []

OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "merged.ics")

USER_AGENT = "Mozilla/5.0 (compatible; sports-calendar-merge/1.0)"

# ------------------------------------------------------------- ics bits ---

def ics_escape(text):
    """Escape text for ICS property values."""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def fold_line(line):
    """Fold a single ICS content line to the 75-octet limit (RFC 5545 3.1)."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, chunk = [], b""
    for byte in [raw[i:i+1] for i in range(len(raw))]:
        # Never split a multi-byte UTF-8 sequence: keep whole chars together.
        if len(chunk) + len(byte) > 75 and chunk:
            parts.append(chunk)
            chunk = b" "
        chunk += byte
    parts.append(chunk)
    return b"\r\n".join(parts).decode("utf-8")


def prop(name, value, params=""):
    return fold_line(f"{name}{params}:{ics_escape(value)}")


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


# ------------------------------------------------------------ espn bits ---

def parse_espn_dt(s):
    # "2026-09-13T17:00Z" -> aware datetime in UTC
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def espn_events(team):
    """Yield (sort_key, vevent_block) tuples for one ESPN team."""
    url = (
        "https://site.api.espn.com/apis/site/v2/sports/"
        f"{team['sport']}/teams/{team['id']}/schedule"
    )
    data = fetch_json(url)
    out = []
    for e in data.get("events", []):
        try:
            out.append(build_espn_vevent(e, team))
        except Exception as exc:  # one bad game must not kill the calendar
            print(f"  ! skipping event {e.get('id')}: {exc}", file=sys.stderr)
    return out


def build_espn_vevent(e, team):
    eid = str(e["id"])
    comp = e["competitions"][0]
    start = parse_espn_dt(comp.get("date") or e["date"])
    time_valid = comp.get("timeValid", True)

    status = comp.get("status", {}).get("type", {})
    completed = bool(status.get("completed"))

    us, them = None, None
    for c in comp.get("competitors", []):
        if str(c.get("id")) == team["id"]:
            us = c
        else:
            them = c
    if us is None or them is None:
        raise ValueError("could not identify teams")

    we_home = us.get("homeAway") == "home"
    opp_name = them["team"].get("shortDisplayName") or them["team"].get("displayName")
    matchup = f"{team['label']} vs {opp_name}" if we_home else f"{team['label']} at {opp_name}"
    title = f"{matchup} ({team['tag']})"

    desc_lines = []
    week_text = (e.get("week") or {}).get("text")
    if week_text:
        desc_lines.append(week_text)

    broadcasts = []
    for b in comp.get("broadcasts", []):
        names = b.get("names") or ([b.get("shortName")] if b.get("shortName") else [])
        broadcasts.extend(n for n in names if n)
    if broadcasts:
        desc_lines.append("TV: " + ", ".join(dict.fromkeys(broadcasts)))

    venue = comp.get("venue") or {}
    addr = venue.get("address") or {}
    city = ", ".join(p for p in (addr.get("city"), addr.get("state")) if p)
    venue_name = venue.get("fullName")
    location = f"{venue_name} ({city})" if venue_name and city else (venue_name or city)
    if location:
        desc_lines.append("Venue: " + location)

    if completed:
        our_score = (us.get("score") or {}).get("displayValue", "?")
        opp_score = (them.get("score") or {}).get("displayValue", "?")
        title += f" \u00b7 Final {our_score}\u2013{opp_score}"
        desc_lines.insert(0, "Result: Final")
    else:
        desc_lines.insert(0, "Status: " + (status.get("description") or "Scheduled"))

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VEVENT",
        prop("UID", f"espn-{eid}@sports-calendar-merge"),
        prop("DTSTAMP", now),
    ]
    if completed or time_valid:
        lines.append(f"DTSTART:{start.strftime('%Y%m%dT%H%M%SZ')}")
        minutes = int(team["hours"] * 60)
        lines.append(f"DURATION:PT{minutes}M")
    else:
        # Time not announced yet -> all-day placeholder so it still shows up.
        title += " \u00b7 Time TBD"
        lines.append(f"DTSTART;VALUE=DATE:{start.strftime('%Y%m%d')}")
    lines += [
        prop("SUMMARY", title),
    ]
    if location:
        lines.append(prop("LOCATION", location))
    if desc_lines:
        lines.append(prop("DESCRIPTION", "\n".join(desc_lines)))
    lines.append("END:VEVENT")

    return (start, "\r\n".join(lines))


# ------------------------------------------------------------- ics feed ---

VEVENT_RE = re.compile(r"BEGIN:VEVENT.*?END:VEVENT", re.DOTALL)
UID_RE = re.compile(r"^UID:(.*)$", re.MULTILINE)
DTSTART_RE = re.compile(r"^DTSTART[^:]*:(.*)$", re.MULTILINE)


def ics_feed_events(feed):
    """Pass VEVENT blocks from a plain ICS feed through unchanged."""
    text = fetch_text(feed["url"])
    out = []
    for m in VEVENT_RE.finditer(text):
        block = m.group(0).replace("\r\n", "\n").replace("\n", "\r\n")
        uid_m = UID_RE.search(block)
        key = uid_m.group(1).strip() if uid_m else block[:60]
        dt_m = DTSTART_RE.search(block)
        sort_key = dt_m.group(1).strip() if dt_m else ""
        out.append((sort_key, f"feed:{key}", block))
    return out


# ----------------------------------------------------------------- main ---

def main():
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    header = [
        "BEGIN:VCALENDAR",
        prop("PRODID", "-//Charlie//Sports Calendar Merge//EN"),
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        prop("X-WR-CALNAME", CALENDAR_NAME),
        "X-PUBLISHED-TTL:PT1H",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
    ]

    seen_uids = set()
    events = []  # (sort_key, uid, block)

    for team in ESPN_TEAMS:
        label = f"{team['label']} ({team['tag']})"
        try:
            team_events = espn_events(team)
        except Exception as exc:
            print(f"! {label}: fetch failed: {exc}", file=sys.stderr)
            continue
        print(f"+ {label}: {len(team_events)} games")
        for start, block in team_events:
            uid = f"espn-{team['id']}-{start.isoformat()}"
            if uid in seen_uids:
                continue
            seen_uids.add(uid)
            events.append((start.isoformat(), uid, block))

    for feed in ICS_FEEDS:
        try:
            feed_events = ics_feed_events(feed)
        except Exception as exc:
            print(f"! feed {feed.get('name', feed['url'])}: fetch failed: {exc}", file=sys.stderr)
            continue
        print(f"+ feed {feed.get('name', feed['url'])}: {len(feed_events)} events")
        for sort_key, uid, block in feed_events:
            if uid in seen_uids:
                continue
            seen_uids.add(uid)
            events.append((sort_key, uid, block))

    events.sort(key=lambda t: t[0])
    body = "\r\n".join([b for _, _, b in events])
    ics = "\r\n".join(header) + "\r\n" + (body + "\r\n" if body else "") + "END:VCALENDAR\r\n"

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8", newline="") as f:
        f.write(ics)
    print(f"Wrote {len(events)} events -> {OUTPUT}")


if __name__ == "__main__":
    main()
