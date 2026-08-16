# -*- coding: utf-8 -*-
#! ironpython3

"""Classifica elementos por ambiente."""

from Autodesk.Revit.DB import (
    XYZ,
    BuiltInCategory,
    BuiltInParameter,
    FilteredElementCollector,
    Transaction,
)

doc = __revit__.ActiveUIDocument.Document


def get_elementos(doc, categorias):
    elementos = {}
    for nome_categoria, ref_categoria in categorias.items():
        elementos[nome_categoria] = (
            FilteredElementCollector(doc)
            .OfCategory(ref_categoria)
            .WhereElementIsNotElementType()
            .ToElements()
        )
    return elementos


def get_fase(elemento, doc):
    fase_id = elemento.get_Parameter(BuiltInParameter.PHASE_CREATED).AsElementId()
    return doc.GetElement(fase_id)


def get_ambiente(ponto, fase, doc):
    return doc.GetRoomAtPoint(ponto, fase)


def get_nivel_ambiente(ambiente):
    return ambiente.Level.Name


def get_nome_ambiente(ambiente):
    nome_ambiente = ambiente.get_Parameter(BuiltInParameter.ROOM_NAME)
    if nome_ambiente and nome_ambiente.HasValue:
        return nome_ambiente.AsString()
    return "AMBIENTE SEM NOME"


def set_ambiente(elemento, nome):
    param = elemento.LookupParameter("Ambiente")  # implementar parâmetro compartilhado!
    if param and not param.IsReadOnly:
        param.Set(nome)
        return True
    return False


def get_ponto_outros(elemento):
    bbox = elemento.get_BoundingBox(None)
    if bbox is None:
        return None

    return (bbox.Min + bbox.Max) * 0.5


def get_ponto_piso_forro(piso):
    pass


def get_ponto_parede(parede):
    try:
        offset = 0.003 + parede.Width / 2.0
        loc = parede.Location
        curva = loc.Curve
        orientacao = parede.Orientation

    except Exception:
        return None

    tangente = curva.ComputeDerivatives(0.5, True).BasisX.Normalize()
    local_normal = XYZ(-tangente.Y, tangente.X, 0.0)

    if local_normal.DotProduct(orientacao) < 0:
        local_normal = XYZ(-local_normal.X, -local_normal.Y, 0.0)

    ponto = curva.Evaluate(0.5, True)
    ponto += local_normal.Multiply(offset)

    bbox = parede.get_BoundingBox(None)
    z_mid = (bbox.Min.Z + bbox.Max.Z) / 2.0

    return XYZ(ponto.X, ponto.Y, z_mid)


def main(doc):
    categorias = {
        "parede": BuiltInCategory.OST_Walls,
        "piso": BuiltInCategory.OST_Floors,
        "forro": BuiltInCategory.OST_Ceilings,
        "peca_hid": BuiltInCategory.OST_PlumbingFixtures,
        "mobiliario": BuiltInCategory.OST_Furniture,
    }

    funcao_get_ponto = {
        "parede": get_ponto_parede,
        "piso": get_ponto_piso_forro,
        "forro": get_ponto_piso_forro,
        "peca_hid": get_ponto_outros,
        "mobiliario": get_ponto_outros,
    }

    elementos = get_elementos(doc, categorias)
    alteracoes = []

    for categoria, elementos_categoria in elementos.items():
        get_ponto = funcao_get_ponto[categoria]

        for elemento in elementos_categoria:
            ponto = get_ponto(elemento)
            if ponto is None:
                continue

            fase = get_fase(elemento, doc)
            if fase is None:
                continue

            ambiente = get_ambiente(ponto, fase, doc)
            if ambiente is None:
                continue

            nivel_ambiente = get_nivel_ambiente(ambiente)
            nome_ambiente = get_nome_ambiente(ambiente)
            ambiente_completo = "{} - {}".format(
                nivel_ambiente,
                nome_ambiente,
            )

            alteracoes.append((elemento, ambiente_completo))

    t = Transaction(doc, "Classificar por ambiente")
    t.Start()

    try:
        for elemento, ambiente_completo in alteracoes:
            set_ambiente(elemento, ambiente_completo)

        t.Commit()

    except Exception as ex:
        t.RollBack()
        print("Erro durante o processamento: {}".format(str(ex)))
        raise


if __name__ == "__main__":
    main(doc)
