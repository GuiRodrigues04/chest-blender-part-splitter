"""Private geometric experiment only; never installs or modifies production code."""
import bpy,bmesh,sys,json,traceback,math
from pathlib import Path
from mathutils import Matrix,Vector
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root));import src;src.register()
from src.geometry_loop import slice_mesh_by_loop
from src.geometry_contract import build_cut_interface,interface_point
from src.geometry_clearance_blade import _triangles
from src.geometry_connectors import (compute_connector_layout,check_receiving_wall_thickness,
    apply_connectors_boolean,min_distance_to_polygon_boundaries)
from src.diagnostic import validate_bmesh_mesh_geometry
from src.connector_surface import cache_prepared_interface,clear_prepared_split_cache
file=Path.home()/'OneDrive/Desktop/Modelos 3D e testes extensao/02_Personagens_e_Criaturas/spot/spot/Vaquinha.blend'
ids=[424,1648,425,1641,423,1659,427,1653,426,1669,429,1663,428,1677,430,1672]
rows=[]
for factor,gap in ((1.,.1),(.4,0.),(.4,.1)):
 row={'factor':factor,'gap_mm':gap};parts=None;objects=[]
 try:
  bpy.ops.wm.open_mainfile(filepath=str(file),use_scripts=False);scene=bpy.context.scene;s=scene.chest_splitter;obj=bpy.data.objects['spot_quadrangulated']
  obj.matrix_world=Matrix.Scale(factor,4)@obj.matrix_world;bpy.context.view_layer.update()
  # Keep the original on disk intact. Geometry-only experiments use a private
  # mesh copy without UV layers, isolating the independent UV-restore exception.
  obj.data=obj.data.copy()
  while obj.data.uv_layers:obj.data.uv_layers.remove(obj.data.uv_layers[0])
  s.target_object=obj;s.split_mode='LOOP';s.loop_vertex_indices=','.join(map(str,ids));s.loop_seed_face_index=958;s.loop_behavior='DETACH';s.part_clearance_mm=gap;s.connector_male_part='A'
  parts=slice_mesh_by_loop(obj,obj.name,ids,958,scene,part_clearance_mm=gap)
  points=[obj.matrix_world@obj.data.vertices[i].co for i in ids];center=sum(points,Vector())/len(points);axis=parts.interface.normal_a_to_b_world
  domain=build_cut_interface(center,axis,points,interface_triangles=_triangles(parts[0]),unit_scale=1000)
  clear_prepared_split_cache();prep=cache_prepared_interface(bpy.context,parts.interface)
  row.update(full_size_mm=[domain.width_mm,domain.height_mm],full_area_mm2=domain.area_mm2,selected_area_mm2=prep.interface.area_mm2,
    deviation_mm=parts.interface.nominal_deviation_mm,local_frame=getattr(parts.interface,'local_contact_frame',False))
  origin_uv=domain.world_to_uv(center)
  radius_mm=min_distance_to_polygon_boundaries(*origin_uv,domain.outer_contours_uv,domain.hole_contours_uv)*1000
  proposed_d=math.floor(min(.2*min(domain.width_mm,domain.height_mm),2*(radius_mm-.4-.1))/.5)*.5
  row.update(center_border_distance_mm=radius_mm,proposed_diameter_mm=max(1,proposed_d))
  row['cases']=[]
  for male_side in ('A','B'):
   for diam,length in ((1.,8.),(max(1,proposed_d),1.5*max(1,proposed_d)),(6.,8.)):
    case={'male':male_side,'diameter_mm':diam,'length_mm':length};temporary=[]
    try:
     # A's true surface defines the centered anchor; B uses its own real surface.
     side=0 if male_side=='A' else 1
     own=build_cut_interface(center,axis,points,interface_triangles=_triangles(parts[side]),unit_scale=1000)
     layout=compute_connector_layout(obj.data,obj.matrix_world,own.origin_world,axis if side==0 else -axis,distribution='MANUAL',
        edge_margin_mm=.4,unit_scale=1000,diameter_mm=diam,clearance_per_side_mm=.1,interface=own,
        manual_specs=[{'u_mm':0.,'v_mm':0.,'yaw_deg':0.}])
     for index,part in enumerate(parts):
      mesh=bpy.data.meshes.new('proof_part');part.to_mesh(mesh);candidate=bpy.data.objects.new('proof_part',mesh);scene.collection.objects.link(candidate);temporary.append(candidate)
     bpy.context.view_layer.update()
     normal=axis if side==0 else -axis;position=layout['positions'][0]
     ok,depth=check_receiving_wall_thickness(temporary[1-side],[position],normal,(length+.1)/1000,
       cavity_radius_bu=(diam/2+.1)/1000)
     case.update(footprint_valid=layout['manual_eval_results'][0]['is_valid'],wall_valid=ok,available_receiver_mm=depth*1000)
     apply_connectors_boolean(temporary[side],temporary[1-side],normal,[position],'CYLINDER',diam,length,0.,.1,.1,1000,
       pin_rotations=layout['pin_rotations'])
     case['parts']=[]
     for candidate in temporary:
      bm=bmesh.new();bm.from_mesh(candidate.data);bm.normal_update();metrics=validate_bmesh_mesh_geometry(bm,1000)
      remaining=set(bm.faces);components=0
      while remaining:
       components+=1;queue=[remaining.pop()]
       while queue:
        face=queue.pop()
        for edge in face.edges:
         for adjacent in edge.link_faces:
          if adjacent in remaining:remaining.remove(adjacent);queue.append(adjacent)
      case['parts'].append({'valid':metrics['is_valid'],'bad_edges':sum(not e.is_manifold for e in bm.edges),'components':components,'volume_mm3':bm.calc_volume()*1e9});bm.free()
     case['status']='OK' if all(p['valid'] and not p['bad_edges'] and p['components']==1 for p in case['parts']) else 'INVALID_RESULT'
    except Exception as error:case.update(status='ERROR',error=str(error),traceback=traceback.format_exc())
    finally:
     for candidate in temporary:
      mesh=candidate.data;bpy.data.objects.remove(candidate,do_unlink=True)
      if mesh.users==0:bpy.data.meshes.remove(mesh)
    row['cases'].append(case)
  row['status']='OK'
 except Exception as error:row.update(status='ERROR',error=str(error),traceback=traceback.format_exc())
 finally:
  if parts:
   for part in parts:part.free()
 rows.append(row);print(json.dumps(row),flush=True)
(Path(__file__).parent/'center_proof.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
