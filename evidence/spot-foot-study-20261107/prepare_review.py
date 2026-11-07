import bpy,bmesh,sys
from pathlib import Path
from mathutils import Vector
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
import src;src.register()
from src.geometry_material import _get_orthonormal_basis
folder=Path(__file__).parent
bpy.ops.wm.open_mainfile(filepath=str(folder/'refined_comparison.blend'))
original=bpy.context.scene;original.name='Fonte dos ensaios'
reference=bpy.data.objects['direct_surface_foot']
bm=bmesh.new();bm.from_mesh(reference.data);mark=bm.faces.layers.int.get('splitter_contact_surface')
cap=[f for f in bm.faces if f[mark]]
normal=sum((f.normal*f.calc_area() for f in cap),Vector()).normalized()
verts={v for f in cap for v in f.verts};center=sum((v.co for v in verts),Vector())/len(verts);bm.free()
u,v=_get_orthonormal_basis(normal)
for name,footname,bodyname,offset in [('Atual - sem folga - explodido','current_foot','current_body',.2031),
                              ('Lamina - 1 mm - montado','foot_refined_1.0_3','direct_surface_body',0.),
                              ('Lamina - 1 mm - explodido','foot_refined_1.0_3','direct_surface_body',.2031)]:
 scene=bpy.data.scenes.new(name);bpy.context.window.scene=scene;scene.unit_settings.system='METRIC'
 scene.unit_settings.length_unit='MILLIMETERS';scene.unit_settings.scale_length=1
 scene.display.shading.color_type='OBJECT'
 for source_name,label,color in ((footname,'Pe',(.75,.3,.08,1)),(bodyname,'Corpo',(.5,.5,.5,1))):
  source=bpy.data.objects[source_name];obj=bpy.data.objects.new(label,source.data.copy());scene.collection.objects.link(obj)
  obj.matrix_world=source.matrix_world.copy();obj.color=color
  if label=='Pe':
   obj.location-=normal*offset;obj['study_display_offset_mm']=offset*1000
   obj['study_requested_gap_mm']=1.0 if footname.startswith('foot_refined') else 0.0
   obj.select_set(True);bpy.context.view_layer.objects.active=obj
 scene['study_note']='Explosao apenas para visualizacao; para medir use a cena montada.' if offset else 'Pecas na posicao de montagem, sem deslocamento visual.'
 scene.world=bpy.data.worlds.new(name)
 for screen in bpy.data.screens:
  for area in screen.areas:
   if area.type=='VIEW_3D':
    area.spaces.active.shading.color_type='OBJECT'
    rv=area.spaces.active.region_3d;rv.view_location=center-normal*.08;rv.view_distance=1.1
    rv.view_rotation=(-normal-u*.6).to_track_quat('-Z','Y')
destination=Path(r'C:\Users\guiro\OneDrive\Documentos\ChatGPT\Extensão Blender\estudo-pe-spot-2026-11-07')
destination.mkdir(exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=str(destination/'Estudo_Pe_Spot.blend'))
