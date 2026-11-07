"""Compare QR GLB after safe repair with its closed BLEND for FDM clearance."""
import json,sys,traceback
from pathlib import Path
import bpy,bmesh
ROOT=Path(__file__).resolve().parents[2]
BASE=Path(r"C:\Users\guiro\OneDrive\Desktop\Placas - Modelos 3D\Modelos_Chest\Modelos Versão 1 - Placas Inteiras")
GLB=BASE/'Placa_QR_Inclinada_Chest_Inteira.glb'
BLEND=BASE/'Blender'/'Placa_QR_Inclinada_Chest_Inteira.blend'
OUT=ROOT/'evidence'/'commercial_plates_glb_20261021'/'qr_fdm_glb_vs_blend.json'
sys.path.insert(0,str(ROOT));import src
from src.geometry_material import slice_mesh_by_material,analyze_material_structure
from src.diagnostic import validate_bmesh_mesh_geometry
src.register()
def load(kind):
  bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.scale_length=1
  if kind=='GLB':
    bpy.ops.import_scene.gltf(filepath=str(GLB));obj=next(o for o in bpy.context.scene.objects if o.type=='MESH')
    before={"verts":len(obj.data.vertices),"faces":len(obj.data.polygons),"nonmanifold":edge_count(obj)}
    bpy.context.scene.chest_splitter.target_object=obj
    op=bpy.ops.chest.splitter_repair_target_mesh()
    repair={"operator":str(op),"message":bpy.context.scene.chest_splitter.get_localized_status()}
  else:
    with bpy.data.libraries.load(str(BLEND),link=False) as (a,b):
      names=[n for n in a.objects if n and 'Placa_QR_Inclinada_Chest_Inteira' in n]
      b.objects=[names[0]]
    obj=b.objects[0];bpy.context.scene.collection.objects.link(obj)
    bpy.context.scene.chest_splitter.target_object=obj
    before={"verts":len(obj.data.vertices),"faces":len(obj.data.polygons),"nonmanifold":edge_count(obj)}
    # The paired BLEND is watertight but carries tiny collinear faces; exercise
    # the extension's explicit repair path, as in the existing QR regression.
    op=bpy.ops.chest.splitter_repair_target_mesh()
    repair={"operator":str(op),"message":bpy.context.scene.chest_splitter.get_localized_status()}
  return obj,before,repair
def edge_count(obj):
  bm=bmesh.new();bm.from_mesh(obj.data)
  try:return sum(not e.is_manifold for e in bm.edges)
  finally:bm.free()
def source_signature(obj):return (tuple(tuple(v.co) for v in obj.data.vertices),tuple(tuple(p.vertices) for p in obj.data.polygons),tuple(p.material_index for p in obj.data.polygons))
records=[]
for kind in ('GLB','BLEND'):
  obj,before,repair=load(kind)
  s=bpy.context.scene.chest_splitter
  rec={'source':kind,'before_repair':before,'repair':repair,'after_repair':{'verts':len(obj.data.vertices),'faces':len(obj.data.polygons),'nonmanifold':edge_count(obj)},'material_slots':len(obj.data.materials)}
  a=analyze_material_structure(obj,0,0)
  rec['region0']={k:a.get(k) for k in ('valid','error','region_face_count','boundary_loops','has_holes','area_mm2')}
  src_sig=source_signature(obj)
  rec['cases']=[]
  for depth,gap in ((.1,0.0),(5.0,.1)):
    c={'depth_mm':depth,'gap_mm':gap}
    try:
      result=slice_mesh_by_material(obj,0,depth_mm=depth,extraction_mode='EXTRUDE',part_clearance_mm=gap)
      c['parts']=[]
      for bm in result:
        bm.normal_update();r=validate_bmesh_mesh_geometry(bm,1000)
        c['parts'].append({'verts':len(bm.verts),'faces':len(bm.faces),'volume_mm3':abs(bm.calc_volume())*1e9,'manifold':r['is_manifold'],'valid':r['is_valid'],'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges)})
      c['success']=len(c['parts'])==2 and all(p['manifold'] and p['valid'] and p['volume_mm3']>0 for p in c['parts'])
      c['total_volume_mm3']=sum(p['volume_mm3'] for p in c['parts'])
      for bm in result:bm.free()
    except Exception as exc:
      c['success']=False;c['exception']=type(exc).__name__+': '+str(exc);c['traceback']=traceback.format_exc(limit=5)
    c['source_unchanged']=source_signature(obj)==src_sig
    rec['cases'].append(c)
  records.append(rec)
OUT.write_text(json.dumps({'files':records},indent=2,ensure_ascii=False,default=str),encoding='utf-8')
print(json.dumps({'files':records},indent=2,ensure_ascii=False,default=str))
