"""Script de auditoria de traduções para o Chest Part Splitter."""

import ast
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

sys.path.insert(0, str(ROOT))
from src.translations import TRANSLATIONS_DICT, MESSAGES, HELP_TOPICS

en_keys = {k[1] for k in TRANSLATIONS_DICT.get("en_US", {}).keys()}
pt_keys = {k[1] for k in TRANSLATIONS_DICT.get("pt_BR", {}).keys()}

print(f"Total keys in TRANSLATIONS_DICT['en_US']: {len(en_keys)}")
print(f"Total keys in TRANSLATIONS_DICT['pt_BR']: {len(pt_keys)}")

extracted_strings = set()
f_strings = []
raw_reports = []

class StringVisitor(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename

    def visit_Call(self, node):
        func_name = ""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        # 1. localize_text("...")
        if func_name == "localize_text":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                s = node.args[0].value.strip()
                if s:
                    extracted_strings.add((self.filename, node.lineno, s, "localize_text"))

        # 2. .label(text=...), .prop(..., text=...), .operator(..., text=...)
        if func_name in ("label", "prop", "operator"):
            for kw in node.keywords:
                if kw.arg == "text":
                    if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        s = kw.value.value.strip()
                        if s:
                            extracted_strings.add((self.filename, node.lineno, s, f"layout.{func_name}(text=...)"))
                    elif isinstance(kw.value, ast.JoinedStr):
                        f_strings.append((self.filename, node.lineno, ast.unparse(kw.value), f"layout.{func_name}(text=f...)"))

        # 3. self.report({'LEVEL'}, msg)
        if func_name == "report":
            if len(node.args) >= 2:
                arg = node.args[1]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    s = arg.value.strip()
                    if s:
                        raw_reports.append((self.filename, node.lineno, s, "report(const)"))
                        extracted_strings.add((self.filename, node.lineno, s, "report"))
                elif isinstance(arg, ast.JoinedStr):
                    raw_reports.append((self.filename, node.lineno, ast.unparse(arg), "report(f-string)"))
                elif isinstance(arg, ast.Call) and getattr(arg.func, "id", "") == "localize_text":
                    if arg.args and isinstance(arg.args[0], ast.Constant) and isinstance(arg.args[0].value, str):
                        s = arg.args[0].value.strip()
                        if s:
                            extracted_strings.add((self.filename, node.lineno, s, "report(localize_text)"))

        # 4. Property definitions (EnumProperty, FloatProperty, BoolProperty, etc.)
        if func_name in ("EnumProperty", "FloatProperty", "BoolProperty", "IntProperty", "StringProperty", "FloatVectorProperty"):
            for kw in node.keywords:
                if kw.arg in ("name", "description"):
                    if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                        s = kw.value.value.strip()
                        if s:
                            extracted_strings.add((self.filename, node.lineno, s, f"{func_name}.{kw.arg}"))
                if kw.arg == "items" and isinstance(kw.value, (ast.List, ast.Tuple)):
                    for elt in kw.value.elts:
                        if isinstance(elt, (ast.List, ast.Tuple)):
                            # Item tuple: ('IDENT', "Name", "Description", ...)
                            if len(elt.elts) >= 2 and isinstance(elt.elts[1], ast.Constant) and isinstance(elt.elts[1].value, str):
                                s = elt.elts[1].value.strip()
                                if s:
                                    extracted_strings.add((self.filename, node.lineno, s, f"{func_name}.item.name"))
                            if len(elt.elts) >= 3 and isinstance(elt.elts[2], ast.Constant) and isinstance(elt.elts[2].value, str):
                                s = elt.elts[2].value.strip()
                                if s:
                                    extracted_strings.add((self.filename, node.lineno, s, f"{func_name}.item.desc"))

        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in ("bl_label", "bl_description"):
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    s = node.value.value.strip()
                    if s:
                        extracted_strings.add((self.filename, node.lineno, s, target.id))
        self.generic_visit(node)


target_files = [
    "ui.py",
    "properties.py",
    "operators.py",
    "connector_editor.py",
    "diagnostic.py",
    "io_export.py",
]

for fname in target_files:
    fpath = SRC / fname
    if not fpath.exists():
        continue
    source = fpath.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=fname)
    visitor = StringVisitor(fname)
    visitor.visit(tree)

print(f"\nExtracted {len(extracted_strings)} distinct string usages across codebase.")

# Check strings missing from EN_US
missing_en = []
for fname, lineno, text, origin in sorted(extracted_strings, key=lambda x: (x[0], x[1])):
    # Skip purely numeric, empty, single letters, symbols, or code identifiers
    if not text or len(text) <= 1 or re.match(r"^[\d\.\s\-_/\\:]+$", text):
        continue
    if text not in en_keys:
        missing_en.append((fname, lineno, text, origin))

print(f"\n=== MISSING FROM TRANSLATIONS_DICT['en_US']: {len(missing_en)} ===")
for fname, lineno, text, origin in missing_en[:50]:
    print(f"[{fname}:{lineno}] ({origin}) {repr(text)}")
if len(missing_en) > 50:
    print(f"... and {len(missing_en) - 50} more.")

print(f"\n=== F-STRINGS IN UI (Bypassing translation): {len(f_strings)} ===")
for fname, lineno, code, origin in f_strings:
    print(f"[{fname}:{lineno}] ({origin}) {code}")

print(f"\n=== RAW REPORTS IN OPERATORS / EDITOR: {len(raw_reports)} ===")
for fname, lineno, code, origin in raw_reports[:40]:
    print(f"[{fname}:{lineno}] ({origin}) {code}")
if len(raw_reports) > 40:
    print(f"... and {len(raw_reports) - 40} more.")
