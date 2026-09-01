from typing import Protocol

from ..models import AssignmentItem


class AssignmentSource(Protocol):
    """Where upcoming assignments come from.

    An implementation owns its own credentials, its own notion of which courses
    count, and any format-specific date handling. It hands back AssignmentItems
    with local dates already resolved.
    """

    name: str

    def fetch_upcoming(self) -> list[AssignmentItem]:
        """Return assignments due from today onward, in no particular order."""
        ...
