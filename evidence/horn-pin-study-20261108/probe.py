import bpy,sys,json,traceback,math
from pathlib import Path
from mathutils import Vector,Matrix
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root));import src;src.register()
from src.geometry_loop import slice_mesh_by_loop
from src.geometry_clearance_blade import _triangles
from src.geometry_contract import build_cut_interface
from src.geometry_connectors import compute_connector_layout,validate_connector_footprint,min_distance_to_polygon_boundaries
from src.connector_surface import cache_prepared_interface,clear_prepared_split_cache
file=Path.home()/'OneDrive/Desktop/Modelos 3D e testes extensao/02_Personagens_e_Criaturas/spot/spot/Vaquinha.blend'
ids=[424,1648,425,1641,423,1659,427,1653,426,1669,429,1663,428,1677,430,1672]
results=[]
for factor in (1.,.25):
 for gap in (0.,.1):
  row={'scale_factor':factor,'gap_mm':gap};parts=None
  try:
   bpy.ops.wm.open_mainfile(filepath=str(file),use_scripts=False);scene=bpy.context.scene;s=scene.chest_splitter;obj=bpy.data.objects['spot_quadrangulated']
   obj.matrix_world=Matrix.Scale(factor,4)@obj.matrix_world;bpy.context.view_layer.update()
   s.target_object=obj;s.split_mode='LOOP';s.loop_vertex_indices=','.join(map(str,ids));s.loop_seed_face_index=958;s.loop_behavior='DETACH'
   s.part_clearance_mm=gap;s.connector_diameter_mm=1;s.connector_length_mm=8;s.connector_edge_margin_mm=.4;s.clearance_per_side_mm=.1;s.end_clearance_mm=.1;s.connector_male_part='A';s.connector_distribution='CENTER'
   points=[obj.matrix_world@obj.data.vertices[i].co for i in ids];center=sum(points,Vector())/len(points)
   parts=slice_mesh_by_loop(obj,obj.name,ids,958,scene,part_clearance_mm=gap)
   iface=parts.interface;normal=iface.normal_a_to_b_world
   full=build_cut_interface(center,normal,points,interface_triangles=_triangles(parts[0]),unit_scale=1000)
   row.update(closure=iface.closure_strategy,deviation_mm=iface.nominal_deviation_mm,local_frame=getattr(iface,'local_contact_frame',False),full_area_mm2=full.area_mm2,full_size_mm=[full.width_mm,full.height_mm],full_center=list(center),cap_triangles=len(_triangles(parts[0])))
   row['part_sizes_mm']=[[1000*(max(v.co[i]for v in bm.verts)-min(v.co[i]for v in bm.verts))for i in range(3)]for bm in parts]
   clear_prepared_split_cache();prep=cache_prepared_interface(bpy.context,iface);selected=prep.interface
   row['selected_area_mm2']=selected.area_mm2;row['selected_size_mm']=[selected.width_mm,selected.height_mm]
   row['selected_contours_mm']=[[[1000*u,1000*v]for u,v in poly]for poly in selected.outer_contours_uv]
   uv=selected.world_to_uv(center);r=.001
   row['nominal_center_uv_mm']=[u*1000 for u in uv]
   row['nominal_center_selected_valid']=validate_connector_footprint(*uv,r,selected.outer_contours_uv,selected.hole_contours_uv,.4)[0]
   row['nominal_center_full_valid']=validate_connector_footprint(*full.world_to_uv(center),r,full.outer_contours_uv,full.hole_contours_uv,.4)[0]
   row['layouts']={}
   for label,domain in [('current',selected),('full',full)]:
    for adjust in (False,True):
     try:
      layout=compute_connector_layout(obj.data,obj.matrix_world,domain.origin_world,domain.normal_a_to_b_world,distribution='CENTER',edge_margin_mm=.4,unit_scale=1000,diameter_mm=1,clearance_per_side_mm=.1,interface=domain,adjust_to_valid_area=adjust)
      row['layouts'][label+str(adjust)]={k:(v if isinstance(v,(int,float,str,bool)) else str(v))for k,v in layout.items()if k not in ('positions','outer_polys','hole_polys')}
      positions=layout['positions'];row['layouts'][label+str(adjust)]['positions']=[list(p)for p in positions]
      row['layouts'][label+str(adjust)]['offset_from_center_mm']=[(p-center-normal*(p-center).dot(normal)).length*1000 for p in positions]
     except Exception as e:row['layouts'][label+str(adjust)]={'error':str(e)}
   row['status']='OK'
  except Exception as e:row.update(status='ERROR',error=str(e),traceback=traceback.format_exc())
  finally:
   if parts:
    for bm in parts:bm.free()
  results.append(row);print(json.dumps(row),flush=True)
(Path(__file__).parent/'probe_results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
