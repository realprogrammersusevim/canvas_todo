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

3. Run:
   ```sh
   uv run main.py
   ```

Things 3 must be open on your Mac for the tasks to be added.
