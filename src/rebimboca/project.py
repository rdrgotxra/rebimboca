"""Modelos IFC e seus dados derivados."""

from __future__ import annotations

import multiprocessing
from typing import TYPE_CHECKING

import ifcopenshell
import ifcopenshell.geom
import numpy as np

if TYPE_CHECKING:
    from .view import View


class ModelGeometry:
    """Geometria tessellada de um elemento IFC, em NumPy puro."""

    def __init__(
        self,
        positions: np.ndarray,
        indices: np.ndarray,
        normals: np.ndarray | None = None,
    ) -> None:
        self.positions = positions
        self.indices = indices
        self.normals = normals


class ModelData:
    """Dados derivados de um arquivo IFC."""

    def __init__(self) -> None:
        self.geometries: dict[str, ModelGeometry] | None = None


class Project:
    """Contexto de trabalho sobre modelos ifcopenshell.

    Guarda modelos, extrai geometria e coordena views. Os arquivos IFC
    continuam sendo objetos ifcopenshell.file originais.
    """

    def __init__(self, *ifc_models: ifcopenshell.file) -> None:
        self._models: dict[ifcopenshell.file, ModelData] = {}
        self._views: dict[str, View] = {}
        # self.settings: dict = {}

        for ifc_model in ifc_models:
            self.add_model(ifc_model)

    @property
    def models(self) -> tuple[ifcopenshell.file, ...]:
        """Snapshot dos arquivos IFC registrados, em ordem de inserção."""
        return tuple(self._models)

    def add_model(self, ifc_model: ifcopenshell.file) -> None:
        """Registra um arquivo IFC já aberto.

        A identidade é o arquivo subjacente: o mesmo arquivo não pode ser
        registrado duas vezes, mas duas aberturas do mesmo caminho sim.
        """
        if ifc_model in self._models:
            raise ValueError("modelo IFC já registrado neste projeto")

        self._models[ifc_model] = ModelData()

    def remove_model(self, ifc_model: ifcopenshell.file) -> None:
        """Desregistra o modelo. As views mudam no próximo update()."""
        if ifc_model not in self._models:
            raise ValueError("modelo IFC não registrado neste projeto")

        del self._models[ifc_model]

    @property
    def views(self) -> tuple[View, ...]:
        """Snapshot das views registradas, em ordem de inserção."""
        return tuple(self._views.values())

    def get_view(self, name: str) -> View:
        """Retorna a view registrada com o nome informado."""
        if name not in self._views:
            raise KeyError(
                f"view {name!r} não existe. "
                f"Disponíveis: {tuple(self._views)}"
            )
        return self._views[name]

    def create_view(self, name: str) -> View:
        """Cria e registra uma View. Não exibe; chame view.show().

        O nome é a chave da view e precisa ser único. Renomear exige
        remover o nome antigo antes de criar o novo.
        """
        if name in self._views:
            raise ValueError(
                f"view {name!r} já existe. "
                f"Remova com remove_view({name!r}) antes de recriar."
            )

        from .view import View

        view = View(self, name)
        self._views[name] = view
        return view

    def remove_view(self, name: str) -> None:
        """Fecha a viewport (se aberta) e desregistra a view."""
        if name not in self._views:
            raise KeyError(
                f"view {name!r} não existe. "
                f"Disponíveis: {tuple(self._views)}"
            )

        self._views[name].close()
        del self._views[name]

    def update(self) -> None:
        """Reextrai a geometria e reconstrói as cenas.

        Lê apenas os objetos IFC já em memória. Não reabre arquivos,
        não salva e não reposiciona câmeras.
        """
        for ifc_model, model_data in self._models.items():
            self._extract_geometry(ifc_model, model_data)

        for view in self._views.values():
            view._rebuild_scene()
            if view.viewport is not None:
                view.viewport.request_draw()

    def _extract_geometry(
        self,
        ifc_model: ifcopenshell.file,
        model_data: ModelData,
    ) -> None:
        """Tessela um modelo e troca as geometrias só ao terminar.

        A troca no final evita deixar o modelo com dados parciais se a
        extração falhar no meio.
        """
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)

        iterator = ifcopenshell.geom.iterator(
            settings, ifc_model, multiprocessing.cpu_count()
        )

        geometries: dict[str, ModelGeometry] = {}
        if iterator.initialize():
            while True:
                shape = iterator.get()
                if shape is not None and len(shape.geometry.verts) > 0:
                    verts = np.asarray(
                        shape.geometry.verts, dtype=np.float32
                    ).reshape(-1, 3)
                    indices = np.asarray(
                        shape.geometry.faces, dtype=np.uint32
                    ).reshape(-1, 3)

                    normals = None
                    raw = shape.geometry.normals
                    if raw is not None and len(raw) == len(verts) * 3:
                        normals = np.asarray(
                            raw, dtype=np.float32
                        ).reshape(-1, 3)

                    geometries[shape.guid] = ModelGeometry(
                        positions=verts,
                        indices=indices,
                        normals=normals,
                    )

                if not iterator.next():
                    break

        model_data.geometries = geometries
