"""Constantes e definições padrão para o Chest Part Splitter."""

# Coleções de organização no Blender
COLLECTION_GUIDES_NAME = "CHEST_SPLITTER_GUIDES"
COLLECTION_PREVIEWS_NAME = "CHEST_SPLITTER_PREVIEWS"
COLLECTION_PARTS_NAME = "CHEST_SPLITTER_PARTS"

# Prefixos de nomes para partes e objetos auxiliares
PART_A_SUFFIX = "__A"
PART_B_SUFFIX = "__B"
WORK_COPY_SUFFIX = "_work_copy"
PLANE_GUIDE_NAME = "CHEST_SPLITTER_PLANE_GUIDE"
PREVIEW_A_NAME = "CHEST_SPLITTER_PREVIEW_A"
PREVIEW_B_NAME = "CHEST_SPLITTER_PREVIEW_B"

# Cores da Viewport (RGBA) para visualização clara de peças A e B
COLOR_PART_A = (0.2, 0.6, 0.9, 1.0)    # Azul ciano
COLOR_PART_B = (0.95, 0.55, 0.15, 1.0) # Laranja âmbar

# Tolerâncias geométricas
MIN_FACE_AREA_BU = 1e-7
SCALE_TOLERANCE = 1e-4
VOLUME_REL_TOLERANCE = 0.005  # 0.5% de tolerância relativa de volume

# Distância padrão de explosão (em mm)
DEFAULT_EXPLOSION_DIST_MM = 30.0

# Presets de folga de montagem por lado (Fase 2)
CLEARANCE_PRESETS = {
    'TIGHT': 0.10,    # Justo
    'NORMAL': 0.15,   # Normal
    'EASY': 0.20,     # Fácil
    'LOOSE': 0.25,    # Solto
}

# Constantes de Cortador Sólido (Fase 3)
SOLID_CUTTER_NAME = "CHEST_SPLITTER_SOLID_CUTTER"

SPLIT_MODES = [
    ('PLANE', "Plano", "Divisão rápida por plano infinito orientável"),
    ('SOLID', "Cortador Sólido", "Divisão volumétrica por sólido fechado (Interseção / Diferença)"),
    ('MATERIAL', "Material", "Divisão assistida por fronteiras de materiais (Fase 4)"),
]

SOLID_SOURCE_TYPES = [
    ('PRIMITIVE', "Primitiva Paramétrica", "Gera uma primitiva volumétrica fechada na coleção de guias"),
    ('EXISTING', "Objeto Existente", "Utiliza um objeto fechado selecionado na cena"),
]

SOLID_PRIMITIVE_TYPES = [
    ('BOX', "Caixa / Cubo", "Primitiva em bloco cúbico ou prismático"),
    ('CYLINDER', "Cilindro", "Primitiva cilíndrica com tampas fechadas"),
    ('SPHERE', "Esfera", "Primitiva esférica UV"),
    ('CAPSULE', "Cápsula", "Primitiva tipo cápsula / estádio tridimensional"),
]


