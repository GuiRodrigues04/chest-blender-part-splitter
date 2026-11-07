import bpy,bmesh,sys,json,traceback
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
import src;src.register()
from src import geometry_loop as gl,geometry_clearance as gc
file=Path(r'C:\Users\guiro\OneDrive\Desktop\Vaquinha pos cortes.blend')
if not file.exists():file=Path(r'C:\Users\guiro\OneDrive\Desktop\Modelos 3D e testes extensao\02_Personagens_e_Criaturas\spot\spot\Vaquinha pos cortes.blend')
bpy.ops.wm.open_mainfile(filepath=str(file))
s=bpy.context.scene.chest_splitter;obj=s.target_object
if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
ids=[int(i) for i in s.loop_vertex_indices.split(',')];seed=s.loop_seed_face_index
results=[]
for method in ('current','direct_surface'):
 for gap in (0.,.1,1.):
  row=dict(method=method,gap_mm=gap)
  def step(*a,**kw):return None if method=='direct_surface' else original_step(*a,**kw)
  original_step=gl.build_stepped_cap_triangles
  try:
   with patch.object(gl,'build_stepped_cap_triangles',step):
    parts=gl.slice_mesh_by_loop(obj,obj.name,ids,seed,bpy.context.scene,part_clearance_mm=gap)
   row['parts']=[]
   for label,bm in zip(('foot','body'),parts):
    marker=bm.faces.layers.int.get('splitter_contact_surface');caps=[f for f in bm.faces if marker and f[marker]]
    row['parts'].append(dict(vertices=len(bm.verts),faces=len(bm.faces),bad_edges=sum(not e.is_manifold for e in bm.edges),volume_mm3=abs(bm.calc_volume())*1e9,cap_faces=len(caps),cap_quads=sum(len(f.verts)==4 for f in caps)))
    if gap==0:
     mesh=bpy.data.meshes.new('study');bm.to_mesh(mesh);new=bpy.data.objects.new(method+'_'+label,mesh);bpy.context.scene.collection.objects.link(new);new.hide_set(True)
    bm.free()
   row['status']='OK'
  except Exception as error:
   row.update(status='ERROR',error=str(error),traceback=traceback.format_exc())
  results.append(row);print('RESULT',json.dumps(row,ensure_ascii=False),flush=True)
(Path(__file__).parent/'initial_results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(Path(__file__).parent/'initial_comparison.blend'))
