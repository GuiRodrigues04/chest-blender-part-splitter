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


def _on_param_change_mark_stale(self, context):
    """Callback para marcar o preview como desatualizado quando parâmetros de corte ou encaixe mudam."""
    if self.session_status == 'PREVIEW_VALID':
        self.session_status = 'PREVIEW_STALE'
        self.last_status = "Os ajustes mudaram. Atualize a prévia antes de criar as peças."
        self.last_status_level = 'WARNING'


def _on_clearance_preset_update(self, context):
    """Atualiza a folga por lado quando o usuário seleciona um preset."""
    if self.clearance_preset in CLEARANCE_PRESETS:
        self.clearance_per_side_mm = CLEARANCE_PRESETS[self.clearance_preset]
    _on_param_change_mark_stale(self, context)


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
    _on_param_change_mark_stale(self, context)


def _on_target_object_update(self, context):
    """Callback ao alterar ou limpar o objeto alvo."""
    _on_param_change_mark_stale(self, context)


class ChestSplitterSettings(bpy.types.PropertyGroup):
    """Estado persistente da sessão do Part Splitter na cena."""

    session_id: StringProperty(
        name="ID da Sessão",
        default="",
        description="Identificador único da sessão de corte",
    )

    session_input_signature: StringProperty(
        name="Assinatura de Entrada da Prévia",
        default="",
        description="Assinatura criptográfica dos parâmetros de entrada da prévia gerada",
    )

    target_object: PointerProperty(
        name="Objeto Alvo",
        type=bpy.types.Object,
        description="Objeto malha original que será dividido em partes",
        update=_on_target_object_update,
    )


    split_mode: EnumProperty(
        name="Modo de Divisão",
        items=SPLIT_MODES,
        default='PLANE',
        description="Método de divisão do modelo",
        update=_on_param_change_mark_stale,
    )

    session_status: EnumProperty(
        name="Status da Sessão",
        items=[
            ('EMPTY', "Vazio", "Nenhum alvo selecionado"),
            ('CONFIGURED', "Alvo Configurado", "Alvo selecionado e analisado"),
            ('PREVIEW_VALID', "Preview Válido", "Preview gerado com sucesso"),
            ('PREVIEW_STALE', "Preview Desatualizado", "Os ajustes mudaram. Atualize a prévia antes de criar as peças"),
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
        update=_on_param_change_mark_stale,
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
    loop_interface_normal: FloatVectorProperty(
        name="Normal da Interface do Loop",
        size=3,
        default=(0.0, 0.0, 1.0),
        subtype='DIRECTION',
        description="Vetor normal de mundo apontando da Parte A para a Parte B",
    )
    loop_interface_origin: FloatVectorProperty(
        name="Origem da Interface do Loop",
        size=3,
        default=(0.0, 0.0, 0.0),
        subtype='TRANSLATION',
        description="Centro da interface do loop em coordenadas de mundo",
    )
    loop_behavior: EnumProperty(
        name="Comportamento do Loop",
        items=[
            ('AUTO', "Automático", "Detecta automaticamente entre destacar saliência ou extrair com profundidade"),
            ('DETACH', "Destacar Parte", "Destaca a região fechada pelo loop criando uma tampa na base"),
            ('EXTRUDE', "Extrair com Profundidade", "Projeta o contorno para dentro do sólido até a profundidade especificada"),
        ],
        default='AUTO',
        description="Comportamento do corte por contorno: automático, destacar parte ou extrair com profundidade",
        update=_on_param_change_mark_stale,
    )
    loop_extrude_depth_mm: FloatProperty(
        name="Profundidade de Extração (mm)",
        description="Profundidade física da extração para dentro do sólido",
        default=5.0,
        min=0.1,
        precision=2,
        update=_on_param_change_mark_stale,
    )
    loop_through_cut: BoolProperty(
        name="Corte Passante",
        description="Permite que a profundidade de extração atravesse completamente o modelo",
        default=False,
        update=_on_param_change_mark_stale,
    )
    loop_detected_mode: EnumProperty(
        name="Modo Detectado",
        items=[
            ('DETACH', "Destacar", "Saliência 3D detectada"),
            ('EXTRUDE', "Extrair", "Região plana detectada"),
            ('AMBIGUOUS', "Ambíguo", "Escolha manual necessária"),
        ],
        default='DETACH',
    )
    loop_auto_reason: StringProperty(
        name="Motivo da Decisão",
        default="",
    )

    # --- Fim Loop ---

    # --- Configurações do Corte por Material (Etapa 6) ---
    material_split_index: IntProperty(
        name="Material da Parte A",
        default=0,
        min=0,
        description="Índice do slot de material que será isolado como Parte A",
        update=_on_param_change_mark_stale,
    )
    material_region_index: IntProperty(
        name="Região do Material",
        default=0,
        min=0,
        description="Qual área separada (ilha) do material será extraída, quando a mesma cor aparece em vários lugares",
        update=_on_param_change_mark_stale,
    )
    material_extrude_depth_mm: FloatProperty(
        name="Profundidade da Peça (mm)",
        default=5.0,
        min=0.1,
        precision=2,
        description="Profundidade física da peça caso a região do material seja superficial",
        update=_on_param_change_mark_stale,
    )
    material_detected_type: StringProperty(
        name="Diagnóstico do Material",
        default="",
    )

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
        update=_on_param_change_mark_stale,
    )

    connector_type: EnumProperty(
        name="Tipo de Encaixe",
        items=[
            ('CYLINDER', "Pino Cilíndrico", "Pino cilíndrico com chanfro de entrada"),
            ('CAPSULE', "Chave Cápsula", "Pino oblongo/cápsula que impede rotação"),
        ],
        default='CYLINDER',
        description="Formato geométrico do encaixe",
        update=_on_param_change_mark_stale,
    )

    connector_male_part: EnumProperty(
        name="Parte com Macho",
        items=[
            ('A', "Parte A", "O pino macho fica na Parte A e a cavidade na Parte B"),
            ('B', "Parte B", "O pino macho fica na Parte B e a cavidade na Parte A"),
        ],
        default='A',
        description="Define qual parte recebe o pino saliente",
        update=_on_param_change_mark_stale,
    )

    part_a_is_superior: BoolProperty(
        name="Parte A é Superior",
        default=True,
        description="Indica se a Parte A está geometricamente no topo em relação ao eixo Z de corte",
    )

    connector_diameter_mm: FloatProperty(
        name="Diâmetro Nominal (mm)",
        default=6.0,
        min=2.0,
        max=40.0,
        precision=2,
        description="Diâmetro ou largura nominal do pino",
        update=_on_param_change_mark_stale,
    )

    connector_capsule_length_mm: FloatProperty(
        name="Comprimento Lateral (mm)",
        default=14.0,
        min=2.0,
        max=150.0,
        precision=1,
        description="Comprimento/largura lateral total do encaixe cápsula no plano de corte (mínimo = diâmetro)",
        update=_on_param_change_mark_stale,
    )

    connector_max_safe_lateral_mm: FloatProperty(
        name="Limite Máx Seguro (mm)",
        default=0.0,
        precision=1,
        description="Limite máximo de comprimento lateral calculado para evitar colisão entre encaixes ou com a borda",
    )

    connector_length_mm: FloatProperty(
        name="Comprimento de Inserção (mm)",
        default=8.0,
        min=2.0,
        max=50.0,
        precision=2,
        description="Profundidade útil nominal do encaixe",
        update=_on_param_change_mark_stale,
    )

    connector_chamfer_mm: FloatProperty(
        name="Chanfro de Entrada (mm)",
        default=0.8,
        min=0.0,
        max=5.0,
        precision=2,
        description="Chanfro na ponta do pino para facilitar a inserção",
        update=_on_param_change_mark_stale,
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
        update=_on_param_change_mark_stale,
    )

    end_clearance_mm: FloatProperty(
        name="Folga de Fundo (mm)",
        default=0.5,
        min=0.1,
        max=3.0,
        precision=2,
        description="Espaço extra no fundo da cavidade fêmea para evitar colisão",
        update=_on_param_change_mark_stale,
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
        update=_on_param_change_mark_stale,
    )

    connector_edge_margin_mm: FloatProperty(
        name="Margem da Borda (mm)",
        default=4.0,
        min=1.0,
        max=30.0,
        precision=1,
        description="Distância mínima de segurança até a casca externa do modelo",
        update=_on_param_change_mark_stale,
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

    # --- Visualização de Cores e Exportação Multicolor (Fase 5) ---
    preview_color_mode: EnumProperty(
        name="Modo de Cor do Preview",
        items=[
            ('MATERIALS', "Cores Originais (Materiais)", "Mantém a visualização dos materiais e texturas reais do modelo"),
            ('PARTS', "Cores A / B (Contraste)", "Destaca Parte A e Parte B com azul e laranja para conferir a divisão"),
        ],
        default='MATERIALS',
        description="Alterna entre as cores reais dos materiais do modelo e as cores de contraste das partes",
    )

    export_directory: StringProperty(
        name="Pasta de Exportação",
        subtype='DIR_PATH',
        default="//",
        description="Diretório onde os arquivos de impressão 3D serão salvos",
    )

    export_format: EnumProperty(
        name="Formato",
        items=[
            ('3MF', "3MF Multimaterial (.3mf)", "Formato nativo para Bambu Studio / OrcaSlicer com cores preservadas"),
            ('STL_PER_MATERIAL', "STL por Material / Cor (.stl)", "Arquivos STL separados por cor para importação multipartes"),
            ('STL_PARTS', "STL por Parte (.stl)", "Arquivos STL separados para cada parte"),
            ('OBJ', "Wavefront OBJ (.obj + .mtl)", "Geometria e materiais em formato OBJ"),
        ],
        default='3MF',
        description="Formato de exportação para fatiamento e impressão 3D",
    )

    export_layout: EnumProperty(
        name="Disposição",
        items=[
            ('ASSEMBLED', "Posição Montada", "Exporta no espaço global de montagem original"),
            ('PRINT_BED', "Mesa de Impressão", "Exporta as peças assentadas lado a lado"),
        ],
        default='ASSEMBLED',
        description="Orientação espacial dos modelos no arquivo de exportação",
    )


def register():
    try:
        bpy.utils.register_class(ChestSplitterSettings)
    except ValueError:
        pass
    bpy.types.Scene.chest_splitter = PointerProperty(type=ChestSplitterSettings)
    # Alias para compatibilidade e nova identidade (Seção 8 do Plano Antigravity)
    bpy.types.Scene.part_splitter = property(lambda self: self.chest_splitter)


def unregister():
    if hasattr(bpy.types.Scene, "part_splitter"):
        del bpy.types.Scene.part_splitter
    if hasattr(bpy.types.Scene, "chest_splitter"):
        del bpy.types.Scene.chest_splitter
    try:
        bpy.utils.unregister_class(ChestSplitterSettings)
    except RuntimeError:
        pass
