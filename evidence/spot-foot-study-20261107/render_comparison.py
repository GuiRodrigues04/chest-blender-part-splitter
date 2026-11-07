import bpy,bmesh,sys
from pathlib import Path
from mathutils import Vector
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root))
import src;src.register()
from src.geometry_material import _get_orthonormal_basis
folder=Path(__file__).parent
bpy.ops.wm.open_mainfile(filepath=str(folder/'refined_comparison.blend'))
scene=bpy.context.scene
for obj in scene.objects:obj.hide_render=True
reference=bpy.data.objects['direct_surface_foot']
bm=bmesh.new();bm.from_mesh(reference.data);layer=bm.faces.layers.int.get('splitter_contact_surface')
cap=[f for f in bm.faces if f[layer]]
normal=sum((f.normal*f.calc_area() for f in cap),Vector()).normalized()
center=sum((v.co for v in set(v for f in cap for v in f.verts)),Vector())/len(set(v for f in cap for v in f.verts));bm.free()
u,v=_get_orthonormal_basis(normal)
focus=center-normal*.13
bpy.ops.object.camera_add(location=focus+normal*.8+u*.5+v*.12)
camera=bpy.context.object;camera.rotation_euler=(focus-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=.62;scene.camera=camera
scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL'
scene.display.shading.show_cavity=True;scene.display.shading.cavity_type='BOTH'
scene.render.resolution_x=1000;scene.render.resolution_y=900;scene.render.resolution_percentage=100
gray=bpy.data.materials.new('Exterior');gray.diffuse_color=(.48,.48,.48,1)
orange=bpy.data.materials.new('Superficie de corte');orange.diffuse_color=(.85,.3,.05,1)
for name,label in [('current_foot','atual_sem_folga'),('foot_refined_1.0_3','prototipo_folga_1mm')]:
 obj=bpy.data.objects[name];obj.hide_set(False);obj.hide_render=False
 obj.data.materials.clear();obj.data.materials.append(gray);obj.data.materials.append(orange)
 attr=obj.data.attributes.get('splitter_contact_surface')
 for f in obj.data.polygons:f.material_index=int(attr is not None and attr.data[f.index].value!=0)
 scene.render.filepath=str(folder/(label+'.png'));bpy.ops.render.render(write_still=True)
 obj.hide_render=True;obj.hide_set(True)
