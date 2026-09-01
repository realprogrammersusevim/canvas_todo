import json
from pathlib import Path


class ImportCache:
    """Assignment ids already pushed to Things, so re-runs don't duplicate.

    Ids are scoped to whichever Canvas instance produced them; pointing the sync
    at a different host means starting from an empty cache.
    """

    def __init__(self, path: Path, persist: bool = True) -> None:
        self.path = path
        self.persist = persist
        self._ids = set(json.loads(path.read_text())) if path.exists() else set()

    def __contains__(self, assignment_id: str) -> bool:
        return assignment_id in self._ids

    def add(self, assignment_id: str) -> None:
        self._ids.add(assignment_id)

    def save(self) -> None:
        if self.persist:
            self.path.write_text(json.dumps(sorted(self._ids), indent=2))
