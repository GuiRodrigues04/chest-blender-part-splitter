"""Constantes e definições padrão para o Chest Part Splitter."""

# Coleções de organização no Blender
COLLECTION_GUIDES_NAME = "CHEST_SPLITTER_GUIDES"
COLLECTION_PREVIEWS_NAME = "CHEST_SPLITTER_PREVIEWS"
COLLECTION_PARTS_NAME = "CHEST_SPLITTER_PARTS"

# Prefixos de nomes para partes e objetos auxiliares
PART_A_SUFFIX = "__A"
PART_B_SUFFIX = "__B"
WORK_COPY_SUFFIX = "_work_copy"

# Tolerâncias geométricas (em mm e radianos)
MIN_FACE_AREA_BU = 1e-7
SCALE_TOLERANCE = 1e-4

# Presets de folga de montagem por lado (Fase 2)
CLEARANCE_PRESETS = {
    'TIGHT': 0.10,    # Justo
    'NORMAL': 0.15,   # Normal
    'EASY': 0.20,     # Fácil
    'LOOSE': 0.25,    # Solto
}
