# canvas-todo

Pulls upcoming assignments from Canvas LMS and adds them to
[Things 3](https://culturedcode.com/things/) as tasks, with deadlines and notes.

## How it works

1. Fetches all upcoming assignments across your active Canvas courses via the
   Canvas API
2. Skips any assignments already imported (tracked in
   `.imported_assignments.json`)
3. Creates a Things 3 task for each new assignment with:
   - Title: `Course Name: Assignment Name`
   - Deadline: due date from Canvas (converted to local time)
   - Notes: link to the assignment page + description in Markdown
4. Saves imported assignment IDs so re-running won't create duplicates

## Setup

1. Install dependencies:

   ```sh
   uv sync
   ```

2. Create a `.env` file:

   ```
   API_URL=https://your-institution.instructure.com
   API_KEY=your_canvas_api_token
   LIST_NAME=                # optional: Things 3 list/project to add tasks to
   ```

   Get your Canvas API token from **Account → Settings → New Access Token**.

3. Hand token management over to the script (optional but recommended):

   ```sh
   uv run main.py --bootstrap-token
   ```

   This creates a token the script owns and writes `API_KEY` and `TOKEN_ID` back
   to `.env`. See [Token renewal](#token-renewal) below.

4. Run:
   ```sh
   uv run main.py
   ```

Things 3 must be open on your Mac for the tasks to be added.

## Token renewal

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
