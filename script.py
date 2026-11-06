# playground/visualizar_ifc.py

from rebimboca import Project
from rendercanvas.auto import loop


ifc_path = "/home/rdrgotxra/Documents/AC20-FZK-Haus.ifc"

project = Project()
project.add_model(ifc_path)
project.update()

view = project.add_view("principal")
view.show()

loop.run()
