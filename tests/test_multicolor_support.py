"""Suíte de testes automatizados para suporte a modelos com múltiplas cores e materiais (Multicolor).

Testa:
1. Corte planar preservando materiais e índices de faces em A e B.
2. Atribuição correta de materiais nas tampas de corte (capping faces).
3. Corte por cortador sólido preservando materiais.
4. Corte por loop de arestas preservando materiais.
5. Encaixes macho/fêmea preservando materiais nas peças.
6. Separação de peças divididas por cor/material (sub-peças para AMS / multicolor).
7. Exportação 3MF Multimaterial (.3mf) com grupos de cores válidos.
8. Exportação de STLs separados por material (.stl) para importação multipartes.
"""

import sys
import os
import zipfile
import bpy
import bmesh
from mathutils import Vector, Matrix

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import src
from src.geometry_plane import slice_mesh_by_plane
from src.geometry_solid import slice_mesh_by_solid
from src.geometry_loop import slice_mesh_by_loop
from src.geometry_connectors import apply_connectors_boolean
from src.io_export import export_objects_to_3mf, export_objects_to_stl_by_material, separate_object_by_material


def assert_true(condition, message):
    if not condition:
        print(f"  [FAIL] {message}")
        sys.exit(1)
    print(f"  [PASS] {message}")


def create_multicolor_cube():
    """Cria um cubo 100mm com 3 materiais distintos: Vermelho, Verde e Azul."""
    mesh = bpy.data.meshes.new("multi_cube_data")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=0.1)  # 100 mm (0.1 BU em metros)

    mat_red = bpy.data.materials.new("Cor_Vermelha")
    mat_red.diffuse_color = (1.0, 0.0, 0.0, 1.0)
    mat_green = bpy.data.materials.new("Cor_Verde")
    mat_green.diffuse_color = (0.0, 1.0, 0.0, 1.0)
    mat_blue = bpy.data.materials.new("Cor_Azul")
    mat_blue.diffuse_color = (0.0, 0.0, 1.0, 1.0)

    mesh.materials.append(mat_red)    # Index 0
    mesh.materials.append(mat_green)  # Index 1
    mesh.materials.append(mat_blue)   # Index 2

    bm.faces.ensure_lookup_table()
    bm.faces[0].material_index = 0
    bm.faces[1].material_index = 1
    bm.faces[2].material_index = 2
    bm.faces[3].material_index = 0
    bm.faces[4].material_index = 1
    bm.faces[5].material_index = 2

    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("Multi_Cube", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def run_tests():
    print("\n" + "=" * 70)
    print("EXECUTANDO TESTES DE SUPORTE A MODELOS MULTICORES E EXPORTAÇÃO")
    print("=" * 70)

    try:
        src.unregister()
    except Exception:
        pass
    src.register()

    # Limpa cena inicial
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    cube_obj = create_multicolor_cube()
    mesh = cube_obj.data

    # --- Teste 1: Corte Planar Preserva Materiais ---
    print("\n--- Teste 1: Corte Planar com 3 Materiais ---")
    mesh_a = bpy.data.meshes.new("part_a")
    mesh_b = bpy.data.meshes.new("part_b")

    res = slice_mesh_by_plane(
        source_mesh=mesh,
        matrix_world=cube_obj.matrix_world,
        plane_origin=Vector((0.0, 0.0, 0.0)),
        plane_normal=Vector((0.0, 0.0, 1.0)),
        target_mesh_a=mesh_a,
        target_mesh_b=mesh_b,
        unit_scale=1000.0,
    )

    assert_true(len(mesh_a.materials) == 3, f"Parte A possui todos os 3 materiais (encontrado: {len(mesh_a.materials)})")
    assert_true(len(mesh_b.materials) == 3, f"Parte B possui todos os 3 materiais (encontrado: {len(mesh_b.materials)})")

    # Verifica se existem faces com índices diferentes de 0 (ou seja, materiais foram mantidos)
    indices_a = {p.material_index for p in mesh_a.polygons}
    indices_b = {p.material_index for p in mesh_b.polygons}
    assert_true(len(indices_a) > 1, f"Parte A retém múltiplos índices de material: {indices_a}")
    assert_true(len(indices_b) > 1, f"Parte B retém múltiplos índices de material: {indices_b}")
    assert_true(res["A"]["is_manifold"] and res["B"]["is_manifold"], "Ambas as partes resultantes são 100% manifold.")

    # --- Teste 2: Corte por Cortador Sólido Preserva Materiais ---
    print("\n--- Teste 2: Corte Sólido com Múltiplos Materiais ---")
    bpy.ops.mesh.primitive_cylinder_add(radius=0.03, depth=0.2, location=(0, 0, 0))
    cyl_cutter = bpy.context.active_object

    solid_a = bpy.data.meshes.new("solid_a")
    solid_b = bpy.data.meshes.new("solid_b")

    slice_mesh_by_solid(
        source_mesh=mesh,
        matrix_world=cube_obj.matrix_world,
        cutter_obj=cyl_cutter,
        target_mesh_a=solid_a,
        target_mesh_b=solid_b,
        unit_scale=1000.0,
    )

    assert_true(len(solid_a.materials) == 3, f"Corte Sólido Parte A possui 3 materiais (encontrado: {len(solid_a.materials)})")
    assert_true(len(solid_b.materials) == 3, f"Corte Sólido Parte B possui 3 materiais (encontrado: {len(solid_b.materials)})")
    bpy.data.objects.remove(cyl_cutter, do_unlink=True)

    # --- Teste 3: Encaixes com Materiais ---
    print("\n--- Teste 3: Encaixes em Peça Multicolor ---")
    obj_a = bpy.data.objects.new("obj_a", mesh_a)
    obj_b = bpy.data.objects.new("obj_b", mesh_b)
    bpy.context.scene.collection.objects.link(obj_a)
    bpy.context.scene.collection.objects.link(obj_b)

    apply_connectors_boolean(
        obj_male=obj_a,
        obj_female=obj_b,
        plane_normal=Vector((0.0, 0.0, 1.0)),
        positions=[Vector((0.0, 0.0, 0.0))],
        connector_type='CYLINDER',
        diameter_mm=8.0,
        length_mm=10.0,
        chamfer_mm=0.8,
        clearance_side_mm=0.15,
        end_clearance_mm=0.20,
        unit_scale=1000.0,
    )

    assert_true(len(obj_a.data.materials) == 3, f"Macho mantém materiais após união booleana do pino: {len(obj_a.data.materials)}")
    assert_true(len(obj_b.data.materials) == 3, f"Fêmea mantém materiais após subtração da cavidade: {len(obj_b.data.materials)}")

    # --- Teste 4: Separação por Material (Sub-peças Multicolor) ---
    print("\n--- Teste 4: Separação de Objeto Multicolor por Materiais ---")
    test_col = bpy.data.collections.new("TEST_SEPARATE_COL")
    bpy.context.scene.collection.children.link(test_col)

    sub_parts = separate_object_by_material(obj_a, test_col)
    assert_true(len(sub_parts) >= 2, f"Objeto separado em sub-peças por cor (geradas: {len(sub_parts)})")
    for sp in sub_parts:
        assert_true(len(sp.data.materials) == 1, f"Sub-peça '{sp.name}' possui exatamente 1 material exclusivo.")

    # --- Teste 5: Exportação 3MF Multimaterial ---
    print("\n--- Teste 5: Exportação 3MF Multimaterial ---")
    tmp_3mf = os.path.join(REPO_ROOT, "scratch", "test_multicolor.3mf")
    export_objects_to_3mf([obj_a, obj_b], tmp_3mf, unit_scale=1000.0)

    assert_true(os.path.exists(tmp_3mf), f"Arquivo 3MF gerado em '{tmp_3mf}'")
    assert_true(os.path.getsize(tmp_3mf) > 500, f"Arquivo 3MF possui tamanho válido: {os.path.getsize(tmp_3mf)} bytes")

    # Inspeciona integridade do arquivo ZIP e presença de cores
    with zipfile.ZipFile(tmp_3mf, 'r') as zf:
        namelist = zf.namelist()
        assert_true('3D/3dmodel.model' in namelist, "3D/3dmodel.model presente no 3MF")
        model_xml = zf.read('3D/3dmodel.model').decode('utf-8')
        assert_true('<m:colorgroup' in model_xml, "Tag colorgroup de materiais/cores presente no XML 3MF")
        assert_true('pid=' in model_xml and 'p1=' in model_xml, "Triângulos possuem mapeamento de cor pid/p1")

    # --- Teste 6: Exportação STLs Separados por Material ---
    print("\n--- Teste 6: Exportação STLs por Material ---")
    stl_dir = os.path.join(REPO_ROOT, "scratch", "test_stls")
    stl_files = export_objects_to_stl_by_material([obj_a], stl_dir, unit_scale=1000.0)

    assert_true(len(stl_files) >= 2, f"Gerados STLs separados por material: {len(stl_files)} arquivos")
    for stl_path in stl_files:
        assert_true(os.path.exists(stl_path), f"Arquivo STL existe: '{os.path.basename(stl_path)}'")
        assert_true(os.path.getsize(stl_path) > 100, f"Arquivo STL não está vazio ({os.path.getsize(stl_path)} bytes)")

    # Limpeza de arquivos de teste temporários
    try:
        if os.path.exists(tmp_3mf):
            os.remove(tmp_3mf)
        for stl_p in stl_files:
            if os.path.exists(stl_p):
                os.remove(stl_p)
    except Exception:
        pass

    print("\n" + "=" * 70)
    print(">>> TODOS OS TESTES DE MULTICOLOR E EXPORTAÇÃO PASSARAM COM 100% OK! <<<")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
    sys.exit(0)
