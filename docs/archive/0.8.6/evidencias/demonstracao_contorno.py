"""Demonstração isolada da representação incorreta do perímetro.

Uso: python demonstracao_contorno.py /caminho/do/repositorio
Não exige Blender. Extrai a função original por AST, sem importar o addon.
Não substitui reprodução no Blender nem é teste de aprovação da correção.
"""
import ast
import json
from pathlib import Path
import sys
from typing import List, Tuple

root = Path(sys.argv[1]) if len(sys.argv) > 1 else None
if root is None:
    raise SystemExit("Informe a raiz do addon, que contém src/geometry_connectors.py.")
source = root / "src" / "geometry_connectors.py"
tree = ast.parse(source.read_text(encoding="utf-8-sig"))
function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == "point_in_polygon_2d")
namespace = {"List": List, "Tuple": Tuple}
exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
inside = namespace[function.name]
rectangle = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
edge_endpoints = [(-1, -1), (1, -1), (1, -1), (1, 1),
                  (-1, 1), (1, 1), (-1, -1), (-1, 1)]
points = [(0, 0), (-0.55, 0), (0.55, 0)]
result = {
    "points_center_left_right": points,
    "ordered_rectangle": [inside(x, y, rectangle) for x, y in points],
    "unordered_edge_endpoints": [inside(x, y, edge_endpoints) for x, y in points],
    "note": "Falso negativo causado pela representação, não pela posição real do ponto."
}
print(json.dumps(result, indent=2, ensure_ascii=False))
