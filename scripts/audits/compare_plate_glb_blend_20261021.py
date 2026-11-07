"""Compare color/material payloads and dimensions for single-material GLBs."""
import json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2]
GLB_DIR=Path(r"C:\Users\guiro\OneDrive\Desktop\Placas - Modelos 3D\Modelos_Chest\Modelos Versão 1 - Placas Inteiras")
BLEND_DIR=GLB_DIR/'Blender'
OUT=ROOT/'evidence'/'commercial_plates_glb_20261021'/'single_material_counterparts.json'
FILES=['Placa_Numero_Chest_Inteira','Placa_QR_Inclinada_Chest_V2_Inteira']
def material_info(m):
    if not m:return None
    nodes=[]
    if m.use_nodes and m.node_tree:
        for n in m.node_tree.nodes:
            item={'type':n.type,'name':n.name}
            if n.type=='BSDF_PRINCIPLED':
                sock=n.inputs.get('Base Color')
                if sock:
                    item['base_color_default']=list(sock.default_value)
                    if sock.is_linked:item['base_color_link_from']=[l.from_node.type+':'+l.from_socket.name for l in sock.links]
            if n.type=='TEX_IMAGE':item['image']=n.image.name if n.image else None
            nodes.append(item)
    return {'name':m.name,'diffuse_color':list(m.diffuse_color),'use_nodes':m.use_nodes,'nodes':nodes}
def object_info(obj):
    mesh=obj.data
    counts={str(i):0 for i in range(len(mesh.materials))}
    for p in mesh.polygons:counts[str(p.material_index)]=counts.get(str(p.material_index),0)+1
    attrs=[]
    for a in mesh.color_attributes:
        vals=[tuple(float(x) for x in e.color) for e in a.data]
        unique=sorted(set(tuple(round(x,5) for x in v) for v in vals))
        attrs.append({'name':a.name,'domain':a.domain,'data_type':a.data_type,'elements':len(a.data),'unique_color_count':len(unique),'sample_colors':unique[:12]})
    return {'object':obj.name,'dimensions_mm':[float(x)*1000 for x in obj.dimensions], 'mesh_vertices':len(mesh.vertices),'faces':len(mesh.polygons),'polygons_per_material':counts,'materials':[material_info(m) for m in mesh.materials], 'color_attributes':attrs,'uv_layers':[u.name for u in mesh.uv_layers], 'vertex_groups':len(obj.vertex_groups)}
records=[]
for stem in FILES:
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.scale_length=1
    bpy.ops.import_scene.gltf(filepath=str(GLB_DIR/(stem+'.glb')))
    glb=[o for o in bpy.context.scene.objects if o.type=='MESH'][0]
    gi=object_info(glb)
    blend_path=BLEND_DIR/(stem+'.blend')
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.context.scene.unit_settings.scale_length=1
    with bpy.data.libraries.load(str(blend_path),link=False) as (src,dst):
        obj_name=stem if stem in src.objects else next(n for n in src.objects if stem in n and src.objects[n].type=='MESH')
        dst.objects=[obj_name]
    obj=dst.objects[0];bpy.context.scene.collection.objects.link(obj)
    bi=object_info(obj)
    records.append({'stem':stem,'blend_path':str(blend_path),'glb':gi,'blend':bi,'same_dimensions_within_0_01mm':all(abs(a-b)<=.01 for a,b in zip(gi['dimensions_mm'],bi['dimensions_mm']))})
OUT.write_text(json.dumps({'comparisons':records},indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'comparisons':records},indent=2,ensure_ascii=False))
