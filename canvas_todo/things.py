import subprocess
import urllib.parse
import webbrowser

from markdownify import markdownify as html_to_markdown

from .models import AssignmentItem


def format_description(description_html: str) -> str:
    if not description_html:
        return ""

    return html_to_markdown(description_html).strip()


def build_notes(item: AssignmentItem) -> str:
    notes = f"Link: {item.url}"
    description_md = format_description(item.description_html)
    if description_md:
        notes = f"{notes}\n\n{description_md}"

    return notes


class ThingsInbox:
    """Adds tasks to the Things 3 Inbox via its URL scheme.

    Every task is tagged so migrate_tasks can find it again later.
    """

    def __init__(self, tag_name: str = "New", area_name: str = "New") -> None:
        self.tag_name = tag_name
        self.area_name = area_name

    def add(self, item: AssignmentItem) -> None:
        params = {
            "title": item.task_title,
            "notes": build_notes(item),
            "tags": ",".join([*item.tags, self.tag_name]),
            "show-quick-entry": "false",
        }

        if item.due:
            # Things 3 accepts YYYY-MM-DD for deadlines
            params["deadline"] = item.due.strftime("%Y-%m-%d")

        # Encode the URL with %20 for spaces (Things expects percent-encoding).
        webbrowser.open(
            "things:///add?"
            + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        )

    def migrate_tasks(self) -> None:
        """
        Uses AppleScript to find all tagged todos that are no longer in the
        Inbox (i.e. have been reviewed and scheduled) and moves them to a list.
        """
        script = f"""
    tell application "Things3"
        set targetArea to area "{self.area_name}"
        set inboxIds to id of (to dos of list "Inbox")
        set movedCount to 0

        repeat with aTodo in (to dos)
            set todoTags to tag names of aTodo
            if "{self.tag_name}" is in todoTags then
                if (id of aTodo) is not in inboxIds then
                    move aTodo to targetArea
                    set currentTags to tags of aTodo
                    set newTags to {{}}
                    repeat with aTag in currentTags
                        set tagValue to name of aTag
                        if tagValue is not "{self.tag_name}" then
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
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            print(f"Migration failed: {result.stderr.strip()}")
        else:
            count = result.stdout.strip()
            print(
                f"Migration complete! Moved {count} {self.tag_name} tagged task(s) "
                f"to the {self.area_name} area."
            )


class DryRunInbox:
    """Prints what would be created instead of touching Things.

    Handy when pointing the sync at a new source for the first time.
    """

    def add(self, item: AssignmentItem) -> None:
        due = item.due.isoformat() if item.due else "no due date"
        notes = build_notes(item)
        print(f"  [{due}] {item.task_title}")
        print(f"      {len(notes)} chars of notes -> {item.url}")
