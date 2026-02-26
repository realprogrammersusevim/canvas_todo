import json
import os
from pathlib import Path
import webbrowser
import urllib.parse
from datetime import datetime

from canvasapi import Canvas
from dotenv import load_dotenv
from markdownify import markdownify as html_to_markdown

# Initialize Canvas
load_dotenv()
canvas = Canvas(os.getenv("API_URL"), os.getenv("API_KEY"))

IMPORT_CACHE = Path(".imported_assignments.json")


def load_imported_ids() -> set[str]:
    if not IMPORT_CACHE.exists():
        return set()

    return set(json.loads(IMPORT_CACHE.read_text()))


def save_imported_ids(ids_set: set[str]) -> None:
    IMPORT_CACHE.write_text(json.dumps(sorted(ids_set), indent=2))


def parse_canvas_datetime(date: str) -> datetime | None:
    if not date:
        return None

    try:
        # Canvas returns UTC timestamps with a trailing "Z".
        # Convert to local time so the date isn't off by one.
        iso_str = date.replace("Z", "+00:00")
        return datetime.fromisoformat(iso_str).astimezone()
    except ValueError:
        return None


def add_to_things(title: str, notes: str, date_str: str, tags=[]) -> None:
    """
    Constructs a Things 3 URL to add a task and executes it.
    """
    # Base Things 3 URL
    base_url = "things:///add?"

    # Parameters for the task
    params = {
        "title": title,
        "notes": notes,
        "tags": f"{','.join(tags)},New",
        "show-quick-entry": "false",  # Set to 'true' if you want to verify before adding
    }

    # Add Canvas todos to a specific list
    list_name = os.getenv("LIST_NAME")
    if list_name and list_name != "":
        params["list"] = list_name

    # Handle Date Parsing (Canvas returns ISO 8601: 2023-10-27T23:59:59Z)
    dt_obj = parse_canvas_datetime(date_str)
    if dt_obj:
        # Things 3 accepts YYYY-MM-DD for deadlines
        params["deadline"] = dt_obj.strftime("%Y-%m-%d")

    # Encode the URL with %20 for spaces (Things expects percent-encoding).
    final_url = base_url + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)

    # Open the URL (Fires the command to Things 3)
    webbrowser.open(final_url)


def format_description(description_html: str):
    if not description_html:
        return ""

    return html_to_markdown(description_html).strip()


def main():
    imported_ids = load_imported_ids()

    # Get current user
    user = canvas.get_current_user()

    # if there aren't favorited courses this defaults to enrolled courses
    courses = user.get_favorite_courses()

    print("Fetching assignments...")

    assignment_entries = []

    for course in courses:
        # Check if course has a name (some are restricting access)
        if not hasattr(course, "name"):
            continue

        print(f"Checking course: {course.name}")

        # Get upcoming assignments
        # "bucket='upcoming'" fetches only future assignments
        assignments = course.get_assignments(bucket="upcoming")

        for assignment in assignments:
            if str(assignment.id) in imported_ids:
                continue

            due_dt = parse_canvas_datetime(assignment.due_at)
            assignment_entries.append((due_dt, course.name, assignment))

    assignment_entries.sort(
        key=lambda entry: (
            entry[0] or datetime.max,
            entry[1].lower(),
        ),
        reverse=True,
    )

    print(f"Adding {len(assignment_entries)} Todos to Things")

    for due_dt, course_name, assignment in assignment_entries:
        # Construct the task title (Course Name: Assignment Name)
        task_title = f"{course_name}: {assignment.name}"

        # Create notes with a link back to Canvas
        # 'html_url' is the link to the assignment page
        description_md = format_description(assignment.description)
        task_notes = f"Link: {assignment.html_url}"
        if description_md:
            task_notes = f"{task_notes}\n\n{description_md}"

        add_to_things(task_title, task_notes, assignment.due_at)
        imported_ids.add(str(assignment.id))

    print("Done! Check your Things 3 Inbox.")
    save_imported_ids(imported_ids)


if __name__ == "__main__":
    main()
