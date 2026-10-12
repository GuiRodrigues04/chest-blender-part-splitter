"""Run original arithmetic functions with small adapters. This does not run Blender."""
import ast
from collections import Counter
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1] / 'fontes_referencia' / 'src'

class Vector:
    def __init__(self, values):
        self.x, self.y = values[:2]
        self.z = values[2] if len(values) > 2 else 0.0
    def __sub__(self, other):
        return Vector((self.x-other.x, self.y-other.y, self.z-other.z))
    def __add__(self, other):
        return Vector((self.x+other.x, self.y+other.y, self.z+other.z))
    def __mul__(self, number):
        return Vector((self.x*number, self.y*number, self.z*number))
    __rmul__ = __mul__
    def dot(self, other):
        return self.x*other.x+self.y*other.y+self.z*other.z
    @property
    def length_squared(self):
        return self.dot(self)
    def normalized(self):
        length = math.sqrt(self.length_squared)
        return self*(1/length) if length else self

class Matrix:
    def __matmul__(self, value):
        return value

def original_function(file, function):
    tree = ast.parse((ROOT/file).read_text(encoding='utf-8-sig'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
    namespace = {'Vector': Vector, 'Matrix': Matrix, 'List': List, 'Tuple': Tuple}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(ROOT/file), 'exec'), namespace)
    return namespace[function]

triangulate = original_function('geometry_loop.py', 'triangulate_polygon_2d')
results = []
for subdivisions in (1, 3, 5):
    n = subdivisions
    points = [(i/n*.1, 0) for i in range(n)] + [(.1, i/n*.1) for i in range(n)] + [(.1-i/n*.1, .1) for i in range(n)] + [(0, .1-i/n*.1) for i in range(n)]
    triangles = triangulate([Vector(p) for p in points])
    degenerate = []
    for tri in triangles:
        a,b,c = [points[i] for i in tri]
        area = abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2
        if area < 1e-12:
            degenerate.append(tri)
    results.append({'case':'original triangulator', 'boundary_vertices':len(points), 'triangles':len(triangles), 'zero_area_triangles':degenerate})
assert [len(r['zero_area_triangles']) for r in results] == [0, 1, 3]

cut_segments = original_function('gpu_drawing.py', '_compute_cut_line_segments')
def mesh(points):
    return SimpleNamespace(vertices=[SimpleNamespace(co=Vector(p)) for p in points], polygons=[SimpleNamespace(vertices=[0,1,2])])
edge_mesh = mesh([(0,0,0),(1,0,0),(0,1,1)])
edge_segments = cut_segments(edge_mesh, Matrix(), Vector((0,0,0)), Vector((0,0,1)))
assert len(edge_segments) == 0
results.append({'case':'plane coincident with triangle edge', 'segment_points_returned':len(edge_segments), 'note':'two endpoints lie on plane; original function excludes case without opposite signs'})

parser_source = (Path(__file__).resolve().parents[1]/'evidencias'/'Argumentos_Originais.txt')
if parser_source.exists():
    results.append({'case':'external CLI arguments', 'argv_without_separator':['script.py','--blender','custom_blender'], 'effective_argv_original':[], 'note':'original code passes [] whenever literal -- is absent'})

print(json.dumps({'scope':'isolated arithmetic and source analysis; not Blender runtime', 'results':results}, indent=2))
