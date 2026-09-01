import re
from datetime import date, datetime

import requests
from icalendar import Calendar

from ..models import AssignmentItem

# "Assignment Title [COURSE-CODE]" -- Canvas appends the course code, not the
# course name, and there is no way to resolve the full name without the API.
SUMMARY_PATTERN = re.compile(r"^(.*) \[([^\]]+)\]$")

# The URL property looks like:
#   https://host/calendar?include_contexts=course_13631&month=08&year=2026#assignment_1160527
# Canvas rewrites UID to the override id when a section-specific due date
# applies, but never rewrites this URL, so the fragment is the only dependable
# source of the real assignment id.
CONTEXT_PATTERN = re.compile(r"include_contexts=course_(\d+)")
ASSET_PATTERN = re.compile(r"#([a-z_]+)_(\d+)$")
HOST_PATTERN = re.compile(r"^https?://[^/]+")

# Canvas injects institution theme assets into the HTML description.
NOISE_TAGS_PATTERN = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>|<link\b[^>]*>", re.DOTALL | re.IGNORECASE
)


def ics_unescape(text: str) -> str:
    """Undo RFC 5545 text escaping.

    icalendar does this for standard properties, but X-ALT-DESC is non-standard
    so it comes back raw, literal backslash-n and all.
    """
    return re.sub(
        r"\\([\;,nN])",
        lambda match: "\n" if match.group(1) in "nN" else match.group(1),
        text,
    )


class IcsFeedSource:
    """Upcoming assignments via the personal calendar feed.

    The feed URL is unauthenticated and needs no personal access token, which
    makes it the fallback when an institution disables token creation. Get it
    from Canvas under Calendar -> Calendar Feed; treat it as a secret, since
    anyone holding it can read your calendar.

    What the feed cannot do: it covers 30 days back to 366 days forward, capped
    at 1000 assignments; it carries course codes rather than course names; it
    spans every active enrollment rather than just favorites; and a course shows
    up only once it has assignments with due dates.
    """

    name = "ics-feed"

    def __init__(
        self,
        feed_url: str,
        course_codes: set[str] | None = None,
        today: date | None = None,
    ) -> None:
        self.feed_url = feed_url
        # Empty means every course in the feed.
        self.course_codes = {code.casefold() for code in course_codes or set()}
        self.today = today or datetime.now().astimezone().date()

    def fetch(self) -> bytes:
        response = requests.get(self.feed_url, timeout=30)
        response.raise_for_status()

        return response.content

    def fetch_upcoming(self) -> list[AssignmentItem]:
        calendar = Calendar.from_ical(self.fetch())

        items = []
        for event in calendar.walk("VEVENT"):
            item = self.parse_event(event)
            if not item or not item.due or item.due < self.today:
                continue
            if self.course_codes and item.course.casefold() not in self.course_codes:
                continue

            items.append(item)

        return items

    def parse_event(self, event) -> AssignmentItem | None:
        url = str(event.get("URL") or "")
        asset = ASSET_PATTERN.search(url)
        context = CONTEXT_PATTERN.search(url)
        host = HOST_PATTERN.match(url)

        # Personal and course calendar events ride along in the same feed;
        # only assignments become tasks.
        if not (asset and context and host) or asset.group(1) != "assignment":
            return None

        assignment_id = asset.group(2)

        summary = str(event.get("SUMMARY") or "")
        matched = SUMMARY_PATTERN.match(summary)
        title, course = matched.groups() if matched else (summary, "Canvas")

        description_html = ics_unescape(str(event.get("X-ALT-DESC") or ""))

        return AssignmentItem(
            id=assignment_id,
            course=course.strip(),
            title=title.strip(),
            url=f"{host.group(0)}/courses/{context.group(1)}/assignments/{assignment_id}",
            due=self.parse_due(event),
            description_html=NOISE_TAGS_PATTERN.sub("", description_html),
        )

    def parse_due(self, event) -> date | None:
        """Assignments due at end of day arrive as an all-day DATE that Canvas
        has already localized; everything else is a UTC timestamp we localize
        ourselves."""
        try:
            start = event.decoded("DTSTART")
        except (KeyError, ValueError):
            return None

        if isinstance(start, datetime):
            return start.astimezone().date()

        return start if isinstance(start, date) else None
