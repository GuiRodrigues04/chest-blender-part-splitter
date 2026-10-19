"""Comprehensive linguistic and translation audit script using Blender RNA reflection."""
import sys
import os
import re

sys.path.insert(0, os.path.abspath("."))
import bpy
import src
src.register()

from src.translations import TRANSLATIONS_DICT, HELP_TOPICS, MESSAGES, get_addon_locale, localize_text

print("==================================================")
print("     STARTING COMPREHENSIVE LINGUISTIC AUDIT     ")
print("==================================================")

# 1. CATALOG SYMMETRY AND COMPLETENESS
en_dict = TRANSLATIONS_DICT.get('en_US', {})
pt_dict = TRANSLATIONS_DICT.get('pt_BR', {})

en_keys = set(k[1] for k in en_dict.keys())
pt_keys = set(k[1] for k in pt_dict.keys())

missing_in_en = pt_keys - en_keys
missing_in_pt = en_keys - pt_keys

print(f"\n1. Catalog Symmetry:")
print(f"   Total en_US entries: {len(en_dict)}")
print(f"   Total pt_BR entries: {len(pt_dict)}")
print(f"   Keys in pt_BR but missing in en_US: {len(missing_in_en)}")
for k in sorted(missing_in_en):
    print(f"     [Missing in en_US] '{k}'")
print(f"   Keys in en_US but missing in pt_BR: {len(missing_in_pt)}")
for k in sorted(missing_in_pt):
    print(f"     [Missing in pt_BR] '{k}'")

# Check for empty values
for (ctx, k), v in en_dict.items():
    if not v or not v.strip():
        print(f"     [Empty value in en_US] key: '{k}'")
for (ctx, k), v in pt_dict.items():
    if not v or not v.strip():
        print(f"     [Empty value in pt_BR] key: '{k}'")

# 2. AUDIT REPORT_MSG CALLS IN SOURCE FILES
print(f"\n2. Auditing report_msg calls in Python source files:")
report_pattern = re.compile(r'report_msg\(\s*(["\'](?:\\.|[^"\'])*["\']|f["\'](?:\\.|[^"\'])*["\'])\s*,\s*(["\'](?:\\.|[^"\'])*["\']|f["\'](?:\\.|[^"\'])*["\'])\s*\)', re.DOTALL)

py_files = [os.path.join("src", f) for f in os.listdir("src") if f.endswith(".py")]
report_calls = []

for pf in py_files:
    with open(pf, "r", encoding="utf-8") as f:
        content = f.read()
    for match in report_pattern.finditer(content):
        pt_arg = match.group(1).strip()
        en_arg = match.group(2).strip()
        report_calls.append((pf, pt_arg, en_arg))

print(f"   Found {len(report_calls)} report_msg calls.")

PT_WORDS = {
    "corte", "cortador", "peça", "peças", "encaixe", "encaixes", "alvo",
    "limpar", "inverter", "folga", "aviso", "padrão", "profundidade",
    "largura", "altura", "espessura", "reverter", "divisão", "dividir",
    "aresta", "arestas", "contorno", "selecionado", "selecionada", "focar",
    "ajuste", "remover", "macho", "fêmea", "remanescente", "sucesso",
    "não", "é", "está", "estão", "para", "quina", "ortogonal", "gerado",
    "gerada", "fechado", "fechada", "aberta", "abertas", "nulo", "nula",
    "inválido", "inválida", "modelo", "malha"
}

EN_WORDS = {
    "target", "cutter", "split", "splitter", "part", "parts", "connector",
    "connectors", "clearance", "warning", "preview", "revert", "mesh",
    "depth", "width", "height", "thickness", "edge", "edges", "boundary",
    "selected", "focus", "receiver", "male", "female", "success", "successfully",
    "invalid", "closed", "open", "failed", "failure"
}

issues_in_reports = []
for file_path, pt, en in report_calls:
    en_clean = re.sub(r'\{[^}]*\}', '', en.lower())
    tokens_en = set(re.findall(r'[a-záàâãéèêíïóôõöúçñ]+', en_clean))
    pt_leaks = tokens_en.intersection(PT_WORDS)
    if pt_leaks:
        issues_in_reports.append((file_path, "PT leak in English report", en, pt_leaks))

    pt_clean = re.sub(r'\{[^}]*\}', '', pt.lower())
    tokens_pt = set(re.findall(r'[a-z]+', pt_clean))
    en_leaks = tokens_pt.intersection(EN_WORDS)
    if en_leaks:
        issues_in_reports.append((file_path, "EN leak in Portuguese report", pt, en_leaks))

print(f"   Issues in report_msg calls: {len(issues_in_reports)}")
for path, kind, text, words in issues_in_reports:
    print(f"     [{kind}] ({path}): {words} in: {text[:70]}...")

# 3. RNA REFLECTION AUDIT (Properties, Operators, Enum Items)
print(f"\n3. Auditing Properties & Operators via Blender RNA reflection:")

# Check ChestSplitterSettings
settings_rna = src.properties.ChestSplitterSettings.bl_rna
rna_strings_to_check = []

for prop in settings_rna.properties:
    if prop.identifier in ('rna_type', 'name'):
        continue
    if prop.name:
        rna_strings_to_check.append(("Setting Prop Name", prop.identifier, prop.name))
    if prop.description:
        rna_strings_to_check.append(("Setting Prop Desc", prop.identifier, prop.description))
    if prop.type == 'ENUM':
        for item in prop.enum_items:
            if item.name:
                rna_strings_to_check.append(("Setting Enum Item Name", f"{prop.identifier}.{item.identifier}", item.name))
            if item.description:
                rna_strings_to_check.append(("Setting Enum Item Desc", f"{prop.identifier}.{item.identifier}", item.description))

# Check Operators
for cls_name in dir(bpy.types):
    if cls_name.startswith("CHEST_OT_splitter_"):
        cls = getattr(bpy.types, cls_name)
        rna = getattr(cls, "bl_rna", None)
        if not rna:
            continue
        if rna.name:
            rna_strings_to_check.append(("Operator Name", cls_name, rna.name))
        if rna.description:
            rna_strings_to_check.append(("Operator Desc", cls_name, rna.description))
        for prop in rna.properties:
            if prop.identifier in ('rna_type', 'name'):
                continue
            if prop.name:
                rna_strings_to_check.append(("Op Prop Name", f"{cls_name}.{prop.identifier}", prop.name))
            if prop.description:
                rna_strings_to_check.append(("Op Prop Desc", f"{cls_name}.{prop.identifier}", prop.description))
            if prop.type == 'ENUM':
                for item in prop.enum_items:
                    if item.name:
                        rna_strings_to_check.append(("Op Enum Item Name", f"{cls_name}.{prop.identifier}.{item.identifier}", item.name))
                    if item.description:
                        rna_strings_to_check.append(("Op Enum Item Desc", f"{cls_name}.{prop.identifier}.{item.identifier}", item.description))

print(f"   Collected {len(rna_strings_to_check)} RNA strings.")

rna_missing_trans = []
for category, ident, text in rna_strings_to_check:
    if not text or not text.strip():
        continue
    # Check if this string has an entry in en_US and pt_BR
    en_val = en_dict.get(('*', text))
    pt_val = pt_dict.get(('*', text))
    if not en_val:
        rna_missing_trans.append((category, ident, "Missing en_US", text))
    if not pt_val:
        rna_missing_trans.append((category, ident, "Missing pt_BR", text))

print(f"   Untranslated RNA strings: {len(rna_missing_trans)}")
for cat, ident, miss, text in rna_missing_trans[:30]:
    print(f"     [{miss}] {cat} ({ident}): '{text}'")

# 4. AUDIT HELP_TOPICS
print(f"\n4. Auditing HELP_TOPICS:")
help_issues = []
for topic, data in HELP_TOPICS.items():
    title = data.get("title", {})
    tooltip = data.get("tooltip", {})
    popups = data.get("popup_lines", {})
    
    for loc in ('pt_BR', 'en_US'):
        t = title.get(loc, "")
        if not t:
            help_issues.append(f"Topic '{topic}' missing title in {loc}")
        tt = tooltip.get(loc, "")
        if not tt:
            help_issues.append(f"Topic '{topic}' missing tooltip in {loc}")
        p = popups.get(loc, [])
        if not p:
            help_issues.append(f"Topic '{topic}' missing popup_lines in {loc}")
        # Check leakage
        if loc == 'en_US':
            words = set(w.lower().strip(".,:()[]{}'\"-!?") for w in (t + " " + tt + " " + " ".join(p)).split())
            leaks = words.intersection(PT_WORDS)
            if leaks:
                help_issues.append(f"Topic '{topic}' en_US contains PT words: {leaks}")
        elif loc == 'pt_BR':
            words = set(w.lower().strip(".,:()[]{}'\"-!?") for w in (t + " " + tt + " " + " ".join(p)).split())
            leaks = words.intersection(EN_WORDS)
            if leaks:
                help_issues.append(f"Topic '{topic}' pt_BR contains EN words: {leaks}")

print(f"   Help topic issues: {len(help_issues)}")
for hi in help_issues:
    print(f"     {hi}")

# 5. DYNAMIC UI RENDERING IN ALL 4 MODES & MULTIPLE STATES
print(f"\n5. Dynamic UI rendering in ALL 4 MODES & MULTIPLE STATES:")
from src.ui import VIEW3D_PT_chest_part_splitter

scene = bpy.context.scene
settings = scene.chest_splitter

mesh = bpy.data.meshes.new("AuditMesh")
obj = bpy.data.objects.new("AuditTarget", mesh)
scene.collection.objects.link(obj)
settings.target_object = obj

class MockAuditLayout:
    def __init__(self, locale_name):
        self.locale_name = locale_name
        self.collected = []
        self.alert = False
        self.scale_y = 1.0
        self.enabled = True
        
    def label(self, text="", icon='NONE', icon_value=0):
        if text:
            self.collected.append(text)
            
    def operator(self, operator, text="", icon='NONE', emboss=True):
        if text:
            self.collected.append(text)
        return type("MockOp", (), {})()
        
    def prop(self, data, property, text="", icon='NONE', expand=False, slider=False, toggle=False):
        if text:
            self.collected.append(text)
            
    def row(self, align=False):
        return self
        
    def column(self, align=False):
        return self
        
    def box(self):
        return self
        
    def split(self, factor=0.0, align=False):
        return self
        
    def separator(self, factor=1.0):
        pass

    def prop_search(self, data, property, search_data, search_property, text="", text_ctxt="", icon='NONE'):
        if text:
            self.collected.append(text)

    def __getattr__(self, name):
        def dummy(*args, **kwargs):
            if 'text' in kwargs and kwargs['text']:
                self.collected.append(kwargs['text'])
            return self
        return dummy

panel = type("DummyPanel", (), {"layout": None, "draw": VIEW3D_PT_chest_part_splitter.draw})()

for test_loc in ['en_US', 'pt_BR']:
    pref = src.translations.get_addon_preferences(bpy.context)
    if pref:
        pref.language = 'EN_US' if test_loc == 'en_US' else 'PT_BR'
    bpy.context.preferences.view.language = test_loc
    
    mock = MockAuditLayout(test_loc)
    panel.layout = mock
    
    # Test ALL 4 split modes: PLANE, LOOP, SOLID, MATERIAL
    for mode in ['PLANE', 'LOOP', 'SOLID', 'MATERIAL']:
        settings.split_mode = mode
        # Test various solid sources
        for sol_src in ['PRIMITIVE', 'EXISTING']:
            settings.solid_source = sol_src
            for status in ['EMPTY', 'CONFIGURED', 'PREVIEW_VALID', 'PREVIEW_STALE', 'PREVIEW_INVALID', 'COMMITTED']:
                settings.session_status = status
                panel.draw(bpy.context)

    print(f"   Collected {len(mock.collected)} UI strings rendered in '{test_loc}'.")
    
    if test_loc == 'en_US':
        leaks = []
        for s in mock.collected:
            words = set(w.lower().strip(".,:()[]{}'\"-!?") for w in s.split())
            hit = words.intersection(PT_WORDS)
            if hit:
                leaks.append((s, hit))
        print(f"   Portuguese leaks in en_US UI: {len(leaks)}")
        for s, hit in leaks[:10]:
            print(f"     [Leak in en_US] '{s}' (words: {hit})")
            
    elif test_loc == 'pt_BR':
        leaks = []
        for s in mock.collected:
            words = set(w.lower().strip(".,:()[]{}'\"-!?") for w in s.split())
            hit = words.intersection(EN_WORDS)
            if hit:
                leaks.append((s, hit))
        print(f"   English leaks in pt_BR UI: {len(leaks)}")
        for s, hit in leaks[:10]:
            print(f"     [Leak in pt_BR] '{s}' (words: {hit})")

print("\n==================================================")
print("     AUDIT FINISHED     ")
print("==================================================")
