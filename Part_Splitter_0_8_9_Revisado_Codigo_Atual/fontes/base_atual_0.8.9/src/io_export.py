"""Módulo de exportação do Chest Part Splitter (Fase 5 e Suporte a Multicolor).

Permite exportar partes divididas para impressão 3D em múltiplos formatos:
- 3MF Multimaterial (.3mf) com grupos de cores e metadados preservados.
- STLs separados por material/cor (.stl) para carregamento como objeto multipartes no Bambu Studio / PrusaSlicer.
- STLs por parte (.stl).
- Wavefront OBJ (.obj + .mtl).
"""

import os
import io
import zipfile
import math
import html
import tempfile
import shutil
from typing import List, Dict, Any, Tuple, Set
import bpy
import bmesh
from mathutils import Vector, Matrix


def sanitize_unique_filename(name: str, used_names: Set[str], ext: str = ".stl") -> str:
    """Sanitiza um nome de arquivo e garante unicidade evitando colisões ou sobrescrita silenciosa."""
    clean = "".join(c for c in name if c.isalnum() or c in ('_', '-'))
    clean = clean.strip("._-")
    if not clean:
        clean = "Part"
    
    candidate = clean
    counter = 1
    while candidate.lower() in used_names:
        counter += 1
        candidate = f"{clean}_{counter}"
    used_names.add(candidate.lower())
    return f"{candidate}{ext}"




def get_material_rgba(mat: bpy.types.Material) -> Tuple[float, float, float, float]:
    """Extrai cor RGBA de um material do Blender (diffuse_color ou Principled BSDF)."""
    if not mat:
        return (0.8, 0.8, 0.8, 1.0)
    
    # 1. Tenta obter do nó Principled BSDF
    if mat.use_nodes and mat.node_tree:
        for node in mat.node_tree.nodes:
            if node.type == 'BSDF_PRINCIPLED':
                base_col_sock = node.inputs.get("Base Color")
                if base_col_sock and hasattr(base_col_sock, "default_value"):
                    col = base_col_sock.default_value
                    return (col[0], col[1], col[2], col[3] if len(col) > 3 else 1.0)

    # 2. Fallback para diffuse_color
    d = mat.diffuse_color
    return (d[0], d[1], d[2], d[3] if len(d) > 3 else 1.0)


def rgba_to_hex(rgba: Tuple[float, float, float, float]) -> str:
    """Converte RGBA float (0..1) para string hexadecimal '#RRGGBBAA'."""
    r = min(255, max(0, int(rgba[0] * 255)))
    g = min(255, max(0, int(rgba[1] * 255)))
    b = min(255, max(0, int(rgba[2] * 255)))
    a = min(255, max(0, int(rgba[3] * 255)))
    return f"#{r:02X}{g:02X}{b:02X}{a:02X}"


def publish_staged_files_atomic(staged_files: List[Tuple[str, str]], target_dir: str) -> List[str]:
    """Publica arquivos estagiados para o diretório de destino de forma atômica com rollback.
    
    Se ocorrer qualquer falha durante a publicação de qualquer arquivo:
    - Todos os arquivos recém-criados no destino durante esta operação são removidos.
    - Todos os arquivos preexistentes que foram substituídos são restaurados de seus backups.
    - Nenhuma saída parcial ou corrompida permanece.
    """
    os.makedirs(target_dir, exist_ok=True)
    backup_dir = tempfile.mkdtemp(prefix="chest_publish_backup_")
    copied_new: List[str] = []
    replaced_backups: List[Tuple[str, str]] = []  # (target_path, backup_path)
    published_files: List[str] = []

    try:
        for stage_path, filename in staged_files:
            target_path = os.path.join(target_dir, filename)
            if os.path.exists(target_path):
                backup_path = os.path.join(backup_dir, f"bak_{len(replaced_backups)}_{filename}")
                shutil.copy2(target_path, backup_path)
                replaced_backups.append((target_path, backup_path))
            else:
                copied_new.append(target_path)
            
            shutil.copy2(stage_path, target_path)
            published_files.append(target_path)
            
    except Exception as e:
        for p in copied_new:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        for target_path, backup_path in replaced_backups:
            if os.path.exists(backup_path):
                try:
                    shutil.copy2(backup_path, target_path)
                except OSError:
                    pass
        raise RuntimeError(f"Falha durante a publicação dos arquivos no destino: {e}. Rollback executado com sucesso.") from e
    finally:
        if os.path.exists(backup_dir):
            try:
                shutil.rmtree(backup_dir)
            except OSError:
                pass

    return published_files


def build_3mf_xml(objects: List[bpy.types.Object], unit_scale: float = 1000.0) -> str:
    """Gera o documento XML '3D/3dmodel.model' conforme especificação 3MF Core + Material Extension."""
    xml_lines = []
    xml_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    xml_lines.append('<model unit="millimeter" xml:lang="en-US"')
    xml_lines.append(' xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"')
    xml_lines.append(' xmlns:m="http://schemas.microsoft.com/3dmanufacturing/material/2015/02">')
    xml_lines.append(' <metadata name="Application">Chest Part Splitter - Blender Extension</metadata>')
    xml_lines.append(' <resources>')

    # 1. Coleta e consolida paleta de materiais/cores globais (C27/V29: incluindo malha avaliada)
    color_map: Dict[str, Tuple[int, int]] = {} # mat_key -> (colorgroup_id, color_index)
    colorgroup_id = 1
    unique_materials = []
    
    for obj in objects:
        if obj.type != 'MESH' or not obj.data:
            continue
        mats = []
        eval_obj = None
        eval_mesh = None
        if len(obj.modifiers) > 0 and bpy.context:
            try:
                depsgraph = bpy.context.evaluated_depsgraph_get()
                eval_obj = obj.evaluated_get(depsgraph)
                eval_mesh = eval_obj.to_mesh()
                if eval_mesh and eval_mesh.materials:
                    mats = list(eval_mesh.materials)
            except Exception as e:
                raise RuntimeError(f"Falha ao avaliar modificadores de '{obj.name}': {e}")
            finally:
                if eval_obj and eval_mesh:
                    eval_obj.to_mesh_clear()
        if not mats:
            mats = list(obj.data.materials)

        for mat in mats:
            if mat and mat.name not in color_map:
                col_rgba = get_material_rgba(mat)
                hex_col = rgba_to_hex(col_rgba)
                idx = len(unique_materials)
                color_map[mat.name] = (colorgroup_id, idx)
                unique_materials.append(hex_col)

    if not unique_materials:
        unique_materials.append("#CCCCCCFF")

    xml_lines.append(f'  <m:colorgroup id="{colorgroup_id}">')
    for c_hex in unique_materials:
        xml_lines.append(f'   <m:color color="{c_hex}"/>')
    xml_lines.append('  </m:colorgroup>')

    # 2. Gera os objetos de malha no XML
    next_obj_id = colorgroup_id + 1
    build_items = []

    for obj in objects:
        if obj.type != 'MESH' or not obj.data:
            continue

        obj_id = next_obj_id
        next_obj_id += 1
        build_items.append(obj_id)

        bm = bmesh.new()
        eval_obj = None
        eval_mesh = None
        if len(obj.modifiers) > 0 and bpy.context:
            try:
                depsgraph = bpy.context.evaluated_depsgraph_get()
                eval_obj = obj.evaluated_get(depsgraph)
                eval_mesh = eval_obj.to_mesh()
                bm.from_mesh(eval_mesh)
            except Exception as e:
                bm.free()
                raise RuntimeError(f"Falha ao avaliar modificadores do objeto '{obj.name}': {e}")
        else:
            bm.from_mesh(obj.data)

        bm.transform(obj.matrix_world)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        escaped_name = html.escape(obj.name, quote=True)
        xml_lines.append(f'  <object id="{obj_id}" type="model" name="{escaped_name}">')
        xml_lines.append('   <mesh>')
        xml_lines.append('    <vertices>')
        for v in bm.verts:
            # Coordenadas em milímetros
            x = v.co.x * unit_scale
            y = v.co.y * unit_scale
            z = v.co.z * unit_scale
            xml_lines.append(f'     <vertex x="{x:.5f}" y="{y:.5f}" z="{z:.5f}"/>')
        xml_lines.append('    </vertices>')

        xml_lines.append('    <triangles>')
        mat_slots = eval_mesh.materials if (eval_mesh and len(eval_mesh.materials) > 0) else obj.data.materials
        for f in bm.faces:
            v0 = f.verts[0].index
            v1 = f.verts[1].index
            v2 = f.verts[2].index
            
            c_idx = 0
            if f.material_index < len(mat_slots):
                m_slot = mat_slots[f.material_index]
                if m_slot and m_slot.name in color_map:
                    c_idx = color_map[m_slot.name][1]

            xml_lines.append(
                f'     <triangle v1="{v0}" v2="{v1}" v3="{v2}" pid="{colorgroup_id}" p1="{c_idx}"/>'
            )
        xml_lines.append('    </triangles>')
        xml_lines.append('   </mesh>')
        xml_lines.append('  </object>')

        bm.free()
        if eval_obj and eval_mesh:
            eval_obj.to_mesh_clear()

    xml_lines.append(' </resources>')
    xml_lines.append(' <build>')
    for bid in build_items:
        xml_lines.append(f'  <item objectid="{bid}"/>')
    xml_lines.append(' </build>')
    xml_lines.append('</model>')

    return '\n'.join(xml_lines)


def export_objects_to_3mf(objects: List[bpy.types.Object], filepath: str, unit_scale: float = 1000.0) -> None:
    """Exporta os objetos fornecidos em um arquivo 3MF compatível com Bambu Studio, OrcaSlicer e PrusaSlicer."""
    content_types_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
        '</Types>'
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
        '</Relationships>'
    )
    model_xml = build_3mf_xml(objects, unit_scale=unit_scale)

    dir_name = os.path.dirname(os.path.abspath(filepath))
    os.makedirs(dir_name, exist_ok=True)
    base_name = os.path.basename(filepath)
    temp_fd, temp_path = tempfile.mkstemp(prefix=f"{base_name}_", suffix=".tmp", dir=dir_name)
    os.close(temp_fd)
    try:
        with zipfile.ZipFile(temp_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('[Content_Types].xml', content_types_xml)
            zf.writestr('_rels/.rels', rels_xml)
            zf.writestr('3D/3dmodel.model', model_xml.encode('utf-8'))

        # Substituição atômica sem apagar prematuramente o arquivo anterior em falhas
        os.replace(temp_path, filepath)
    except Exception:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise



def separate_object_by_material(source_obj: bpy.types.Object, target_collection: bpy.types.Collection) -> List[bpy.types.Object]:
    """Divide um objeto malha em múltiplos sub-objetos individuais, um para cada material/cor.
    
    Cada sub-objeto retém suas faces correspondentes, seu material exclusivo e a mesma
    origem de coordenadas de mundo, permitindo importação e alinhamento direto no fatiador.
    """
    if source_obj.type != 'MESH' or not source_obj.data:
        return []

    materials = source_obj.data.materials
    if len(materials) <= 1:
        return [source_obj]

    created_objs = []
    base_name = source_obj.name

    for mat_idx, mat in enumerate(materials):
        mat_name = mat.name if mat else f"Mat_{mat_idx}"
        
        bm = bmesh.new()
        bm.from_mesh(source_obj.data)
        bm.faces.ensure_lookup_table()
        
        faces_to_delete = [f for f in bm.faces if f.material_index != mat_idx]
        if len(faces_to_delete) == len(bm.faces):
            bm.free()
            continue

        bmesh.ops.delete(bm, geom=faces_to_delete, context='FACES')

        sub_mesh = bpy.data.meshes.new(f"{base_name}__{mat_name}")
        if mat:
            sub_mesh.materials.append(mat)
        
        for f in bm.faces:
            f.material_index = 0
            
        bm.to_mesh(sub_mesh)
        sub_mesh.update()
        bm.free()

        sub_obj = bpy.data.objects.new(f"{base_name}__{mat_name}", sub_mesh)
        sub_obj.matrix_world = source_obj.matrix_world.copy()
        if mat:
            sub_obj.color = mat.diffuse_color

        # Validação estrita de contrato de sólidos para impressão 3D (Seção 9)
        bm_check = bmesh.new()
        bm_check.from_mesh(sub_mesh)
        is_manifold = all(e.is_manifold for e in bm_check.edges)
        open_edges = len([e for e in bm_check.edges if not e.is_manifold])
        bm_check.free()

        sub_obj["is_manifold"] = is_manifold
        sub_obj["open_edges"] = open_edges
        sub_obj["is_solid_for_printing"] = is_manifold
        sub_obj["chest_session_id"] = source_obj.get("chest_session_id", source_obj.get("chest_splitter_session_id", ""))
        sub_obj["chest_role"] = "SUBPART_MATERIAL"
        if "chest_splitter_part" in source_obj:
            sub_obj["chest_splitter_part"] = source_obj["chest_splitter_part"]

        target_collection.objects.link(sub_obj)
        created_objs.append(sub_obj)

    return created_objs


def export_objects_to_stl_by_material(
    objects: List[bpy.types.Object],
    output_dir: str,
    unit_scale: float = 1000.0,
) -> List[str]:
    """Exporta os objetos divididos em arquivos STL separados por material/cor.
    
    Arquivos gerados compartilham o mesmo sistema de coordenadas globais em milímetros.
    Ao importar todos de uma vez no Bambu Studio ou PrusaSlicer, o fatiador os carrega
    como um único objeto multipartes, permitindo atribuir filamentos/cores a cada um.
    Utiliza transação atômica em diretório temporário para evitar saídas parciais ou corrompidas.
    """
    os.makedirs(output_dir, exist_ok=True)
    exported_files = []

    # Preserva seleção e objeto ativo
    prev_selected = list(bpy.context.selected_objects) if bpy.context else []
    prev_active = bpy.context.view_layer.objects.active if bpy.context and bpy.context.view_layer else None

    # Cria coleção temporária isolada
    temp_col = bpy.data.collections.new("TEMP_CHEST_EXPORT")
    bpy.context.scene.collection.children.link(temp_col)

    temp_stage_dir = tempfile.mkdtemp(prefix="chest_export_stl_")
    staged_files = []

    try:
        all_sub_parts = []
        for obj in objects:
            if obj.type != 'MESH' or not obj.data:
                continue

            mats = obj.data.materials
            if len(mats) > 1:
                sub_parts = separate_object_by_material(obj, temp_col)
                all_sub_parts.extend([(obj, p) for p in sub_parts])
            else:
                all_sub_parts.append((obj, obj))

        # Valida todas as subpeças ANTES de qualquer gravação (P07 e T23)
        for parent_obj, part in all_sub_parts:
            bm_part = bmesh.new()
            eval_obj = None
            eval_mesh = None
            if len(part.modifiers) > 0 and bpy.context:
                try:
                    depsgraph = bpy.context.evaluated_depsgraph_get()
                    eval_obj = part.evaluated_get(depsgraph)
                    eval_mesh = eval_obj.to_mesh()
                    bm_part.from_mesh(eval_mesh)
                except Exception as e:
                    bm_part.free()
                    raise RuntimeError(f"Falha ao avaliar modificadores de '{part.name}': {e}")
            else:
                bm_part.from_mesh(part.data)
            
            from .operators import validate_printable_mesh
            is_valid, msg, _ = validate_printable_mesh(bm_part, part_name=part.name, unit_scale=unit_scale, check_manifold=True)
            bm_part.free()
            if eval_obj and eval_mesh:
                eval_obj.to_mesh_clear()
            
            if not is_valid:
                raise ValueError(f"Material superficial detectado na peça '{parent_obj.name}' ({msg}). "
                                 f"Para imprimir separadamente, utilize o modo de corte 'Material' "
                                 f"com profundidade, gerando um sólido real.")

        used_names: Set[str] = set()
        # Gravação no diretório de staging temporário
        for parent_obj, part in all_sub_parts:
            filename = sanitize_unique_filename(part.name, used_names, ext=".stl")
            stage_path = os.path.join(temp_stage_dir, filename)
            
            bpy.ops.object.select_all(action='DESELECT')
            part.select_set(True)
            bpy.context.view_layer.objects.active = part

            if hasattr(bpy.ops.wm, "stl_export"):
                res = bpy.ops.wm.stl_export(
                    filepath=stage_path,
                    export_selected_objects=True,
                    global_scale=unit_scale,
                    use_scene_unit=False,
                    apply_modifiers=True,
                )
                if 'FINISHED' not in res:
                    raise RuntimeError(f"Exportador STL nativo falhou para '{part.name}'")
            else:
                res = bpy.ops.export_mesh.stl(
                    filepath=stage_path,
                    use_selection=True,
                    global_scale=unit_scale,
                    use_scene_unit=False,
                )
                if 'FINISHED' not in res:
                    raise RuntimeError(f"Exportador STL clássico falhou para '{part.name}'")

            if not os.path.exists(stage_path) or os.path.getsize(stage_path) == 0:
                raise RuntimeError(f"Exportação falhou: arquivo vazio ou ausente para '{part.name}' ({filename})")

            staged_files.append((stage_path, filename))

        # Sucesso completo de todos os arquivos: publicação atômica para o diretório de destino
        exported_files = publish_staged_files_atomic(staged_files, output_dir)

    finally:
        # Limpa staging temporário
        if os.path.exists(temp_stage_dir):
            try:
                shutil.rmtree(temp_stage_dir)
            except OSError:
                pass

        # Limpa objetos temporários da coleção
        for o in list(temp_col.objects):
            m = o.data
            temp_col.objects.unlink(o)
            bpy.data.objects.remove(o, do_unlink=True)
            if m and m.users == 0:
                bpy.data.meshes.remove(m, do_unlink=True)
        if temp_col.name in bpy.context.scene.collection.children:
            bpy.context.scene.collection.children.unlink(temp_col)
        bpy.data.collections.remove(temp_col)

        # Restaura contexto anterior de seleção e ativo
        if bpy.context:
            for o in bpy.context.selected_objects:
                o.select_set(False)
            for o in prev_selected:
                if o.name in bpy.data.objects:
                    o.select_set(True)
            if prev_active and prev_active.name in bpy.data.objects:
                bpy.context.view_layer.objects.active = prev_active

    return exported_files

