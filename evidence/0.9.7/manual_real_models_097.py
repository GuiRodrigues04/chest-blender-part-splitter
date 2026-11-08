"""Small local real-model comparison. Does not save or modify the source files.

Blender --background --factory-startup --python-exit-code 1 --python this_file
-- /addon/root /models/root /output.json
"""
import sys, os, json, time
from pathlib import Path
import bpy, bmesh
from mathutils import Vector

addon_root, models_root, output = map(Path, sys.argv[sys.argv.index('--')+1:])
sys.path.insert(0,str(addon_root))
import src
src.register()
from src.geometry_region import slice_region, mesh_signature
from src.geometry_material import slice_mesh_by_material
from src.geometry_loop import slice_mesh_by_loop
from src import geometry_quad_cap
from src.geometry_plane import slice_mesh_by_plane
from src.diagnostic import get_scene_scale_to_mm

plate=models_root/'03_Testes_Extensao_e_Templates/01_Regiao_Inteira/01_Simples/Placa_4_Testes_Multicontatos.blend'
cat=models_root/'02_Personagens_e_Criaturas/Gato_Cinza/Teste Gato.blend'
spot=models_root/'02_Personagens_e_Criaturas/spot/spot/Vaquinha.blend'
cases=[('region_green',plate,'PLACA_ALVO','WHOLE',1,0),
       ('region_blue',plate,'PLACA_ALVO','WHOLE',2,0),
       ('plate_plane',plate,'PLACA_ALVO','PLANE',0,0),
       ('plate_material_depth',plate,'PLACA_ALVO','EXTRUDE',1,1),
       ('plate_material_base',plate,'PLACA_ALVO','BASE',1,0),
       ('cat_material',cat,'Gato Cinza Retopology','EXTRUDE',2,5),
       ('cat_plane',cat,'Gato Cinza Retopology','PLANE',0,0),
       ('spot_loop_zero',spot,'spot_quadrangulated','LOOP',0,0),
       ('spot_loop_gap',spot,'spot_quadrangulated','LOOP',0,.1)]

def metrics(mesh,scale):
    bm=bmesh.new()
    try:
        bm.from_mesh(mesh)
        return dict(vertices=len(bm.verts),faces=len(bm.faces),
                    nonmanifold_edges=sum(not e.is_manifold for e in bm.edges),
                    volume_mm3=abs(bm.calc_volume())*scale**3)
    finally:bm.free()

results=[]
for name,path,objname,mode,slot,value in cases:
    row=dict(case=name,mode=mode,file=str(path))
    start=time.time()
    meshes=[]
    try:
        bpy.ops.wm.open_mainfile(filepath=str(path))
        if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
        obj=bpy.data.objects[objname];scene=bpy.context.scene;scale=get_scene_scale_to_mm(scene)
        before=mesh_signature(obj.data)
        meshes=[bpy.data.meshes.new('Regression A'),bpy.data.meshes.new('Regression B')]
        if mode=='WHOLE':
            s=scene.chest_splitter;s.target_object=obj;s.region_target=obj;s.split_mode='MATERIAL'
            s.material_extraction_mode='WHOLE';s.material_split_index=slot;s.material_region_index=0
            s.part_clearance_mm=0;s.part_clearance_bottom_enable=False;s.connector_enabled=False;s.invert_sides=False
            s.region_face_indices=','.join(str(f.index) for f in obj.data.polygons if f.material_index==slot)
            s.region_mesh_signature=before
            report=slice_region(obj,s,scene,*meshes)
            row['contacts']=len(report.get('contact_choices',[]))
        elif mode=='PLANE':
            points=[obj.matrix_world@v.co for v in obj.data.vertices]
            center=Vector(tuple((min(p[i] for p in points)+max(p[i] for p in points))/2 for i in range(3)))
            slice_mesh_by_plane(obj.data,obj.matrix_world,center,Vector((0,0,1)),*meshes,unit_scale=scale)
        else:
            if mode=='LOOP':
                ids=[424,1648,425,1641,423,1659,427,1653,426,1669,429,1663,428,1677,430,1672]
                parts=slice_mesh_by_loop(obj,obj.name,ids,958,scene,part_clearance_mm=value,part_clearance_apply_to='PART')
                marker=parts[0].faces.layers.int.get('splitter_contact_surface')
                row['cap_quads']=sum(len(f.verts)==4 for f in parts[0].faces if marker and f[marker])
            else:
                parts=slice_mesh_by_material(obj,slot,depth_mm=value,scene=scene,region_index=0,extraction_mode=mode)
            try:
                for bm,mesh in zip(parts,meshes):bm.to_mesh(mesh)
            finally:
                for bm in parts:bm.free()
        if hasattr(geometry_quad_cap,'finish_cut_pair'):
            row['topology']=geometry_quad_cap.finish_cut_pair(*meshes,obj.data,obj.matrix_world,scale,use_contact_marks=mode not in ('PLANE','SOLID'))
        row['parts']=[metrics(mesh,scale) for mesh in meshes]
        assert all(p['nonmanifold_edges']==0 and p['volume_mm3']>0 for p in row['parts'])
        row['status']='OK'
        assert mesh_signature(obj.data)==before,'Source geometry changed'
    except Exception as error:
        row['status']='ERROR';row['error']=str(error)
    finally:
        for mesh in meshes:
            if mesh.users==0:bpy.data.meshes.remove(mesh)
    row['seconds']=round(time.time()-start,3)
    results.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
output.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
