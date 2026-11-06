from __future__ import annotations

import multiprocessing
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import ifcopenshell
import ifcopenshell.geom
import numpy as np

if TYPE_CHECKING:
    from .view import View


@dataclass
class GeometryData:
    """Geometria extraída de um elemento IFC. NumPy puro, GPU-agnóstica."""

    positions: np.ndarray               # (N, 3) float32
    indices: np.ndarray                 # (M, 3) uint32
    normals: np.ndarray | None = None   # (N, 3) float32
    material_name: str | None = None    # reservado v1+


class Project:
    """Contexto de trabalho sobre modelos IFC.

    Registra modelos, extrai geometria e coordena views. Sem Scene, sem
    GPU — pode existir headless (análise, CI, clash detection).

    O name de cada modelo é derivado de Path(path).stem. A identidade
    documental é a identidade de registro.
    """

    def __init__(self):
        self._models: dict[str, ifcopenshell.file] = {}
        self._geometries: dict[tuple[str, str], GeometryData] = {}
        self._views: dict[str, View] = {}
        self.settings: dict = {}
        self.render_origin: np.ndarray = np.zeros(3, dtype=np.float64)

    @property
    def model_names(self) -> tuple[str, ...]:
        """Snapshot dos names de modelos registrados, em ordem de inserção."""
        return tuple(self._models)

    def add_model(self, path: str) -> ifcopenshell.file:
        """Abre um IFC e registra no projeto. Retorna o ifcopenshell.file cru.

        O name é derivado de Path(path).stem. Não extrai geometria;
        chame update() para isso.
        """
        name = Path(path).stem
        if name in self._models:
            raise ValueError(
                f"modelo {name!r} já registrado (filename colide). "
                f"Renomeie o arquivo ou remova com remove_model({name!r})."
            )
        model = ifcopenshell.open(path)
        self._models[name] = model
        return model

    def get_model(self, name: str) -> ifcopenshell.file:
        if name not in self._models:
            raise KeyError(
                f"modelo {name!r} não registrado. "
                f"Disponíveis: {self.model_names}"
            )
        return self._models[name]

    def remove_model(self, name: str) -> None:
        """Desregistra o modelo, suas geometrias e remove das views.

        Não destrói o ifcopenshell.file — apenas o remove do projeto.
        """
        if name not in self._models:
            raise KeyError(
                f"modelo {name!r} não registrado. "
                f"Disponíveis: {self.model_names}"
            )
        del self._models[name]
        for key in [k for k in self._geometries if k[0] == name]:
            del self._geometries[key]
        for view in self._views.values():
            view._on_model_removed(name)

    @property
    def view_names(self) -> tuple[str, ...]:
        """Snapshot dos names de views registradas, em ordem de inserção."""
        return tuple(self._views)

    def add_view(self, name: str) -> View:
        """Cria e registra uma View. Não exibe; chame view.show()."""
        if name in self._views:
            raise ValueError(f"view {name!r} já existe")
        from .view import View

        view = View(self)
        self._views[name] = view
        return view

    def get_view(self, name: str) -> View:
        if name not in self._views:
            raise KeyError(
                f"view {name!r} não existe. "
                f"Disponíveis: {self.view_names}"
            )
        return self._views[name]

    def remove_view(self, name: str) -> None:
        """Fecha o viewport (se aberto) e desregistra a view."""
        if name not in self._views:
            raise KeyError(
                f"view {name!r} não existe. "
                f"Disponíveis: {self.view_names}"
            )
        self._views[name].close()
        del self._views[name]

    def update(self) -> None:
        """Reextrai geometria de todos os modelos e reconstrói todas as views.

        Use após mutar modelos via ifcopenshell. Não relê arquivos do
        disco. Não reposiciona câmeras — o enquadramento do usuário é
        preservado; chame view.fit() para reenquadrar.
        """
        for name in list(self._models):
            self._extract_geometry(name)
        for view in self._views.values():
            view._rebuild_scene()
            if view.viewport is not None:
                view.viewport.request_draw()

    def set(self, **kwargs) -> None:
        """Placeholder v0. Configurações globais entram em v1+."""
        pass

    def _extract_geometry(self, name: str) -> None:
        """Re-tessela um modelo via geometry iterator com swap atômico."""
        model = self._models[name]
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)

        iterator = ifcopenshell.geom.iterator(
            settings, model, multiprocessing.cpu_count()
        )

        new_geoms: dict[tuple[str, str], GeometryData] = {}
        if iterator.initialize():
            while True:
                shape = iterator.get()
                if shape is not None and len(shape.geometry.verts) > 0:
                    verts = np.asarray(
                        shape.geometry.verts, dtype=np.float64
                    ).reshape(-1, 3)
                    positions = (verts - self.render_origin).astype(np.float32)
                    indices = np.asarray(
                        shape.geometry.faces, dtype=np.uint32
                    ).reshape(-1, 3)

                    normals = None
                    raw = shape.geometry.normals
                    if raw is not None and len(raw) == len(verts) * 3:
                        normals = np.asarray(raw, dtype=np.float32).reshape(-1, 3)

                    new_geoms[(name, shape.guid)] = GeometryData(
                        positions=positions,
                        indices=indices,
                        normals=normals,
                    )
                if not iterator.next():
                    break

        for key in [k for k in self._geometries if k[0] == name]:
            del self._geometries[key]
        self._geometries.update(new_geoms)
