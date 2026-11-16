"""Teste manual da API da rebimboca.

Execute a partir da raiz do repositório:
    poetry run python script.py

As verificações destrutivas rodam em projetos separados, para que a
janela final abra já com o modelo carregado.
"""

import sys

import ifcopenshell

import rebimboca

IFC_PATH = "/home/rdrgotxra/Documents/AC20-FZK-Haus.ifc"


def check(condition: bool, message: str) -> None:
    """Falha cedo quando uma verificação simples não é atendida."""
    if not condition:
        raise AssertionError(message)
    print(f"OK: {message}")


# 1. O import básico não deve carregar o backend gráfico.
check(
    "rendercanvas.auto" not in sys.modules,
    "import não carrega rendercanvas",
)

# 2. Project pode ser criado vazio ou já com modelos.
arch = ifcopenshell.open(IFC_PATH)

check(rebimboca.Project().models == (), "Project vazio começa sem modelos")
check(
    rebimboca.Project(arch).models == (arch,),
    "Project aceita modelo no construtor",
)

# 3. O mesmo arquivo não pode ser registrado duas vezes.
try:
    rebimboca.Project(arch, arch)
except ValueError as exc:
    print(f"OK: duplicata de modelo rejeitada: {exc}")
else:
    raise AssertionError("duplicata deveria gerar ValueError")

# 4. Views são criadas depois e guardadas em variáveis.
project = rebimboca.Project(arch)
view = project.create_view("perspective")
check(project.views == (view,), "views são registradas em ordem")
check(view.name == "perspective", "a view guarda o nome informado")

# 5. Nomes de view são únicos.
try:
    project.create_view("perspective")
except ValueError as exc:
    print(f"OK: duplicata de view rejeitada: {exc}")
else:
    raise AssertionError("duplicata deveria gerar ValueError")

section = project.create_view("section")
check(project.views == (view, section), "create_view registra nova view")
check(project.get_view("section") is section, "get_view devolve a view")

# 6. update() extrai a geometria do objeto IFC em memória.
project.update()
model_data = project._models[arch]
geometry_count = len(model_data.geometries or {})
check(geometry_count > 0, f"update() extraiu {geometry_count} geometrias")

# 7. Remover a view desregistra o nome.
project.remove_view("section")
check(project.views == (view,), "remove_view remove pelo nome")

# 8. Remoção de modelo é testada em um projeto separado, sem viewport.
other = rebimboca.Project(arch)
other.update()
other.remove_model(arch)
check(other.models == (), "remove_model desregistra o modelo")

# 9. Mostrar a viewport com o modelo presente.
view.show()
check("rendercanvas.auto" in sys.modules, "show() carrega o backend gráfico")
model_meshes = view.elements.get(arch, {})
check(len(model_meshes) == geometry_count, "a cena contém todos os meshes")

# O estado atual ainda exige manter o loop gráfico ativo.
from rendercanvas.auto import loop

loop.run()
