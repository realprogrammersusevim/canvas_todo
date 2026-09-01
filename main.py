"""Composition root: reads configuration, picks an input source, wires it to Things."""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from canvas_todo.cache import ImportCache
from canvas_todo.sources import AssignmentSource, CanvasApiSource, IcsFeedSource
from canvas_todo.sync import sync
from canvas_todo.things import DryRunInbox, ThingsInbox

IMPORT_CACHE = Path(".imported_assignments.json")
ENV_FILE = Path(".env")


def build_source(choice: str) -> AssignmentSource:
    """Construct the requested input source, or explain what configuration is missing."""
    feed_url = os.getenv("ICS_URL")
    api_url, api_key = os.getenv("API_URL"), os.getenv("API_KEY")

    if choice == "auto":
        choice = "ics" if feed_url else "api"

    if choice == "ics":
        if not feed_url:
            sys.exit(
                "No ICS_URL in .env. Get the feed URL from Canvas under "
                "Calendar -> Calendar Feed."
            )

        codes = {
            code.strip()
            for code in (os.getenv("COURSE_CODES") or "").split(",")
            if code.strip()
        }

        return IcsFeedSource(feed_url, course_codes=codes)

    if not (api_url and api_key):
        sys.exit(
            "No API_URL/API_KEY in .env. Canvas access tokens come from "
            "Account -> Settings -> New Access Token."
        )

    return CanvasApiSource(
        api_url, api_key, token_id=os.getenv("TOKEN_ID"), env_file=ENV_FILE
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Canvas to Things 3 task sync")
    parser.add_argument(
        "--source",
        choices=["auto", "api", "ics"],
        default="auto",
        help="Where assignments come from: the REST API (needs a personal access "
        "token) or the calendar feed (needs none). Default picks the feed when "
        "ICS_URL is set.",
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Migrate tagged tasks out of Inbox to the configured area",
    )
    parser.add_argument("--all", action="store_true", help="Sync and migrate tasks")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be added without touching Things or the import cache",
    )
    parser.add_argument(
        "--bootstrap-token",
        action="store_true",
        help="Create a self-renewing access token and save it to .env (API source only)",
    )
    args = parser.parse_args()

    load_dotenv()

    inbox = ThingsInbox(
        tag_name=os.getenv("TAG_NAME", "New"), area_name=os.getenv("AREA_NAME", "New")
    )

    if args.bootstrap_token:
        source = build_source("api")
        source.bootstrap_token()
        return

    if args.migrate:
        inbox.migrate_tasks()
        return

    cache = ImportCache(IMPORT_CACHE, persist=not args.dry_run)
    sync(build_source(args.source), DryRunInbox() if args.dry_run else inbox, cache)

    if args.dry_run:
        return

    print("Done! Check your Things 3 Inbox.")

    if args.all:
        inbox.migrate_tasks()


if __name__ == "__main__":
    main()
