from __future__ import annotations

from typing import TYPE_CHECKING

import pygfx as gfx

if TYPE_CHECKING:
    from .view import View


class Viewport:
    """Infraestrutura gráfica: canvas, renderer e controller."""

    def __init__(self, view: View):
        from rendercanvas.auto import RenderCanvas

        self.view = view
        self.canvas = RenderCanvas(size=(800, 600))
        self.renderer = gfx.WgpuRenderer(self.canvas)
        self.controller = gfx.OrbitController(
            view.camera,
            register_events=self.renderer,
        )
        self.canvas.request_draw(self._draw)

    def _draw(self) -> None:
        self.renderer.render(self.view.scene, self.view.camera)

    def request_draw(self) -> None:
        self.canvas.request_draw()

    def close(self) -> None:
        try:
            self.canvas.close()
        except Exception:
            pass
