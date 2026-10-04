# Sports Calendar Merge

One ICS subscription URL that combines:

- Chicago Bears (NFL)
- Chicago Bulls (NBA)
- Colorado Buffaloes football (CFB)
- Indiana Hoosiers football (CFB)
- Colorado Buffaloes men's basketball (CBB)
- Indiana Hoosiers men's basketball (CBB)

`merge.py` pulls each team's schedule from ESPN's public schedule API,
merges the games into a single `docs/merged.ics`, and a GitHub Actions
workflow regenerates it **hourly**. Host the `docs/` folder with GitHub
Pages and the URL stays fresh on its own.

Event titles look like `Bears vs Packers (NFL)` or
`Colorado at Utah (CFB)`. Completed games get the final score appended
(`· Final 59–37`); games with no announced kickoff time show as
all-day events marked `· Time TBD`.

## Setup (~5 minutes)

You need a free GitHub account.

1. Create a new **public** repository (e.g. `sports-calendar`).
   Public is fine here — these are public sports schedules, nothing private.
2. Upload these files to the repo, keeping the folder structure
   (`merge.py`, `.github/workflows/update.yml`, `docs/`).
   Easiest: on the repo page, *Add file → Upload files* and drag the
   folder contents in (do it once for the root files, once inside
   `.github/workflows/`, once inside `docs/`). Or `git push` if you
   prefer the command line.
3. In the repo, go to **Settings → Pages**:
   - Source: **Deploy from a branch**
   - Branch: **main**, folder: **/docs** → Save.
4. After about a minute your live URL is:
   `https://<your-username>.github.io/sports-calendar/merged.ics`
5. Subscribe on iPhone: **Settings → Calendar → Add Calendar →
   Add Subscription Calendar** → paste the URL.
   (Google Calendar web: Settings → Add calendar → From URL.)
6. Done. The hourly workflow keeps the file fresh; your phone
   re-fetches it on its own (Apple checks roughly hourly,
   Google up to about once a day).

To force a refresh any time: repo → **Actions** →
*Update merged calendar* → **Run workflow**.

## Customizing

- **Add/remove teams:** edit the `ESPN_TEAMS` list at the top of
  `merge.py` (ESPN team ids are in the URL of the team's ESPN page).
- **Also merge plain ICS feeds:** add `{"name": ..., "url": ...}`
  entries to `ICS_FEEDS` in `merge.py` — e.g. a holidays calendar.
  They'll be merged in verbatim.

## Notes

- College basketball schedules for 2026–27 aren't published on ESPN
  yet (season starts in November). They'll appear automatically once
  they are — no action needed.
- If one source fails on a given run, the script keeps the other
  teams rather than producing an empty calendar.
