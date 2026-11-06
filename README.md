# rebimboca

Biblioteca Python experimental para explorar modelos IFC com código e uma viewport 3D. O `ifcopenshell` continua sendo a API para consultar e modificar os modelos; a rebimboca coordena modelos, geometria e views.

## Status

**v0 em desenvolvimento.** A API ainda pode mudar. A viewport básica está disponível; recursos como materiais IFC, seleção interativa e atualização incremental ainda não estão implementados.

## API pública

- `Project`: registra modelos IFC, extrai geometria com `update()` e coordena views.
- `View`: representa uma visualização; `show()` abre a viewport, `close()` a fecha e `fit()` reenquadra a câmera.
- `Viewport`: infraestrutura gráfica criada por `View.show()`.
- `GeometryData`: dados de geometria em arrays NumPy.

`Project.add_model(path)` retorna o `ifcopenshell.file` original. O nome registrado é derivado do nome do arquivo, sem extensão. Acesse o modelo diretamente com a API do IfcOpenShell.

## Exemplo mínimo

```python
import rebimboca
from rendercanvas.auto import loop

project = rebimboca.Project()
model = project.add_model("modelo.ifc")
project.update()

# O modelo continua sendo um ifcopenshell.file comum.
print(model.by_type("IfcWall"))

view = project.add_view("principal")
view.show()
loop.run()
```

Execute o exemplo em um ambiente com a rebimboca e suas dependências instaladas. Em Jupyter, exiba `view.viewport.canvas` como última expressão da célula, em vez de iniciar `loop.run()`.
