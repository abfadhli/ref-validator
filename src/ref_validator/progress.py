"""Progress callback protocol."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ProgressCallback(Protocol):
    def on_start(self, total: int, description: str) -> None: ...
    def on_advance(self, amount: int = 1) -> None: ...
    def on_message(self, message: str) -> None: ...
    def on_finish(self) -> None: ...


class NullProgress:
    """No-op progress callback."""

    def on_start(self, total: int, description: str) -> None:
        pass

    def on_advance(self, amount: int = 1) -> None:
        pass

    def on_message(self, message: str) -> None:
        pass

    def on_finish(self) -> None:
        pass
