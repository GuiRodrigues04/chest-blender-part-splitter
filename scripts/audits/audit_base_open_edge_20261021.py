import bpy, sys, json, bmesh
from pathlib import Path

ROOT=Path(r'C:\Users\guiro\.gemini\antigravity\scratch\chest-blender-part-splitter')
OUT=ROOT/'evidence'/'commercial_cube_20261021'/'base_open_edge_repro.json'
BLEND=Path(r'C:\Users\guiro\OneDrive\Desktop\Placas - Modelos 3D\Modelos_Chest\Modelos Versão 1 - Placas Inteiras\Blender\Placa_Arco_Chest_Inteira.blend')
sys.path.insert(0,str(ROOT))
import src
src.register()
bpy.ops.wm.open_mainfile(filepath=str(BLEND))
import src.geometry_material as gm
from src.geometry_plane import evaluate_bmesh_metrics as original_metrics

captured=[]
def inspect_metrics(bm,scale):
    open_edges=[]
    for e in bm.edges:
        if not e.is_manifold:
            linked=list(e.link_faces)
            open_edges.append({
                'edge_index':e.index,'linked_face_count':len(linked),
                'vertex_indices':[v.index for v in e.verts],
                'vertices_world_mm':[[round(float(c*scale),9) for c in v.co] for v in e.verts],
                'linked_faces':[{'index':f.index,'material_index':f.material_index,
                    'area_mm2':float(f.calc_area()*scale*scale),
                    'normal_world':[round(float(c),9) for c in f.normal],
                    'vertex_indices':[v.index for v in f.verts],
                    'center_world_mm':[round(float(c*scale),9) for c in f.calc_center_median()]}
                    for f in linked],
                'edge_length_mm':float(e.calc_length()*scale),
            })
    m=original_metrics(bm,scale)
    captured.append({'face_count':len(bm.faces),'edge_count':len(bm.edges),
                     'non_manifold_edge_count':len(open_edges),'non_manifold_edges':open_edges,
                     'metrics':m})
    return m
gm.evaluate_bmesh_metrics=inspect_metrics
obj=bpy.data.objects['Placa_Arco_Chest_Inteira']
try:
    res=gm.slice_mesh_by_material(obj,1,depth_mm=2.0,scene=bpy.context.scene,
        region_index=0,extraction_mode='BASE',part_clearance_mm=0.0)
    result={'status':'UNEXPECTED_PASS','parts':[inspect_metrics(res.bm_a,1000),inspect_metrics(res.bm_b,1000)]}
    res.bm_a.free();res.bm_b.free()
except Exception as e:
    result={'status':'REPRODUCED_REJECTION','error':repr(e),'message':str(e),'evaluations':captured}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
print('BASE_OPEN_EDGE_REPRO',json.dumps(result,ensure_ascii=False,default=str))
