"""Probe EXACT versus MANIFOLD connector booleans on Chest material preview."""
import json,sys,traceback
from pathlib import Path
import bpy,bmesh
ROOT=Path(__file__).resolve().parents[2]
BLEND=Path(r"C:\Users\guiro\OneDrive\Desktop\Placas - Modelos 3D\Modelos_Chest\Modelos Versão 1 - Placas Inteiras\Blender\Placa_Chest_Inteira.blend")
OUT=ROOT/'evidence'/'commercial_plates_blend_20261021'/'isolated'/'connector_solver_probe.json'
sys.path.insert(0,str(ROOT));import src;src.register()
from src.geometry_material import get_material_regions
from src.operators import get_current_session_parts,verify_preview_current
from src.diagnostic import validate_bmesh_mesh_geometry
import src.operators as ops
bpy.ops.wm.open_mainfile(filepath=str(BLEND))
scene=bpy.context.scene;s=scene.chest_splitter
obj=max((o for o in scene.objects if o.type=='MESH'),key=lambda o:len(o.data.polygons))
s.target_object=obj;bpy.context.view_layer.objects.active=obj
for o in bpy.context.selected_objects:o.select_set(False)
obj.select_set(True)
bm=bmesh.new();bm.from_mesh(obj.data)
try:region=set(get_material_regions(bm,0)[0])
finally:bm.free()
sig=(tuple(tuple(v.co) for v in obj.data.vertices),tuple(tuple(p.vertices) for p in obj.data.polygons),tuple(p.material_index for p in obj.data.polygons))
s.split_mode='LOOP';bpy.context.tool_settings.mesh_select_mode=(False,False,True);bpy.ops.object.mode_set(mode='EDIT')
ebm=bmesh.from_edit_mesh(obj.data);ebm.faces.ensure_lookup_table()
for f in ebm.faces:f.select_set(f.index in region)
ebm.faces.active=next((f for f in ebm.faces if f.select),None);ebm.select_flush_mode();bmesh.update_edit_mesh(obj.data)
capture=bpy.ops.chest.splitter_capture_face_boundary();bpy.ops.object.mode_set(mode='OBJECT')
s.split_mode='MATERIAL';s.material_split_index=0;s.material_region_index=0;s.material_extraction_mode='EXTRUDE';s.material_extrude_depth_mm=2
s.material_interface_mat_mode='EXTRACTED';s.assembly_clearance_preset='FDM';s.connector_enabled=True;s.connector_distribution='AUTO_SHAPE'
s.connector_diameter_mm=1.2;s.connector_length_mm=1.5;s.connector_chamfer_mm=.1;s.connector_edge_margin_mm=.4;s.commit_next_target='NONE'
record={'target':obj.name,'capture':str(capture),'captured':s.loop_is_captured,'profile':s.assembly_clearance_preset,
        'part_clearance_mm':s.part_clearance_mm,'bottom_clearance_mm':s.part_clearance_bottom_mm,
        'connector_diameter_mm':s.connector_diameter_mm,'connector_length_mm':s.connector_length_mm,
        'connector_chamfer_mm':s.connector_chamfer_mm,'connector_distribution':s.connector_distribution}
def run(label,force=None):
  original=ops.apply_connectors_boolean
  selected_solvers=[]
  def wrapped(*args,**kwargs):
    if force:kwargs['boolean_solver']=force
    selected=original(*args,**kwargs);selected_solvers.append(selected);return selected
  ops.apply_connectors_boolean=wrapped
  try:
    result=bpy.ops.chest.splitter_generate_preview();entry={'label':label,'result':str(result),'status':s.session_status,'message':s.get_localized_status()}
    entry['selected_connector_solvers']=selected_solvers
    parts=get_current_session_parts(scene);entry['preview_current']=verify_preview_current(bpy.context)[0]
    entry['parts']=[]
    for p in parts:
      bm=bmesh.new();bm.from_mesh(p.data)
      try:
        r=validate_bmesh_mesh_geometry(bm,1000)
        entry['parts'].append({'object':p.name,'verts':len(bm.verts),'faces':len(bm.faces),'volume_mm3':abs(bm.calc_volume())*1e9,
          'valid':r['is_valid'],'manifold':r['is_manifold'],'degenerate_faces':r['degenerate_faces'],'nonmanifold_edges':r['non_manifold_edges']})
      finally:bm.free()
    if result=={'FINISHED'}:
      entry['commit']=str(bpy.ops.chest.splitter_commit_parts());entry['revert']=str(bpy.ops.chest.splitter_revert_cut(operation_id=s.active_operation_id or s.session_id))
    entry['source_unchanged']=(sig==(tuple(tuple(v.co) for v in obj.data.vertices),tuple(tuple(p.vertices) for p in obj.data.polygons),tuple(p.material_index for p in obj.data.polygons)))
    return entry
  except Exception as exc:return {'label':label,'exception':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc(limit=6)}
  finally:
    ops.apply_connectors_boolean=original
record['exact']=run('existing exact')
if record['exact'].get('result')!="{'FINISHED'}":
  try:bpy.ops.chest.splitter_remove_preview()
  except Exception:pass
  record['manifold_retry_probe']=run('forced manifold',force='MANIFOLD')
OUT.write_text(json.dumps(record,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
print(json.dumps(record,indent=2,ensure_ascii=False,default=str))
