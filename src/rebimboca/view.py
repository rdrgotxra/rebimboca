from __future__ import annotations

from typing import TYPE_CHECKING

import pygfx as gfx

from .project import Project

if TYPE_CHECKING:
    from .viewport import Viewport


class View:
    """Configuração de visualização, independente da viewport aberta.

    Cada View possui sua própria Scene e Camera. A View sobrevive a
    close(); a Viewport gráfica é descartável.
    """

    def __init__(self, project: Project):
        if not isinstance(project, Project):
            raise TypeError(
                f"project deve ser uma instância de Project, "
                f"não {type(project).__name__}"
            )
        self.project = project
        self.scene = gfx.Scene()
        self.camera = gfx.PerspectiveCamera(fov=70, aspect=800 / 600)
        self.camera.local.z = 500
        self.elements: dict[tuple[str, str], gfx.Mesh] = {}
        self.viewport: Viewport | None = None
        self.settings: dict = {}

        self.scene.add(gfx.AmbientLight())
        light = gfx.DirectionalLight()
        light.position = (300, 400, 500)
        self.scene.add(light)

    def show(self) -> None:
        """Cria a viewport gráfica para esta view, se ainda não existir."""
        if self.viewport is not None:
            return
        if not self.elements:
            self._rebuild_scene()
            self.fit()

        from .viewport import Viewport

        self.viewport = Viewport(self)

    def close(self) -> None:
        """Destrói a viewport, preservando a View, a Scene e a Camera."""
        if self.viewport is not None:
            self.viewport.close()
            self.viewport = None

    def set(self, **kwargs) -> None:
        """Placeholder v0. Overrides por view entram em v1+."""
        pass

    def fit(self) -> None:
        """Enquadra a câmera nos elementos. Z-up (padrão IFC)."""
        if not self.elements:
            return
        self.camera.show_object(
            self.scene,
            view_dir=(1, -1, 1),
            up=(0, 0, 1),
        )
        if self.viewport is not None:
            self.viewport.request_draw()

    def _rebuild_scene(self) -> None:
        """Recria todos os meshes a partir da geometria do Project."""
        for mesh in self.elements.values():
            self.scene.remove(mesh)
        self.elements.clear()

        material = gfx.MeshStandardMaterial(color="#cccccc")
        for key, geom in self.project._geometries.items():
            kwargs = dict(positions=geom.positions, indices=geom.indices)
            if geom.normals is not None:
                kwargs["normals"] = geom.normals
            mesh = gfx.Mesh(gfx.Geometry(**kwargs), material)
            self.scene.add(mesh)
            self.elements[key] = mesh

    def _on_model_removed(self, name: str) -> None:
        for key in [k for k in self.elements if k[0] == name]:
            self.scene.remove(self.elements[key])
            del self.elements[key]
        if self.viewport is not None:
            self.viewport.request_draw()
