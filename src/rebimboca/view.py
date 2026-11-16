"""Configuração de visualização: Scene, Camera e meshes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygfx as gfx

if TYPE_CHECKING:
    import ifcopenshell

    from .project import Project
    from .viewport import Viewport


class View:
    """Configuração de visualização, independente da viewport aberta.

    Cada View tem sua própria Scene e Camera. A View sobrevive a
    close(); só a Viewport gráfica é descartada.
    """

    def __init__(self, project: Project, name: str) -> None:
        self.project = project
        self.name = name
        self.scene = gfx.Scene()
        self.camera = gfx.PerspectiveCamera(fov=70, aspect=800 // 600)
        self.camera.local.z = 500

        # arquivo IFC -> GUID -> mesh
        self.elements: dict[ifcopenshell.file, dict[str, gfx.Mesh]] = {}
        self.viewport: Viewport | None = None

        self.scene.add(gfx.AmbientLight())
        light = gfx.DirectionalLight()
        light.local.position = (300, 400, 500)
        self.scene.add(light)

    def show(self) -> None:
        """Cria a viewport gráfica, se ainda não existir."""
        if self.viewport is not None:
            return

        if not self.elements:
            self._rebuild_scene()
            self.fit()

        from .viewport import Viewport

        self.viewport = Viewport(self)

    def close(self) -> None:
        """Fecha a viewport, preservando a View e sua cena."""
        if self.viewport is not None:
            self.viewport.close()
            self.viewport = None

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
        """Recria os meshes a partir das geometrias do Project."""
        for meshes in self.elements.values():
            for mesh in meshes.values():
                self.scene.remove(mesh)
        self.elements.clear()

        material = gfx.MeshStandardMaterial(color="#cccccc")
        for ifc_model, model_data in self.project._models.items():
            if model_data.geometries is None:
                continue

            meshes: dict[str, gfx.Mesh] = {}
            for guid, geom in model_data.geometries.items():
                kwargs = {
                    "positions": geom.positions,
                    "indices": geom.indices,
                }
                if geom.normals is not None:
                    kwargs["normals"] = geom.normals
                mesh = gfx.Mesh(gfx.Geometry(**kwargs), material)
                self.scene.add(mesh)
                meshes[guid] = mesh

            self.elements[ifc_model] = meshes
