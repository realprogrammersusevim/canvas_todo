# canvas-todo

Pulls upcoming assignments from Canvas LMS and adds them to
[Things 3](https://culturedcode.com/things/) as tasks, with deadlines and notes.

## How it works

1. Fetches upcoming assignments from an **input source** (see below)
2. Skips any assignments already imported (tracked in
   `.imported_assignments.json`)
3. Creates a Things 3 task for each new assignment with:
   - Title: `Course: Assignment Name`
   - Deadline: due date from Canvas (converted to local time)
   - Notes: link to the assignment page + description in Markdown
4. Saves imported assignment IDs so re-running won't create duplicates

## Input sources

Assignments can come from either of two sources, which are interchangeable —
everything downstream of `AssignmentSource.fetch_upcoming()` is source-agnostic.

| | `--source api` | `--source ics` |
|---|---|---|
| Credential | personal access token | calendar feed URL |
| Course label | full course name | course code |
| Scope | favorited courses | every active enrollment |
| Coverage | all upcoming | 30 days back to 366 forward, max 1000 |
| Expiry | 90 days, auto-renewed | none |

`--source auto` (the default) uses the feed when `ICS_URL` is set, otherwise the
API.

Prefer the API when your institution lets you mint a token: it gives real course
names and honors your favorites. Use the feed when it doesn't — some Canvas
instances disable self-service token creation, leaving the feed as the only way
in without an admin.

## Setup

1. Install dependencies:

   ```sh
   uv sync
   ```

2. Create a `.env` file with the settings for whichever source you're using:

   ```
   # Shared
   AREA_NAME=                # Things 3 area that --migrate moves tasks into
   TAG_NAME=                 # tag applied to new tasks, used to find them later

   # API source
   API_URL=https://your-institution.instructure.com
   API_KEY=your_canvas_api_token

   # ICS source
   ICS_URL=https://your-institution.instructure.com/feeds/calendars/user_XXXX.ics
   COURSE_CODES=             # optional: comma-separated allowlist, e.g. CSCE-361.001.1268
   ```

   An API token comes from **Account → Settings → New Access Token**. A feed URL
   comes from **Calendar → Calendar Feed**; it needs no token, but it is itself
   the credential, so treat it like a password.

3. Hand token management over to the script (API source only, optional but
   recommended):

   ```sh
   uv run main.py --bootstrap-token
   ```

   This creates a token the script owns and writes `API_KEY` and `TOKEN_ID` back
   to `.env`. See [Token renewal](#token-renewal) below.

4. Check what would be imported, then run for real:

   ```sh
   uv run main.py --dry-run
   uv run main.py
   ```

Things 3 must be open on your Mac for the tasks to be added.

## Usage

```sh
uv run main.py                    # sync
uv run main.py --dry-run          # print what would be added, touch nothing
uv run main.py --source ics       # force a specific input source
uv run main.py --migrate          # move reviewed tasks out of the Inbox
uv run main.py --all              # sync, then migrate
```

## Token renewal

Applies to the API source only; feed URLs don't expire.

Canvas refuses to issue an access token more than 90 days out, so a hand-made
token silently breaks the sync every quarter. An unexpired token can, however,
push its own expiration date forward — so a token that gets used regularly never
has to expire.

After `--bootstrap-token`, every sync checks the token and slides its expiration
back out to 89 days whenever fewer than 30 days remain. The token string itself
never changes, so nothing else needs updating.

The one catch: this only works while the token is still valid. If you don't sync
for 30+ consecutive days after the last renewal, the token lapses and you'll
need a new one from Canvas settings plus another `--bootstrap-token`. Running
the sync on a schedule (or just using it) avoids this entirely.

## Feed caveats

The calendar feed is a thinner slice of Canvas than the API:

- Course **codes**, not names (`CSCE-361.001.1268`, not `Software Engineering`).
  Canvas doesn't put the name in the feed and there's no way to resolve it
  without API access.
- Every active enrollment shows up, not just favorites. Narrow it with
  `COURSE_CODES`.
- A course appears only once it has assignments with due dates on it.
- Assignments with no due date never appear (the API's `upcoming` bucket
  excludes them too, so this matches).

## Layout

```
main.py                        CLI and wiring: reads config, picks a source
canvas_todo/
  models.py                    AssignmentItem, the shared shape
  cache.py                     already-imported ids
  sync.py                      source -> inbox, ordering and dedupe
  things.py                    Things 3 URL scheme + AppleScript migration
  sources/
    base.py                    the AssignmentSource protocol
    canvas_api.py              REST API + access token management
    ics_feed.py                calendar feed parsing
```

Adding a source means implementing `fetch_upcoming()` and returning
`AssignmentItem`s; nothing else has to change.
