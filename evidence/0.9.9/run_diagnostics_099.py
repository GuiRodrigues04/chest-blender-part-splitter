"""Focused release replay and 20-case connector-route matrix for Blender."""
import json, math, sys, traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tests'))
import bpy,bmesh,src
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from test_release_workflows import ReleaseWorkflows, mesh_bmesh
from test_all_cut_topology import AllCutTopology

def part_metrics(part):
    bm=bmesh.new(); bm.from_mesh(part.data); bm.transform(part.matrix_world); bm.normal_update()
    try:
        points=[part.matrix_world @ v.co for v in part.data.vertices]
        tree=BVHTree.FromBMesh(bm)
        return {'volume_mm3':abs(bm.calc_volume())*1e9,'manifold':all(e.is_manifold for e in bm.edges),
          'vertices':sorted(tuple(round(c,7) for c in p) for p in points),
          'bbox_mm':[[min(p[i] for p in points)*1000 for i in range(3)],[max(p[i] for p in points)*1000 for i in range(3)]],
          'bvh':tree,'points':points,'mesh':bm}
    except:
        bm.free();raise

def main():
    src.register()
    # Reproduce only the first body at 1 mm depth and .15 mm clearance.
    ReleaseWorkflows.setUpClass()
    case=ReleaseWorkflows()
    case.setup_case(case.items[0],'LOOP','AUTO',.15); case.s.loop_extrude_depth_mm=1
    case.generate(); first=[part_metrics(p) for p in case.__class__.__module__ and __import__('src.operators',fromlist=['get_current_session_parts']).get_current_session_parts(bpy.context.scene)]
    case.generate(); second=[part_metrics(p) for p in __import__('src.operators',fromlist=['get_current_session_parts']).get_current_session_parts(bpy.context.scene)]
    replay=[]
    for i,(a,b) in enumerate(zip(first,second)):
        distances=[]
        for p in a['points']:
            hit=b['bvh'].find_nearest(p)
            distances.append((hit[0]-p).length if hit and hit[0] else float('inf'))
        for p in b['points']:
            hit=a['bvh'].find_nearest(p)
            distances.append((hit[0]-p).length if hit and hit[0] else float('inf'))
        replay.append({'part':i,'same_unordered_rounded_vertices':a['vertices']==b['vertices'],
          'vertex_count_first':len(a['vertices']),'vertex_count_repeat':len(b['vertices']),
          'volume_delta_mm3':abs(a['volume_mm3']-b['volume_mm3']),
          'bbox_delta_mm':max(abs(a['bbox_mm'][j][k]-b['bbox_mm'][j][k]) for j in (0,1) for k in range(3)),
          'bidirectional_vertex_to_surface_max_mm':max(distances)*1000 if distances else 0})
    for r in first+second:r['mesh'].free()
    del case
    # Matrix uses the 20 mm diameter, 40 mm tall closed cylinder from all-cut tests.
    matrix=[]
    helper=AllCutTopology()
    for method in ('LOOP','WHOLE','SOLID','MATERIAL','PLANE'):
      for male in ('A','B'):
       for gap in (0.,.2):
        row={'route':method,'male_part':male,'gap_mm':gap}
        try:
          obj,s=helper.setup_cut(method,gap,segments=16)
          original=tuple(tuple(v.co) for v in obj.data.vertices)
          supports_pins=method!='SOLID'
          s.connector_enabled=False; s.connector_type='CYLINDER'; s.connector_male_part=male
          s.connector_diameter_mm=2.; s.connector_length_mm=3.; s.connector_chamfer_mm=0.
          s.clearance_per_side_mm=.1; s.end_clearance_mm=.2; s.connector_edge_margin_mm=.5
          s.connector_distribution='CENTER'; s.part_clearance_apply_to='PART'
          if method=='WHOLE':
            pre=bpy.ops.chest.splitter_generate_preview()
            if pre!={'FINISHED'}: raise RuntimeError('WHOLE preliminary no-pin preview failed')
            choice=bpy.ops.chest.splitter_choose_contact(index=0)
            if choice!={'FINISHED'} or s.contact_patch_index<0: raise RuntimeError('WHOLE contact selection failed')
          s.connector_enabled=supports_pins
          s.connector_avoid_edges=True
          op=bpy.ops.chest.splitter_generate_preview(); row['operator_result']=str(op); row['status']=s.session_status
          parts=[o for o in bpy.context.scene.objects if o.get('chest_role') in ('PREVIEW_A','PREVIEW_B')]
          row['part_count']=len(parts); row['parts']=[]
          for part in parts:
            bm=bmesh.new();bm.from_mesh(part.data);bm.transform(part.matrix_world);bm.normal_update()
            try: row['parts'].append({'name':part.name,'manifold':all(e.is_manifold for e in bm.edges),'volume_mm3':abs(bm.calc_volume())*1e9})
            finally:bm.free()
          row['source_unchanged']=original==tuple(tuple(v.co) for v in obj.data.vertices)
          row['connector_capability']='unsupported_by_design' if not supports_pins else 'enabled'
          row['passed']=(op=={'FINISHED'} and s.session_status=='PREVIEW_VALID' and len(parts)==2 and row['source_unchanged'] and all(p['manifold'] and p['volume_mm3']>0 for p in row['parts']))
        except Exception as exc:
          row.update(passed=False,error=repr(exc),traceback=traceback.format_exc(limit=3))
        matrix.append(row);print('PIN_MATRIX',json.dumps(row),flush=True)
    report={'phase':'diagnostics','source':str(ROOT),'current_replay':replay,
      'matrix':matrix,'matrix_totals':{'cases':len(matrix),'passed':sum(bool(x.get('passed')) for x in matrix),'failed':sum(not x.get('passed') for x in matrix)}}
    out=ROOT/'evidence'/'0.9.9';(out/'current_replay_and_pin_matrix.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('DIAGNOSTICS',json.dumps({'current_replay':replay,'matrix_totals':report['matrix_totals']},indent=2),flush=True)
    return 0 if report['matrix_totals']['failed']==0 else 1
if __name__=='__main__':raise SystemExit(main())
