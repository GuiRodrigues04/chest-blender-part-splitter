"""Python padrão: python auditar_textos.py CAMINHO_ADDON SAIDA.csv
Inventário de candidatos; não prova idioma renderizado e não altera o addon.
"""
import ast
import csv
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("Uso: auditar_textos.py DIRETORIO_ADDON SAIDA.csv")
root = Path(sys.argv[1]).resolve()
rows = []
def source(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "{param}"
                       for v in node.values)
    return ""

for path in sorted(root.rglob("*.py")):
    if "translations" in path.stem:
        continue
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("bl_label", "bl_description"):
                    value = source(node.value)
                    if value:
                        rows.append((str(path.relative_to(root)), node.lineno,
                                     target.id, value))
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else (
                node.func.id if isinstance(node.func, ast.Name) else "")
            for kw in node.keywords:
                if kw.arg in ("text", "name", "description", "heading"):
                    value = source(kw.value)
                    if value:
                        rows.append((str(path.relative_to(root)), node.lineno,
                                     name + "." + kw.arg, value))
            if name in ("report", "ValueError", "RuntimeError", "ConnectorValidationError",
                        "SolidSliceError", "PlaneSliceError"):
                for arg in node.args:
                    value = source(arg)
                    if value:
                        rows.append((str(path.relative_to(root)), node.lineno, name, value))
        if isinstance(node, ast.Tuple) and len(node.elts) == 3:
            a, label, tip = node.elts
            if (isinstance(a, ast.Constant) and isinstance(a.value, str)
                    and a.value and a.value.upper() == a.value
                    and "_" not in source(label)[:1]):
                for kind, value in [("enum.label", source(label)), ("enum.description", source(tip))]:
                    if value:
                        rows.append((str(path.relative_to(root)), node.lineno, kind, value))

rows = sorted(set(rows))
out = Path(sys.argv[2])
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["arquivo", "linha", "origem", "texto_candidato", "chave_destino", "revisao"])
    for row in rows:
        writer.writerow([*row, "", "PENDENTE"])
print("Candidatos:", len(rows), "Arquivo:", out)
