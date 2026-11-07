"""Save reviewer-friendly GLBs with successful MATERIAL and LOOP previews."""
import json,sys,traceback
from pathlib import Path
import bpy,bmesh
ROOT=Path(__file__).resolve().parents[2]
GLB_DIR=Path(r"C:\Users\guiro\OneDrive\Desktop\Placas - Modelos 3D\Modelos_Chest\Modelos Versão 1 - Placas Inteiras")
OUT=ROOT/'evidence'/'commercial_plates_glb_20261021'
sys.path.insert(0,str(ROOT));import src
from src.geometry_material import get_material_regions,analyze_material_structure
from src.operators import get_current_session_parts
src.register()
def nonmanifold(obj):
  bm=bmesh.new();bm.from_mesh(obj.data)
  try:return sum(not e.is_manifold for e in bm.edges)
  finally:bm.free()
records=[]
for stem in ('Placa_Arco_Chest_Inteira','Placa_Mesa_Chest_Inteira','Placa_Osso_Chest_V2_Inteira'):
  for mode in ('MATERIAL','LOOP'):
    rec={'file':stem+'.glb','mode':mode}
    try:
      bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.scale_length=1
      bpy.ops.import_scene.gltf(filepath=str(GLB_DIR/(stem+'.glb')))
      obj=next(o for o in bpy.context.scene.objects if o.type=='MESH')
      s=bpy.context.scene.chest_splitter;s.target_object=obj
      rec['raw_nonmanifold_edges']=nonmanifold(obj)
      repair=bpy.ops.chest.splitter_repair_target_mesh();rec['repair_operator']=str(repair)
      rec['repaired_nonmanifold_edges']=nonmanifold(obj)
      bm=bmesh.new();bm.from_mesh(obj.data)
      try:
        regions=get_material_regions(bm,0)
        viable=[]
        for ri in range(len(regions)):
          a=analyze_material_structure(obj,0,ri)
          if a.get('valid'):viable.append((len(regions[ri]),ri))
        if not viable:raise RuntimeError('No valid material region #0')
        region_index=max(viable)[1]
      finally:bm.free()
      s.connector_enabled=False;s.part_clearance_mm=0.1;s.part_clearance_apply_to='PART'
      s.assembly_clearance_preset='NONE';s.commit_next_target='NONE'
      s.material_split_index=0;s.material_region_index=region_index
      s.material_extraction_mode='EXTRUDE';s.material_extrude_depth_mm=1
      s.loop_behavior='AUTO';s.loop_extrude_depth_mm=1
      if mode=='LOOP':
        bpy.context.view_layer.objects.active=obj
        for o in bpy.context.selected_objects:o.select_set(False)
        obj.select_set(True);bpy.context.tool_settings.mesh_select_mode=(False,False,True)
        bpy.ops.object.mode_set(mode='EDIT')
        ebm=bmesh.from_edit_mesh(obj.data);ebm.faces.ensure_lookup_table()
        chosen=set(regions[region_index])
        for f in ebm.faces:f.select_set(f.index in chosen)
        bmesh.update_edit_mesh(obj.data)
        rec['capture_operator']=str(bpy.ops.chest.splitter_capture_face_boundary())
        rec['capture_loops']=len(json.loads(s.loop_boundary_loops))
        rec['capture_vertices']=s.loop_vertex_count
        bpy.ops.object.mode_set(mode='OBJECT')
        s.split_mode='LOOP'
      else:s.split_mode='MATERIAL'
      result=bpy.ops.chest.splitter_generate_preview()
      rec['preview_operator']=str(result);rec['message']=s.get_localized_status()
      parts=get_current_session_parts(bpy.context.scene)
      rec['parts']=[]
      for p in parts:
        bm=bmesh.new();bm.from_mesh(p.data)
        try:rec['parts'].append({'name':p.name,'faces':len(bm.faces),'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),'volume_mm3':abs(bm.calc_volume())*1e9})
        finally:bm.free()
      if len(parts)!=2 or not all(x['nonmanifold_edges']==0 and x['volume_mm3']>0 for x in rec['parts']):
        raise RuntimeError('Preview did not contain two closed positive-volume solids')
      path=OUT/(stem+'_'+mode+'_preview.blend')
      bpy.ops.wm.save_as_mainfile(filepath=str(path));rec['review_blend']=str(path)
    except Exception as e:
      rec['error']=type(e).__name__+': '+str(e);rec['traceback']=traceback.format_exc(limit=5)
    records.append(rec);print(json.dumps(rec,ensure_ascii=False),flush=True)
(OUT/'review_previews.json').write_text(json.dumps(records,indent=2,ensure_ascii=False),encoding='utf-8')
