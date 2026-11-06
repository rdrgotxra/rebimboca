from __future__ import annotations

import multiprocessing
from dataclasses import dataclass
from pathlib import Path

import ifcopenshell
import ifcopenshell.geom
import numpy as np
import pygfx as gfx
from rendercanvas.auto import RenderCanvas, loop


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

    O name de cada modelo é derivado do filename. Restrição por design:
    identidade documental = identidade de registro. Aliases customizados
    podem ser adicionados em v1+ se a dor for concreta.
    """

    def __init__(self):
        self._models: dict[str, ifcopenshell.file] = {}
        self._geometries: dict[tuple[str, str], GeometryData] = {}
        self._views: dict[str, View] = {}
        self.settings: dict = {}
        self.render_origin: np.ndarray = np.zeros(3, dtype=np.float64)

    # ── Models ────────────────────────────────────────────────────────

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

    # ── Views ─────────────────────────────────────────────────────────

    @property
    def view_names(self) -> tuple[str, ...]:
        """Snapshot dos names de views registradas, em ordem de inserção."""
        return tuple(self._views)

    def add_view(self, name: str) -> View:
        """Cria e registra uma View. Não exibe; chame view.show()."""
        if name in self._views:
            raise ValueError(f"view {name!r} já existe")
        v = View(self)
        self._views[name] = v
        return v

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

    # ── Atualização ───────────────────────────────────────────────────

    def update(self) -> None:
        """Reextrai geometria de todos os modelos e reconstrói todas as views.

        Use após mutar modelos via ifcopenshell. Não relê arquivos do
        disco. Não reposiciona câmeras — o enquadramento do usuário é
        preservado; chame view.fit() para reenquadrar.

        v0: custo total (re-tessela tudo, recria todos os meshes).
        v1+: diff por GUID, update_range por buffer, update(models=[...]).
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
        """Re-tessela um modelo via geometry iterator.

        Iterator (não create_shape em loop): cache interno, multicore,
        5-10x mais rápido em modelos inteiros. Término: `next()` retorna
        False. `get()` retornar None é estado transitório de um elemento
        que falhou, não sinal de fim.

        Swap atômico: se a extração falhar no meio, a geometria anterior
        é preservada.
        """
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
                    # render_origin preserva precisão em float32 para
                    # modelos em coordenadas UTM (v1+). Em v0 é (0,0,0).
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


class View:
    """Configuração de visualização: Scene, Camera, índice de meshes.

    Sobrevive a close(). A Viewport (canvas + renderer + controller) é
    descartável. Lê project._geometries (intra-pacote) para construir a
    cena; não tesselа.

    Scene por View: isolamento de estado visual por view. Meshes são
    duplicados (objetos leves); buffers GPU são compartilhados pelo cache
    do dispositivo no pygfx.
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
        """Materializa a View numa Viewport.

        Abre com o estado atual de project._geometries. Chame
        project.update() antes se houver mutações ou modelos não extraídos.
        Idempotente: show() com viewport aberta retorna imediatamente.
        """
        if self.viewport is not None:
            return
        if not self.elements:
            self._rebuild_scene()
            self.fit()
        self.viewport = Viewport(self)

    def close(self) -> None:
        """Destrói o Viewport. A View (Scene, Camera, elements) persiste."""
        if self.viewport is not None:
            self.viewport.close()
            self.viewport = None

    def set(self, **kwargs) -> None:
        """Placeholder v0. Overrides por view (material, visibilidade) v1+."""
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
        """Recria todos os gfx.Mesh a partir de project._geometries."""
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


class Viewport:
    """Infraestrutura gráfica: canvas, renderer, controller."""

    def __init__(self, view: View):
        self.view = view
        self.canvas = RenderCanvas(size=(800, 600))
        self.renderer = gfx.WgpuRenderer(self.canvas)
        # register_events conecta mouse/teclado ao renderer. Sem isso,
        # a câmera fica estática.
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


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("uso: python main.py caminho/para/arquivo.ifc")
        sys.exit(1)

    project = Project()
    project.add_model(sys.argv[1])
    project.update()

    view = project.add_view("main")
    view.show()

    loop.run()
