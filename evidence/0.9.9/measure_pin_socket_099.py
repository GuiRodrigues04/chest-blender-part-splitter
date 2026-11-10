"""Measure one actual integrated pin/socket from output meshes using BVH rays."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
import bpy,bmesh,src
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from test_all_cut_topology import AllCutTopology
from src.connector_surface import prepare_split_candidates
from src.geometry_connectors import compute_connector_layout

def tree_for(obj):
    bm=bmesh.new();bm.from_mesh(obj.data);bm.transform(obj.matrix_world);bm.normal_update()
    return bm,BVHTree.FromBMesh(bm)

def main():
    src.register(); helper=AllCutTopology(); obj,s=helper.setup_cut('LOOP',0.,segments=16)
    s.connector_enabled=True;s.connector_type='CYLINDER';s.connector_male_part='A'
    s.connector_diameter_mm=2.;s.connector_length_mm=3.;s.connector_chamfer_mm=0.
    s.clearance_per_side_mm=.1;s.end_clearance_mm=.2;s.connector_edge_margin_mm=.5;s.connector_distribution='CENTER'
    assert bpy.ops.chest.splitter_generate_preview()=={'FINISHED'},s.get_localized_status()
    prepared=prepare_split_candidates(bpy.context,force_recompute=True)
    iface=prepared.interface; norm=iface.normal_a_to_b_world.normalized()
    layout=compute_connector_layout(obj.data,obj.matrix_world,iface.origin_world,norm,'CENTER',.5,1000.,2.,.1,interface=iface)
    center=layout['positions'][0]
    rot=layout['pin_rotations'][0].to_matrix();u=rot@Vector((1,0,0));v=rot@Vector((0,1,0));axis=rot@Vector((0,0,1))
    parts={o.get('chest_role')[-1]:o for o in bpy.context.scene.objects if o.get('chest_role') in ('PREVIEW_A','PREVIEW_B')}
    meshes={k:tree_for(o) for k,o in parts.items()}
    rows=[]
    for role in ('A','B'):
      tree=meshes[role][1]; radii=[]
      for fraction in (.25,.5,.75):
       start=center+axis*(.003*fraction)
       for j in range(8):
        direction=(u*__import__('math').cos(j*__import__('math').pi/4)+v*__import__('math').sin(j*__import__('math').pi/4)).normalized()
        hit=tree.ray_cast(start,direction,.005)
        if hit[0] is not None:radii.append((hit[0]-start).length*1000)
      floor=tree.ray_cast(center+axis*.0005,axis,.01)
      rows.append({'role':role,'radial_samples':len(radii),'radius_min_mm':min(radii) if radii else None,'radius_max_mm':max(radii) if radii else None,'axial_floor_mm':(floor[0]-center).dot(axis)*1000 if floor[0] is not None else None})
    for bm,_ in meshes.values():bm.free()
    male=next(r for r in rows if r['role']=='A');female=next(r for r in rows if r['role']=='B')
    report={'fixture':'closed 20mm-diameter cylinder; LOOP; 2mm pin; 3mm length; 0.1mm radial clearance; 0.2mm end clearance','center_world':list(center),'axis_world':list(axis),'measurements':rows,
      'measured_radius_delta_range_mm':[female['radius_min_mm']-male['radius_max_mm'],female['radius_max_mm']-male['radius_min_mm']],
      'measured_end_clearance_mm':female['axial_floor_mm']-male['axial_floor_mm'],
      'radial_pass':bool(male['radial_samples']>=12 and female['radial_samples']>=12 and abs((female['radius_min_mm']+female['radius_max_mm']-male['radius_min_mm']-male['radius_max_mm'])/2-.1)<=.02),
      'end_pass':bool(female['axial_floor_mm'] is not None and male['axial_floor_mm'] is not None and abs((female['axial_floor_mm']-male['axial_floor_mm'])-.2)<=.02)}
    path=ROOT/'evidence'/'0.9.9'/'pin_socket_physical_measurement.json';path.write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2));return 0 if report['radial_pass'] and report['end_pass'] else 1
if __name__=='__main__':raise SystemExit(main())
