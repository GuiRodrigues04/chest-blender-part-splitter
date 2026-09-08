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


from .constants import (
    CLEARANCE_PRESETS,
    SPLIT_MODES,
    SOLID_SOURCE_TYPES,
    SOLID_PRIMITIVE_TYPES,
)


def _on_preview_transform_update(self, context):
    """Callback disparado quando o modo de visualização ou a distância de explosão é alterada."""
    if context and hasattr(context, "scene"):
        try:
            from .operators import update_preview_positions
            update_preview_positions(context.scene)
        except Exception:
            pass


def _on_clearance_preset_update(self, context):
    """Atualiza a folga por lado quando o usuário seleciona um preset."""
    if self.clearance_preset in CLEARANCE_PRESETS:
        self.clearance_per_side_mm = CLEARANCE_PRESETS[self.clearance_preset]


def _poll_mesh_cutter(self, obj):
    """Filtra objetos válidos para atuarem como cortador sólido."""
    return obj.type == 'MESH' and obj != self.target_object


def _on_cutter_object_update(self, context):
    """Atualiza diagnósticos imediatos ao alterar o objeto cortador."""
    if self.solid_cutter_object and self.solid_cutter_object.type == 'MESH':
        try:
            from .diagnostic import get_scene_scale_to_mm
            import bmesh
            scale_to_mm = get_scene_scale_to_mm(context.scene if context else None)
            bm = bmesh.new()
            bm.from_mesh(self.solid_cutter_object.data)
            bm.transform(self.solid_cutter_object.matrix_world)
            self.solid_cutter_is_manifold = all(e.is_manifold for e in bm.edges)
            self.solid_cutter_non_manifold_edges = len([e for e in bm.edges if not e.is_manifold])
            self.solid_cutter_triangles = sum(len(f.verts) - 2 for f in bm.faces)
            vol_bu = bm.calc_volume()
            self.solid_cutter_volume_mm3 = abs(vol_bu) * (scale_to_mm ** 3)
            xs = [v.co.x for v in bm.verts]
            ys = [v.co.y for v in bm.verts]
            zs = [v.co.z for v in bm.verts]
            if xs:
                self.solid_cutter_dims_mm = (
                    (max(xs) - min(xs)) * scale_to_mm,
                    (max(ys) - min(ys)) * scale_to_mm,
                    (max(zs) - min(zs)) * scale_to_mm,
                )
            bm.free()
        except Exception:
            pass


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
        items=SPLIT_MODES,
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

    # --- Configurações do Plano de Corte (Fase 1) ---
    plane_origin: FloatVectorProperty(
        name="Origem do Plano",
        size=3,
        default=(0.0, 0.0, 0.0),
        precision=3,
        description="Ponto 3D por onde passa o plano de corte",
    )

    plane_normal: FloatVectorProperty(
        name="Normal do Plano",
        size=3,
        default=(0.0, 0.0, 1.0),
        precision=3,
        description="Vetor normal de orientação do corte",
    )

    invert_sides: BoolProperty(
        name="Inverter Lados A/B",
        default=False,
        description="Inverte os papéis de Parte A e Parte B",
    )

    # --- Fase 3A (Modo D): Loop de Arestas ---
    loop_is_captured: BoolProperty(
        name="Loop Capturado",
        default=False,
    )
    loop_vertex_count: IntProperty(
        name="Vértices no Loop",
        default=0,
    )
    loop_vertex_indices: StringProperty(
        name="Índices dos Vértices do Loop",
        default="",
    )
    loop_is_planar: BoolProperty(
        name="Loop é Plano",
        default=False,
    )
    loop_planarity_deviation_mm: FloatProperty(
        name="Desvio de Planicidade (mm)",
        default=0.0,
    )
    loop_seed_face_index: IntProperty(
        name="Índice da Face Semente (Região A)",
        default=-1,
    )
    loop_topology_signature: StringProperty(
        name="Assinatura Topológica",
        default="",
    )

    # --- Fim Loop ---

    # --- Guias de Visualização ---
    view_mode: EnumProperty(
        name="Visualização",
        items=[
            ('ASSEMBLED', "Montado", "Peças unidas na posição original"),
            ('EXPLODED', "Explodido", "Peças afastadas para inspeção do corte"),
        ],
        default='ASSEMBLED',
        description="Modo de visualização das partes de preview",
        update=lambda self, context: _on_preview_transform_update(self, context),
    )

    explosion_distance_mm: FloatProperty(
        name="Distância de Explosão (mm)",
        default=30.0,
        min=0.0,
        max=500.0,
        precision=1,
        description="Distância de afastamento entre as partes na vista explodida",
        update=lambda self, context: _on_preview_transform_update(self, context),
    )

    # --- Configurações do Cortador Sólido (Fase 3) ---
    solid_source: EnumProperty(
        name="Origem do Cortador",
        items=SOLID_SOURCE_TYPES,
        default='PRIMITIVE',
        description="Origem geométrica do cortador sólido",
    )

    solid_primitive_type: EnumProperty(
        name="Primitiva",
        items=SOLID_PRIMITIVE_TYPES,
        default='BOX',
        description="Formato geométrico da primitiva de corte",
    )

    solid_cutter_object: PointerProperty(
        name="Objeto Cortador",
        type=bpy.types.Object,
        poll=_poll_mesh_cutter,
        update=_on_cutter_object_update,
        description="Objeto fechado e manifold que atua como cortador sólido",
    )

    solid_cutter_is_manifold: BoolProperty(
        name="Cortador Manifold",
        default=True,
    )

    solid_cutter_non_manifold_edges: IntProperty(
        name="Arestas Abertas Cortador",
        default=0,
    )

    solid_cutter_triangles: IntProperty(
        name="Triângulos Cortador",
        default=0,
    )

    solid_cutter_volume_mm3: FloatProperty(
        name="Volume Cortador (mm³)",
        default=0.0,
        precision=2,
    )

    solid_cutter_dims_mm: FloatVectorProperty(
        name="Dimensões Cortador (mm)",
        size=3,
        default=(0.0, 0.0, 0.0),
        precision=2,
    )


    # --- Diagnósticos das Partes Divididas ---
    part_a_volume_mm3: FloatProperty(
        name="Volume Parte A (mm³)",
        default=0.0,
        precision=2,
    )

    part_a_dims_mm: FloatVectorProperty(
        name="Dimensões Parte A (mm)",
        size=3,
        default=(0.0, 0.0, 0.0),
        precision=2,
    )

    part_a_triangles: IntProperty(
        name="Triângulos Parte A",
        default=0,
    )

    part_a_is_manifold: BoolProperty(
        name="Parte A Manifold",
        default=True,
    )

    part_a_non_manifold_edges: IntProperty(
        name="Arestas Abertas A",
        default=0,
    )

    part_a_components: IntProperty(
        name="Componentes Parte A",
        default=0,
    )

    part_b_volume_mm3: FloatProperty(
        name="Volume Parte B (mm³)",
        default=0.0,
        precision=2,
    )

    part_b_dims_mm: FloatVectorProperty(
        name="Dimensões Parte B (mm)",
        size=3,
        default=(0.0, 0.0, 0.0),
        precision=2,
    )

    part_b_triangles: IntProperty(
        name="Triângulos Parte B",
        default=0,
    )

    part_b_is_manifold: BoolProperty(
        name="Parte B Manifold",
        default=True,
    )

    part_b_non_manifold_edges: IntProperty(
        name="Arestas Abertas B",
        default=0,
    )

    part_b_components: IntProperty(
        name="Componentes Parte B",
        default=0,
    )

    part_sum_volume_mm3: FloatProperty(
        name="Soma dos Volumes (mm³)",
        default=0.0,
        precision=2,
    )

    volume_diff_pct: FloatProperty(
        name="Diferença de Volume (%)",
        default=0.0,
        precision=3,
    )

    # --- Configurações de Encaixes e Folgas (Fase 2) ---
    connector_enabled: BoolProperty(
        name="Ativar Encaixes",
        default=False,
        description="Gera pinos macho e cavidades fêmea na interface do corte",
    )

    connector_type: EnumProperty(
        name="Tipo de Encaixe",
        items=[
            ('CYLINDER', "Pino Cilíndrico", "Pino cilíndrico com chanfro de entrada"),
            ('CAPSULE', "Chave Cápsula", "Pino oblongo/cápsula que impede rotação"),
        ],
        default='CYLINDER',
        description="Formato geométrico do encaixe",
    )

    connector_male_part: EnumProperty(
        name="Parte com Macho",
        items=[
            ('A', "Parte A", "O pino macho fica na Parte A e a cavidade na Parte B"),
            ('B', "Parte B", "O pino macho fica na Parte B e a cavidade na Parte A"),
        ],
        default='A',
        description="Define qual parte recebe o pino saliente",
    )

    connector_diameter_mm: FloatProperty(
        name="Diâmetro Nominal (mm)",
        default=6.0,
        min=2.0,
        max=40.0,
        precision=2,
        description="Diâmetro ou largura nominal do pino",
    )

    connector_length_mm: FloatProperty(
        name="Comprimento de Inserção (mm)",
        default=8.0,
        min=2.0,
        max=50.0,
        precision=2,
        description="Profundidade útil nominal do encaixe",
    )

    connector_chamfer_mm: FloatProperty(
        name="Chanfro de Entrada (mm)",
        default=0.8,
        min=0.0,
        max=5.0,
        precision=2,
        description="Chanfro na ponta do pino para facilitar a inserção",
    )

    clearance_preset: EnumProperty(
        name="Preset de Folga",
        items=[
            ('TIGHT', "Justo (0,10 mm)", "Impressora muito bem calibrada"),
            ('NORMAL', "Normal (0,15 mm)", "Primeiro teste recomendado para PLA"),
            ('EASY', "Fácil (0,20 mm)", "Montagem manual suave sem força"),
            ('LOOSE', "Solto (0,25 mm)", "Peças volumosas ou folga maior"),
            ('CUSTOM', "Personalizado", "Valor livre de folga por lado"),
        ],
        default='NORMAL',
        description="Predefinições recomendadas para FDM (bico 0,4 mm e PLA)",
        update=lambda self, context: _on_clearance_preset_update(self, context),
    )

    clearance_per_side_mm: FloatProperty(
        name="Folga por Lado (mm)",
        default=0.15,
        min=0.05,
        max=1.0,
        precision=3,
        description="Folga radial por lado na cavidade fêmea (folga total no diâmetro = 2x este valor)",
    )

    end_clearance_mm: FloatProperty(
        name="Folga de Fundo (mm)",
        default=0.5,
        min=0.1,
        max=3.0,
        precision=2,
        description="Espaço extra no fundo da cavidade fêmea para evitar colisão",
    )

    connector_distribution: EnumProperty(
        name="Distribuição",
        items=[
            ('CENTER', "1 Pino (Centro)", "Um conector no centro geométrico do corte"),
            ('LINEAR_2', "2 Pinos (Linha)", "Dois conectores alinhados no maior vão"),
            ('LINEAR_3', "3 Pinos (Linha)", "Três conectores distribuídos em linha"),
            ('GRID_4', "4 Pinos (Grade)", "Quatro conectores distribuídos em grade 2x2"),
        ],
        default='CENTER',
        description="Padrão de distribuição dos encaixes no plano",
    )

    connector_edge_margin_mm: FloatProperty(
        name="Margem da Borda (mm)",
        default=4.0,
        min=1.0,
        max=30.0,
        precision=1,
        description="Distância mínima de segurança até a casca externa do modelo",
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
