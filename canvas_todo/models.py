from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class AssignmentItem:
    """One upcoming assignment, normalized across input sources.

    Sources resolve their own quirks (timezones, truncation, id schemes) before
    constructing one of these, so everything downstream is source-agnostic.
    """

    id: str
    course: str
    title: str
    url: str
    due: date | None = None
    description_html: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def task_title(self) -> str:
        return f"{self.course}: {self.title}"
