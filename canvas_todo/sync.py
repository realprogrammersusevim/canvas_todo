from datetime import date

from .cache import ImportCache
from .sources.base import AssignmentSource


def sync(source: AssignmentSource, inbox, cache: ImportCache) -> int:
    print(f"Fetching assignments from {source.name}...")

    new_items = [item for item in source.fetch_upcoming() if item.id not in cache]

    # Things prepends to the Inbox, so add in reverse to land in date order.
    new_items.sort(
        key=lambda item: (item.due or date.max, item.course.lower()), reverse=True
    )

    print(f"{len(new_items)} new assignment(s)")

    for item in new_items:
        inbox.add(item)
        cache.add(item.id)

    cache.save()

    return len(new_items)
