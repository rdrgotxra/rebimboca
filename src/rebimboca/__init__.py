"""rebimboca — live coding sobre modelos IFC."""

from typing import TYPE_CHECKING, Any

from .project import GeometryData, Project

if TYPE_CHECKING:
    from .view import View
    from .viewport import Viewport

__all__ = ["GeometryData", "Project", "View", "Viewport"]


def __getattr__(name: str) -> Any:
    if name == "View":
        from .view import View

        return View
    if name == "Viewport":
        from .viewport import Viewport

        return Viewport
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
