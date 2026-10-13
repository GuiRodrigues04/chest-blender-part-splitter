"""Python padrão: python identificar_fontes.py CAMINHO_DO_ADDON
Somente leitura. Produz JSON no stdout; funciona sem Blender.
"""
import sys
import ast
import json
import hashlib
from pathlib import Path

root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
if root is None or not root.is_dir():
    raise SystemExit("Informe o diretório extraído do addon.")
report = {"root": str(root), "files": [], "syntax_errors": []}
for p in sorted(root.rglob("*")):
    if not p.is_file() or p.suffix not in (".py", ".toml"):
        continue
    data = p.read_bytes()
    item = {"path": str(p.relative_to(root)),
            "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    if p.suffix == ".py":
        try:
            ast.parse(data.decode("utf-8-sig"), filename=str(p))
        except (SyntaxError, UnicodeError) as exc:
            report["syntax_errors"].append({"path": item["path"], "error": str(exc)})
    report["files"].append(item)
manifest = root / "blender_manifest.toml"
report["manifest_text"] = manifest.read_text() if manifest.exists() else None
print(json.dumps(report, indent=2, ensure_ascii=False))
