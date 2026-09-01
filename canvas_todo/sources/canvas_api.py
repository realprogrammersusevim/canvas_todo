from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests
from canvasapi import Canvas

from ..models import AssignmentItem

# Canvas caps token expiration at 90 days, but an unexpired token can slide its
# own expiration forward. Renewing well before the deadline keeps the token
# alive indefinitely without ever regenerating it.
TOKEN_LIFETIME_DAYS = 89
TOKEN_RENEW_WHEN_DAYS_LEFT = 30


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


def expiration_timestamp(days: int) -> str:
    expires = datetime.now(UTC) + timedelta(days=days)

    return expires.strftime("%Y-%m-%dT%H:%M:%SZ")


class CanvasApiSource:
    """Upcoming assignments via the REST API, authenticated with a personal
    access token. Requires an institution that lets you mint one."""

    name = "canvas-api"

    def __init__(
        self,
        api_url: str,
        api_key: str,
        token_id: str | None = None,
        env_file: Path = Path(".env"),
    ) -> None:
        self.api_url = api_url
        self.api_key = api_key
        self.token_id = token_id
        self.env_file = env_file
        self.canvas = Canvas(api_url, api_key)

    def request(self, method: str, path: str, **kwargs) -> requests.Response:
        """Call a Canvas REST endpoint that canvasapi doesn't wrap."""
        base_url = (self.api_url or "").rstrip("/")
        headers = {"Authorization": f"Bearer {self.api_key}"}

        return requests.request(
            method, f"{base_url}/api/v1{path}", headers=headers, timeout=30, **kwargs
        )

    def write_env_values(self, values: dict[str, str]) -> None:
        """Update keys in .env in place, leaving comments and other keys alone."""
        lines = self.env_file.read_text().splitlines() if self.env_file.exists() else []
        pending = dict(values)

        for index, line in enumerate(lines):
            key = line.split("=", 1)[0].strip()
            if key in pending:
                lines[index] = f'{key}="{pending.pop(key)}"'

        for key, value in pending.items():
            lines.append(f'{key}="{value}"')

        self.env_file.write_text("\n".join(lines) + "\n")

    def bootstrap_token(self) -> None:
        """Create a token this script owns, so it can renew it on every sync."""
        user = self.request("GET", "/users/self")
        if not user.ok:
            print(
                f"Current API_KEY isn't working ({user.status_code}). Nothing created."
            )
            return

        created = self.request(
            "POST",
            f"/users/{user.json()['id']}/tokens",
            data={
                "token[purpose]": "canvas_todo",
                "token[expires_at]": expiration_timestamp(TOKEN_LIFETIME_DAYS),
            },
        )
        if not created.ok:
            print(f"Could not create a token ({created.status_code}): {created.text}")
            return

        token = created.json()
        # The full token string is only ever returned at creation time.
        self.write_env_values(
            {"API_KEY": token["visible_token"], "TOKEN_ID": str(token["id"])}
        )

        print(f"Created token {token['id']}, expiring {token['expires_at']}.")
        print("Saved to .env. Syncs will now renew it automatically.")

    def renew_token_if_needed(self) -> None:
        if not self.token_id:
            return

        current = self.request("GET", f"/users/self/tokens/{self.token_id}")
        if not current.ok:
            print(
                f"Warning: couldn't read token {self.token_id} ({current.status_code})."
            )
            return

        expires_at = parse_canvas_datetime(current.json().get("expires_at"))
        if not expires_at:
            return

        days_left = (expires_at - datetime.now().astimezone()).days
        if days_left > TOKEN_RENEW_WHEN_DAYS_LEFT:
            return

        renewed = self.request(
            "PUT",
            f"/users/self/tokens/{self.token_id}",
            data={"token[expires_at]": expiration_timestamp(TOKEN_LIFETIME_DAYS)},
        )
        if renewed.ok:
            print(f"Renewed access token, now expiring {renewed.json()['expires_at']}.")
        else:
            print(
                f"Warning: token renewal failed ({renewed.status_code}) "
                f"with {days_left} day(s) left. Run --bootstrap-token before it lapses."
            )

    def fetch_upcoming(self) -> list[AssignmentItem]:
        self.renew_token_if_needed()

        user = self.canvas.get_current_user()

        # if there aren't favorited courses this defaults to enrolled courses
        courses = user.get_favorite_courses()

        items = []

        for course in courses:
            # Check if course has a name (some are restricting access)
            if not hasattr(course, "name"):
                continue

            print(f"Checking course: {course.name}")

            # "bucket='upcoming'" fetches only future assignments
            for assignment in course.get_assignments(bucket="upcoming"):
                due = parse_canvas_datetime(assignment.due_at)
                items.append(
                    AssignmentItem(
                        id=str(assignment.id),
                        course=course.name,
                        title=assignment.name,
                        url=assignment.html_url,
                        due=due.date() if due else None,
                        description_html=assignment.description or "",
                    )
                )

        return items
