"""Actual standing-pose STL: finite guide, pins, partial rejection and saved example."""
import os,sys,json
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bpy,bmesh
from mathutils import Vector,Matrix
import src
from src.geometry_plane import slice_mesh_by_plane,reconstruct_boundary_loops,PlaneSliceError
from src.plane_region import PlaneRegion
from src.operators import ensure_plane_guide

src.register()
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
source=r'C:\Users\guiro\OneDrive\Documentos\ChatGPT\Extensão Blender\malhas-otimizadas\Pose04_leve_fiel.blend'
with bpy.data.libraries.load(source,link=False) as (available,loaded):loaded.objects=available.objects
obj=next(o for o in loaded.objects if o and o.type=='MESH')
scene=bpy.context.scene;scene.collection.objects.link(obj);bpy.context.view_layer.objects.active=obj;obj.select_set(True)
obj.data=obj.data.copy();obj.data.transform(obj.matrix_world);obj.matrix_world=Matrix.Identity(4);bpy.context.view_layer.update()
obj.name='Pose04_Teste_Area_Limitada'
factor=.2/max(obj.dimensions);obj.data.transform(Matrix.Scale(factor,4));obj.data.update();bpy.context.view_layer.update()
scene=bpy.context.scene;s=scene.chest_splitter;s.target_object=obj;s.split_mode='PLANE';s.connector_enabled=False;s.part_clearance_mm=0
corners=[obj.matrix_world@Vector(p) for p in obj.bound_box];lo=Vector(tuple(min(v[i] for v in corners) for i in range(3)));hi=Vector(tuple(max(v[i] for v in corners) for i in range(3)))
found=None
for axis in (2,1,0):
    n=Vector(tuple(int(i==axis) for i in range(3)));u=n.cross(Vector((1,0,0)) if axis!=0 else Vector((0,1,0))).normalized();v=n.cross(u).normalized()
    for frac in (.45,.55,.65,.35,.75):
        origin=(lo+hi)/2;origin[axis]=lo[axis]+(hi[axis]-lo[axis])*frac
        bm=bmesh.new();bm.from_mesh(obj.data)
        bis=bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),plane_co=origin,plane_no=n,dist=1e-7)
        loops=reconstruct_boundary_loops([e for e in bis.get('geom_cut',[]) if isinstance(e,bmesh.types.BMEdge)])
        bm.free()
        if len(loops)<2:continue
        for loop in sorted(loops,key=len):
            uu=[(p-origin).dot(u) for p in loop];vv=[(p-origin).dot(v) for p in loop]
            margin=.0006;u0,u1=min(uu)-margin,max(uu)+margin;v0,v1=min(vv)-margin,max(vv)+margin
            reg=PlaneRegion(tuple(origin+u*x+v*y for x,y in ((u0,v0),(u1,v0),(u1,v1),(u0,v1))))
            a=bpy.data.meshes.new('testA');b=bpy.data.meshes.new('testB')
            try:
                report=slice_mesh_by_plane(obj.data,obj.matrix_world,origin,n,a,b,plane_region=reg)
                assert report['A']['is_manifold'] and report['B']['is_manifold']
                if min(report['A']['volume_mm3'],report['B']['volume_mm3'])<.001:continue
                found=(origin,n,u,v,(u0,u1,v0,v1),report)
                break
            except PlaneSliceError:pass
            finally:bpy.data.meshes.remove(a);bpy.data.meshes.remove(b)
        if found:break
    if found:break
assert found,'No valid independent limb section found'
origin,n,u,v,bounds,report=found;u0,u1,v0,v1=bounds
guide=ensure_plane_guide(bpy.context)
# Set local guide X/Y to the tested affine footprint, normal Z to the cut normal.
mw=Matrix(((u.x,v.x,n.x,0),(u.y,v.y,n.y,0),(u.z,v.z,n.z,0),(0,0,0,1)))
mw.translation=origin+u*(u0+u1)/2+v*(v0+v1)/2
guide.matrix_world=mw;bpy.context.view_layer.update()
s.plane_extent_mode='LIMITED';s.plane_width_mm=(u1-u0)*1000;s.plane_height_mm=(v1-v0)*1000;bpy.context.view_layer.update()
assert bpy.ops.chest.splitter_generate_preview()=={'FINISHED'}
# Connector dimensions adapted to the real limb section.
smallest=min((u1-u0)*1000,(v1-v0)*1000)
s.connector_enabled=True;s.connector_distribution='CENTER';s.connector_diameter_mm=max(1,min(3,smallest*.15));s.connector_length_mm=3;s.connector_edge_margin_mm=.5
assert bpy.ops.chest.splitter_generate_preview()=={'FINISHED'}
assert s.session_status=='PREVIEW_VALID'
out=r'C:\Users\guiro\OneDrive\Documentos\ChatGPT\Extensão Blender\plano-limitado-0.8.19'
with open(os.path.join(out,'pose-real.json'),'w') as f:json.dump({'source':source,'axis':list(n),'guide_width_mm':s.plane_width_mm,'guide_height_mm':s.plane_height_mm,'A':report['A'],'B':report['B'],'connectors_preview':'passed'},f,indent=2)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'Exemplo_Pose04_Area_Limitada.blend'))
print('REAL_POSE_LIMITED_AND_CONNECTOR_PASS',flush=True)
