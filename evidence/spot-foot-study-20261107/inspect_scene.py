import bpy,bmesh,sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
import src;src.register()
file=Path(r'C:\Users\guiro\OneDrive\Desktop\Vaquinha pos cortes.blend')
if not file.exists():file=Path(r'C:\Users\guiro\OneDrive\Desktop\Modelos 3D e testes extensao\02_Personagens_e_Criaturas\spot\spot\Vaquinha pos cortes.blend')
bpy.ops.wm.open_mainfile(filepath=str(file))
scene=bpy.context.scene;s=scene.chest_splitter
print('UNITS',scene.unit_settings.system,scene.unit_settings.scale_length,flush=True)
settings={}
for prop in s.bl_rna.properties:
 k=prop.identifier
 if any(word in k for word in ('loop','clearance','target','session','connector_enabled','last_status')):
  v=getattr(s,k)
  if isinstance(v,bpy.types.Object):v=v.name
  elif not isinstance(v,(str,int,float,bool,type(None))):v=str(v)
  settings[k]=v
print('SETTINGS',json.dumps(settings,ensure_ascii=False),flush=True)
for o in bpy.data.objects:
 if o.type!='MESH':continue
 bm=bmesh.new();bm.from_mesh(o.data);bm.transform(o.matrix_world)
 print('OBJECT',o.name,'VF',len(bm.verts),len(bm.faces),'DIMS',tuple(o.dimensions),'SCALE',tuple(o.scale),'BAD',sum(not e.is_manifold for e in bm.edges),'VOLUME',abs(bm.calc_volume())*1e9,'CUSTOM',str(dict(o.items())),flush=True);bm.free()
for op in scene.chest_operations:
 print('OP',op.operation_id,op.status,'target',op.target_name,'snapshot',op.snapshot_object.name if op.snapshot_object else None,flush=True)
(Path(__file__).parent/'settings.json').write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding='utf-8')
