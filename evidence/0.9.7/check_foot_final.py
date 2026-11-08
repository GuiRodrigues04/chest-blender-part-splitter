import bpy,bmesh,sys,json,traceback
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
import src;src.register()
from src.geometry_loop import slice_mesh_by_loop
file=Path.home()/'OneDrive/Desktop/Modelos 3D e testes extensao/02_Personagens_e_Criaturas/spot/spot/Vaquinha pos cortes.blend'
results=[]
for gap,side in [(0.,'PART'),(.1,'PART'),(.2,'PART'),(.5,'PART'),(1.,'PART'),(.1,'CAVITY'),(.1,'BOTH'),(1.,'CAVITY'),(1.,'BOTH')]:
 bpy.ops.wm.open_mainfile(filepath=str(file));scene=bpy.context.scene;s=scene.chest_splitter;obj=s.target_object
 ids=[int(i) for i in s.loop_vertex_indices.split(',')]
 row=dict(gap=gap,side=side)
 try:
  r=slice_mesh_by_loop(obj,obj.name,ids,s.loop_seed_face_index,scene,part_clearance_mm=gap,part_clearance_apply_to=side)
  row.update(status='OK',closure=r.interface.closure_strategy,strategy=getattr(r.interface,'clearance_strategy','OFFSET'),
   measurements=getattr(r.interface,'clearance_measurements',None),
   patches=[r.interface.final_contact_a is not None,r.interface.final_contact_b is not None],
   bad=[sum(not e.is_manifold for e in bm.edges) for bm in r])
  for bm in r:bm.free()
 except Exception as e:row.update(status='ERROR',error=str(e),traceback=traceback.format_exc())
 results.append(row);print(json.dumps(row),flush=True)
(Path(__file__).parent/'foot_results_final.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
