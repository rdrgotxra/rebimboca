# rebimboca

Biblioteca Python experimental para explorar modelos IFC com código e uma viewport 3D. O `ifcopenshell` continua sendo a API para consultar e modificar os modelos; a rebimboca coordena modelos, geometria e views.

## Status

**v0 em desenvolvimento.** A API ainda pode mudar. A viewport básica está disponível; recursos como materiais IFC, seleção interativa e atualização incremental ainda não estão implementados.

## API pública

- `Project`: registra modelos IFC, extrai geometria com `update()` e coordena views.
- `View`: representa uma visualização; `show()` abre a viewport, `close()` a fecha e `fit()` reenquadra a câmera.
- `Viewport`: infraestrutura gráfica criada por `View.show()`.
- `ModelGeometry`: geometria extraída de um elemento IFC, em arrays NumPy.

`Project.add_model(arch)` recebe um `ifcopenshell.file` já aberto. O modelo é identificado pelo próprio arquivo. `Project.models` retorna uma tupla com os arquivos registrados.

As views são identificadas por nome e criadas depois, para que o usuário as guarde em variáveis:

```python
view = project.create_view("perspective")
section = project.create_view("section")
```

`create_view(name)` exige um nome único e não exibe a view. `get_view(name)` retorna uma view já registrada, e `remove_view(name)` desregistra pelo nome. Nomes são chaves: para renomear, remova o nome antigo antes de criar o novo.

`update()` é o único ponto de sincronização: alterações nos arquivos IFC ou a remoção de modelos só aparecem nas views depois de chamar `project.update()`.

## Exemplo mínimo

```python
import ifcopenshell
import rebimboca

arch = ifcopenshell.open("modelo.ifc")

project = rebimboca.Project(arch)
project.update()

# O modelo continua sendo um ifcopenshell.file comum.
print(arch.by_type("IfcWall"))

view = project.create_view("principal")
view.show()
```

Execute o exemplo em um ambiente com a rebimboca e suas dependências instaladas. Em Jupyter, exiba `view.viewport.canvas` como última expressão da célula.
