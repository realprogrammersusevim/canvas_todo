import json
import os
from pathlib import Path
import argparse
import subprocess
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


def add_to_things(title: str, notes: str, date_str: str, tags: list[str] = []) -> None:
    """
    Constructs a Things 3 URL to add a task to the Inbox and executes it.
    New tasks are always tagged so they can be identified and migrated later.
    """
    base_url = "things:///add?"

    all_tags = list(tags) + [os.getenv("TAG_NAME", "New")]
    params = {
        "title": title,
        "notes": notes,
        "tags": ",".join(all_tags),
        "show-quick-entry": "false",
    }

    # Handle Date Parsing (Canvas returns ISO 8601: 2023-10-27T23:59:59Z)
    dt_obj = parse_canvas_datetime(date_str)
    if dt_obj:
        # Things 3 accepts YYYY-MM-DD for deadlines
        params["deadline"] = dt_obj.strftime("%Y-%m-%d")

    # Encode the URL with %20 for spaces (Things expects percent-encoding).
    final_url = base_url + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)

    # Open the URL (Fires the command to Things 3)
    webbrowser.open(final_url)


def migrate_tasks() -> None:
    """
    Uses AppleScript to find all tagged todos that are no longer in the
    Inbox (i.e. have been reviewed and scheduled) and moves them to a list.
    """
    area_name = os.getenv("AREA_NAME", "New")
    tag_name = os.getenv("TAG_NAME", "New")
    script = f"""
    tell application "Things3"
        set targetArea to area "{area_name}"
        set inboxIds to id of (to dos of list "Inbox")
        set movedCount to 0

        repeat with aTodo in (to dos)
            set todoTags to tag names of aTodo
            if "{tag_name}" is in todoTags then
                if (id of aTodo) is not in inboxIds then
                    move aTodo to targetArea
                    set currentTags to tags of aTodo
                    set newTags to {{}}
                    repeat with aTag in currentTags
                        set tagValue to name of aTag
                        if tagValue is not "{tag_name}" then
                            set end of newTags to tagValue
                        end if
                    end repeat
                    set AppleScript's text item delimiters to ", "
                    set newTagString to newTags as string
                    set AppleScript's text item delimiters to ""
                    set tag names of aTodo to newTagString
                    set movedCount to movedCount + 1
                end if
            end if
        end repeat

        return movedCount as string
    end tell
    """
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Migration failed: {result.stderr.strip()}")
    else:
        count = result.stdout.strip()
        print(
            f"Migration complete! Moved {count} {tag_name} tagged task(s) to the {area_name} area."
        )


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
    parser = argparse.ArgumentParser(description="Canvas to Things 3 task sync")
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Migrate tagged tasks out of Inbox to the configured area",
    )
    parser.add_argument("--all", action="store_true", help="Sync and migrate tasks")
    args = parser.parse_args()

    if args.migrate:
        migrate_tasks()
    elif args.all:
        main()
        migrate_tasks()
    else:
        main()
