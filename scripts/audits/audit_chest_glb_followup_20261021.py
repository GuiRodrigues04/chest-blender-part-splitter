"""Final targeted Chest GLB MATERIAL EXTRUDE regression on the integrated fix."""
import json,sys,traceback
from pathlib import Path
import bpy,bmesh
ROOT=Path(__file__).resolve().parents[2]
GLB=Path(r"C:\Users\guiro\OneDrive\Desktop\Placas - Modelos 3D\Modelos_Chest\Modelos Versão 1 - Placas Inteiras\Placa_Chest_Inteira.glb")
OUT=ROOT/'evidence'/'commercial_plates_glb_20261021'/'chest_glb_followup.json'
sys.path.insert(0,str(ROOT));import src
from src.geometry_material import slice_mesh_by_material
from src.diagnostic import validate_bmesh_mesh_geometry
from src.operators import get_current_session_parts,verify_preview_current
src.register()
def snapshot(obj):
  return (tuple(tuple(float(x) for x in v.co) for v in obj.data.vertices),
          tuple(tuple(p.vertices) for p in obj.data.polygons),
          tuple(p.material_index for p in obj.data.polygons))
def mesh_stats(bm):
  bm.normal_update();r=validate_bmesh_mesh_geometry(bm,1000)
  return {'verts':len(bm.verts),'edges':len(bm.edges),'faces':len(bm.faces),
    'volume_mm3':abs(bm.calc_volume())*1e9,'valid':r['is_valid'],'manifold':r['is_manifold'],
    'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges)}
def part_stats(parts):
  out=[]
  for p in parts:
    bm=bmesh.new();bm.from_mesh(p.data);bm.transform(p.matrix_world)
    try:
      s=mesh_stats(bm);s['object']=p.name;out.append(s)
    finally:bm.free()
  return out
records=[]
for mi,gap in ((0,0.0),(0,0.1),(1,0.1)):
  case={'file':GLB.name,'material_index':mi,'region_index':0,'extraction_mode':'EXTRUDE','depth_mm':2.0,
        'requested_gap_mm':gap,'apply_to':'PART','connectors':False,'pins':False}
  try:
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.scale_length=1
    imp=bpy.ops.import_scene.gltf(filepath=str(GLB));obj=next(o for o in bpy.context.scene.objects if o.type=='MESH')
    raw= snapshot(obj)
    case['import_operator']=str(imp);case['raw']={'verts':len(obj.data.vertices),'faces':len(obj.data.polygons)}
    from src.diagnostic import validate_bmesh_mesh_geometry
    def count_open(target):
      bm=bmesh.new();bm.from_mesh(target.data)
      try:return sum(not e.is_manifold for e in bm.edges)
      finally:bm.free()
    case['raw']['nonmanifold_edges']=count_open(obj)
    s=bpy.context.scene.chest_splitter;s.target_object=obj
    case['repair_operator']=str(bpy.ops.chest.splitter_repair_target_mesh())
    case['repair_message']=s.get_localized_status()
    case['repaired']={'verts':len(obj.data.vertices),'faces':len(obj.data.polygons),'nonmanifold_edges':count_open(obj)}
    source=snapshot(obj)

    # Exercise the core geometry directly with the same parameters used by
    # the paired BLEND regression, then prove both returned BMeshes are solids.
    direct=None
    try:
      direct=slice_mesh_by_material(obj,mi,region_index=0,depth_mm=2.0,extraction_mode='EXTRUDE',part_clearance_mm=gap,part_clearance_apply_to='PART')
      case['direct_geometry']={'parts':[mesh_stats(bm) for bm in direct], 'closed_solid_pair':len(direct)==2 and all(x['valid'] and x['manifold'] and x['volume_mm3']>0 for x in [mesh_stats(bm) for bm in direct])}
    except Exception as exc:
      case['direct_geometry']={'exception':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc(limit=4)}
    finally:
      if direct:
        for bm in direct:bm.free()
    case['source_unchanged_after_direct']=snapshot(obj)==source

    # Exercise the shipped preview/commit/revert operators too.
    s.split_mode='MATERIAL';s.material_split_index=mi;s.material_region_index=0
    s.material_extraction_mode='EXTRUDE';s.material_extrude_depth_mm=2.0
    s.assembly_clearance_preset='NONE';s.part_clearance_mm=gap
    s.part_clearance_apply_to='PART';s.part_clearance_bottom_enable=False
    s.connector_enabled=False;s.commit_next_target='NONE'
    case['effective_gap_mm']=float(s.part_clearance_mm)
    case['effective_bottom_gap_mm']=float(s.part_clearance_bottom_mm if s.part_clearance_bottom_enable else s.part_clearance_mm)
    case['configuration_matches']=abs(case['effective_gap_mm']-gap)<1e-6
    op=bpy.ops.chest.splitter_generate_preview();case['preview_operator']=str(op);case['status']=s.session_status;case['message']=s.get_localized_status()
    parts=get_current_session_parts(bpy.context.scene);case['preview_current']=verify_preview_current(bpy.context)[0]
    case['preview_parts']=part_stats(parts)
    case['closed_solid_preview']=len(parts)==2 and all(p['valid'] and p['manifold'] and p['volume_mm3']>0 for p in case['preview_parts'])
    case['source_unchanged_after_preview']=snapshot(obj)==source
    if case['closed_solid_preview']:
      case['source_volume_mm3']=sum(x['volume_mm3'] for x in case['direct_geometry'].get('parts',[])) if False else None
      bm=bmesh.new();bm.from_mesh(obj.data)
      try:case['source_volume_mm3']=abs(bm.calc_volume())*1e9
      finally:bm.free()
      case['preview_volume_mm3']=sum(x['volume_mm3'] for x in case['preview_parts'])
      case['volume_delta_mm3']=case['preview_volume_mm3']-case['source_volume_mm3']
      case['commit_operator']=str(bpy.ops.chest.splitter_commit_parts())
      case['source_unchanged_after_commit']=snapshot(obj)==source
      opid=s.active_operation_id or s.session_id
      case['revert_operator']=str(bpy.ops.chest.splitter_revert_cut(operation_id=opid))
      case['source_unchanged_after_revert']=snapshot(obj)==source
  except Exception as exc:
    case['exception']=type(exc).__name__+': '+str(exc);case['traceback']=traceback.format_exc(limit=6)
  records.append(case);print(json.dumps(case,ensure_ascii=False,default=str),flush=True)
OUT.write_text(json.dumps({'blender':bpy.app.version_string,'glb':str(GLB),'cases':records},indent=2,ensure_ascii=False,default=str),encoding='utf-8')
