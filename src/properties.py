"""Propriedades de configuração e estado persistente do Chest Part Splitter."""

import bpy
from bpy.props import (
    PointerProperty,
    StringProperty,
    FloatProperty,
    IntProperty,
    BoolProperty,
    FloatVectorProperty,
    EnumProperty,
)


class ChestSplitterSettings(bpy.types.PropertyGroup):
    """Estado persistente da sessão do Part Splitter na cena."""

    session_id: StringProperty(
        name="ID da Sessão",
        default="session_01",
        description="Identificador único da sessão de corte",
    )

    target_object: PointerProperty(
        name="Objeto Alvo",
        type=bpy.types.Object,
        description="Objeto malha original que será dividido em partes",
    )

    split_mode: EnumProperty(
        name="Modo de Divisão",
        items=[
            ('PLANE', "Plano", "Divisão por plano orientado (Fase 1)"),
            ('SOLID', "Cortador Sólido", "Divisão por cortador fechado (Fase 3)"),
            ('MATERIAL', "Materiais", "Divisão assistida por materiais (Fase 4)"),
        ],
        default='PLANE',
        description="Método de divisão do modelo",
    )

    session_status: EnumProperty(
        name="Status da Sessão",
        items=[
            ('EMPTY', "Vazio", "Nenhum alvo selecionado"),
            ('CONFIGURED', "Alvo Configurado", "Alvo selecionado e analisado"),
            ('PREVIEW_VALID', "Preview Válido", "Preview gerado com sucesso"),
            ('PREVIEW_INVALID', "Preview Inválido", "Falha na geração do preview"),
            ('COMMITTED', "Confirmado", "Partes finais geradas"),
        ],
        default='EMPTY',
    )

    # Diagnósticos em cache do alvo
    diag_dims_mm: FloatVectorProperty(
        name="Dimensões (mm)",
        size=3,
        default=(0.0, 0.0, 0.0),
        precision=2,
    )

    diag_triangles: IntProperty(
        name="Triângulos",
        default=0,
    )

    diag_faces: IntProperty(
        name="Faces",
        default=0,
    )

    diag_volume_mm3: FloatProperty(
        name="Volume (mm³)",
        default=0.0,
        precision=2,
    )

    diag_is_manifold: BoolProperty(
        name="É Manifold",
        default=True,
    )

    diag_non_manifold_edges: IntProperty(
        name="Arestas Abertas",
        default=0,
    )

    diag_has_unapplied_scale: BoolProperty(
        name="Escala Não Aplicada",
        default=False,
    )

    diag_is_non_uniform_scale: BoolProperty(
        name="Escala Não Uniforme",
        default=False,
    )

    diag_degenerate_faces: IntProperty(
        name="Faces Degeneradas",
        default=0,
    )

    # Feedback de mensagens ao usuário
    last_status: StringProperty(
        name="Mensagem de Status",
        default="",
    )

    last_status_level: EnumProperty(
        name="Nível de Status",
        items=[
            ('INFO', "Info", ""),
            ('SUCCESS', "Sucesso", ""),
            ('WARNING', "Aviso", ""),
            ('ERROR', "Erro", ""),
        ],
        default='INFO',
    )


def register():
    try:
        bpy.utils.register_class(ChestSplitterSettings)
    except ValueError:
        pass
    bpy.types.Scene.chest_splitter = PointerProperty(type=ChestSplitterSettings)


def unregister():
    if hasattr(bpy.types.Scene, "chest_splitter"):
        del bpy.types.Scene.chest_splitter
    try:
        bpy.utils.unregister_class(ChestSplitterSettings)
    except RuntimeError:
        pass
