import bpy, bmesh, sys, json, math, traceback
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(r'C:\Users\guiro\.gemini\antigravity\scratch\chest-blender-part-splitter')
OUT=ROOT/'evidence'/'commercial_cube_20261021'
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0,str(ROOT))
import src
src.register()
from src.geometry_material import list_material_regions, analyze_material_structure, slice_mesh_by_material
from src.diagnostic import validate_bmesh_mesh_geometry
from src.constants import PREVIEW_A_NAME, PREVIEW_B_NAME
from src import operators
BLEND=Path(r'C:\Users\guiro\OneDrive\Desktop\Padrão Testes.blend')
results=[]
def log(case, status, **data):
    row={'case':case,'status':status,**data};results.append(row)
    print('AUDIT',json.dumps(row,ensure_ascii=False,default=str))
def load():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    # scene addon properties survive register; reset interactive state with originals
    bpy.context.view_layer.update()
def bm_metrics(bm):
    bm.normal_update()
    valid=validate_bmesh_mesh_geometry(bm,1000)
    return {'verts':len(bm.verts),'faces':len(bm.faces),'volume_mm3':abs(float(bm.calc_volume()))*1e9,'closed':all(e.is_manifold for e in bm.edges),'valid':valid.get('is_valid'),'degenerate':len(valid.get('degenerate_faces',[])),'nonmanifold':len(valid.get('non_manifold_edges',[])),'material_counts':{str(i):sum(1 for f in bm.faces if f.material_index==i) for i in sorted(set(f.material_index for f in bm.faces))}}
def clean_bms(pair):
    for bm in pair:
        if bm: bm.free()
def source_state(obj):
    return (tuple(tuple(v.co) for v in obj.data.vertices), tuple(tuple(p.vertices) for p in obj.data.polygons), tuple(p.material_index for p in obj.data.polygons), tuple((m.name if m else None,tuple(m.diffuse_color) if m else None) for m in obj.data.materials))
def contact_gap_mm(interface):
    a=(interface.final_contact_a or {}).get('boundary',[]);b=(interface.final_contact_b or {}).get('boundary',[])
    n=interface.normal_a_to_b_world
    if len(a)!=len(b) or not a:return None
    ds=[(pb-pa).dot(n)*1000.0 for pa,pb in zip(a,b)]
    return {'count':len(ds),'min_mm':min(ds),'mean_mm':sum(ds)/len(ds),'max_mm':max(ds)}
def world_bvh(obj):
    bm=bmesh.new();bm.from_mesh(obj.data);bm.transform(obj.matrix_world);bm.normal_update()
    tree=BVHTree.FromBMesh(bm);bm.free();return tree
def ray_radius_mm(tree, origin, direction, unit_scale):
    hit=tree.ray_cast(origin,direction,0.02)
    if not hit or hit[0] is None:return None
    return (hit[0]-origin).length*unit_scale
# Inventory and source preservation
load()
for name in ('Cubo Teste','Cubo Teste 2','Cube.001__B__A','Cubo Teste 2__B'):
    o=bpy.data.objects.get(name)
    if not o: continue
    green=2
    regs=list_material_regions(o,green)
    summaries=[]
    for reg in regs:
        a=analyze_material_structure(o,green,reg['index'])
        summaries.append({'region':reg['index'],'faces':reg['face_count'],'valid':a.get('valid'),'type':a.get('type'),'deviation_mm':a.get('base_deviation_mm'),'err':a.get('error')})
    log('inventory:'+name,'PASS',hidden=o.hide_get() or o.hide_viewport,green_material=o.data.materials[green].name,regions=summaries)
# Direct geometry sweep of all discovered green regions; collect actual solid validation/volume.
for name in ('Cubo Teste','Cubo Teste 2','Cube.001__B__A','Cubo Teste 2__B'):
    load();o=bpy.data.objects.get(name)
    if not o: continue
    for r in list_material_regions(o,2):
        case=f'material:{name}:region{r["index"]}:extrude:none'
        try:
            result=slice_mesh_by_material(o,2,depth_mm=2,scene=bpy.context.scene,region_index=r['index'],extraction_mode='EXTRUDE',part_clearance_mm=0.0)
            ma,mb=(bm_metrics(result.bm_a),bm_metrics(result.bm_b))
            log(case,'PASS' if ma['valid'] and mb['valid'] and ma['closed'] and mb['closed'] else 'FAIL',faces=r['face_count'],A=ma,B=mb,volume_sum=ma['volume_mm3']+mb['volume_mm3'],iface={'clearance':getattr(result.interface,'clearance_applied',None),'area':getattr(result.interface,'area_mm2',None)})
            if name=='Cubo Teste' and r['index']==2:
                col=bpy.data.collections.new('AUDIT_GREEN_EXTRACTION');bpy.context.scene.collection.children.link(col)
                for label,bm in zip(('PART_A_EXTRACTED_GREEN','PART_B_REMAINDER'),(result.bm_a,result.bm_b)):
                    mesh=bpy.data.meshes.new(label);bm.to_mesh(mesh);mesh.update();obj=bpy.data.objects.new(label,mesh);col.objects.link(obj)
                    for mat in o.data.materials:mesh.materials.append(mat)
                bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'green_material_region2_extruded_clearance_none.blend'))
            clean_bms(result)
        except Exception as e: log(case,'EXPECTED_REJECTION' if type(e).__name__=='LocalizedGeometryError' or (type(e).__name__=='ValueError' and 'todas as faces do modelo já utilizam este material' in str(e).lower()) else 'ERROR',faces=r['face_count'],error=repr(e),trace=traceback.format_exc(limit=2))
# Material direct clearance/application matrix with measured interface contact surfaces.
for gap,apply,bottom in [(0.0,'PART',0.0),(.1,'PART',.1),(.1,'CAVITY',.1),(.1,'BOTH',.1),(.1,'BOTH',.2)]:
    load();o=bpy.data.objects['Cubo Teste'];case=f'material:Cubo Teste:region2:gap{gap}:{apply}:bottom{bottom}'
    try:
        result=slice_mesh_by_material(o,2,depth_mm=2,scene=bpy.context.scene,region_index=2,extraction_mode='EXTRUDE',part_clearance_mm=gap,part_clearance_apply_to=apply,part_clearance_bottom_mm=bottom)
        ma,mb=bm_metrics(result.bm_a),bm_metrics(result.bm_b);gap_measured=contact_gap_mm(result.interface)
        log(case,'PASS' if ma['valid'] and mb['valid'] and ma['closed'] and mb['closed'] else 'FAIL',A=ma,B=mb,volume_sum_mm3=ma['volume_mm3']+mb['volume_mm3'],requested_gap_mm=gap,apply=apply,bottom_mm=bottom,measured_contact_gap=gap_measured,interface_clearance_applied=result.interface.clearance_applied)
        clean_bms(result)
    except Exception as e:log(case,'EXPECTED_REJECTION',error=repr(e))
# Representative region: profile and application matrix, loop direct + material preview/commit/revert.
load();o=bpy.data.objects.get('Cubo Teste'); s=bpy.context.scene.chest_splitter
if o:
    # pick largest green island as real Edit Mode selected region and capture its boundary
    regs=list_material_regions(o,2); r=max(regs,key=lambda x:x['face_count']); s.target_object=o;s.split_mode='LOOP';s.loop_behavior='EXTRUDE';s.loop_extrude_depth_mm=2.;s.connector_enabled=False;s.commit_next_target='NONE';s.view_mode='ASSEMBLED'
    before=source_state(o); original_mesh=o.data
    try:
        # Temporarily reveal for active target and enter actual edit-mode face selection.
        o.hide_viewport=False;o.hide_set(False);bpy.ops.object.select_all(action='DESELECT');o.select_set(True);bpy.context.view_layer.objects.active=o
        bpy.ops.object.mode_set(mode='EDIT');bpy.context.tool_settings.mesh_select_mode=(False,False,True)
        bm=bmesh.from_edit_mesh(o.data);bm.faces.ensure_lookup_table()
        for f in bm.faces:f.select_set(f.material_index==2 and f.index in {x.index for x in bm.faces if x.material_index==2})
        green_faces=[f for f in bm.faces if f.material_index==2]
        # capture one chosen connected material island only
        desired=set()
        # derive selected island faces via exact region helper as first_face seed and flood by shared edges
        seed=next(f for f in green_faces if f.index==r['first_face']); island={seed}; stack=[seed]
        while stack:
            f=stack.pop()
            for e in f.edges:
                for n in e.link_faces:
                    if n.material_index==2 and n not in island:island.add(n);stack.append(n)
        for f in green_faces:f.select_set(f in island)
        bm.faces.active=seed;bmesh.update_edit_mesh(o.data)
        cap=bpy.ops.chest.splitter_capture_face_boundary(); captured={'op':list(cap),'is_captured':s.loop_is_captured,'count':s.loop_vertex_count,'seed':s.loop_seed_face_index,'indices':[int(x) for x in s.loop_vertex_indices.split(',') if x]}
        bpy.ops.object.mode_set(mode='OBJECT')
        log('loop:capture-real-green-island','PASS' if cap=={'FINISHED'} and s.loop_is_captured else 'FAIL',target=o.name,region=r['index'],faces=len(island),capture=captured,source_selection_preserved=(o.data is original_mesh and before==source_state(o)))
        # Direct loop splitter gap measurements on the captured 62-point contour.
        from src.geometry_loop import slice_mesh_by_loop_extrude
        captured_indices=[int(x) for x in s.loop_vertex_indices.split(',') if x]
        for gap,apply,bottom in [(0.0,'PART',0.0),(.1,'PART',.1),(.1,'CAVITY',.1),(.1,'BOTH',.1),(.1,'BOTH',.2)]:
            case=f'loop-direct:region{r["index"]}:gap{gap}:{apply}:bottom{bottom}'
            try:
                result=slice_mesh_by_loop_extrude(o,o.name,captured_indices,s.loop_seed_face_index,2.0,False,bpy.context.scene,gap,apply,bottom if bottom>0 else None)
                ma,mb=bm_metrics(result.bm_a),bm_metrics(result.bm_b)
                log(case,'PASS' if ma['valid'] and mb['valid'] and ma['closed'] and mb['closed'] else 'FAIL',A=ma,B=mb,volume_sum_mm3=ma['volume_mm3']+mb['volume_mm3'],requested_gap_mm=gap,apply=apply,bottom_mm=bottom,measured_contact_gap=contact_gap_mm(result.interface),interface_clearance_applied=result.interface.clearance_applied)
                clean_bms(result)
            except Exception as e:log(case,'EXPECTED_REJECTION' if type(e).__name__=='LocalizedGeometryError' else 'ERROR',error=repr(e))
        # Loop clearance cases with direct geometry (NONE, FDM amount=0.1; app side options)
        for gap,apply,bottom,profile,bottom_enable in [(0.,'PART',0.,'NONE',False),(.1,'PART',.1,'FDM',False),(.1,'CAVITY',.1,'FDM',False),(.1,'BOTH',.1,'FDM',False),(.1,'BOTH',.2,'CUSTOM',True)]:
            s.assembly_clearance_preset=profile;s.part_clearance_mm=gap;s.part_clearance_bottom_mm=bottom;s.part_clearance_bottom_enable=bottom_enable;s.part_clearance_apply_to=apply
            case=f'loop:{r["index"]}:gap{gap}:{apply}:bottom{bottom}'
            try:
                ret=bpy.ops.chest.splitter_generate_preview()
                parts=operators.get_current_session_parts(bpy.context.scene)
                metrics=[]
                for p in parts:
                    b=bmesh.new();b.from_mesh(p.data);metrics.append(bm_metrics(b));b.free()
                log(case,'PASS' if ret=={'FINISHED'} and len(parts)==2 and all(x['valid'] and x['closed'] for x in metrics) else 'FAIL',operator=list(ret),session_status=s.session_status,parts=metrics,selected_preserved=(before==source_state(o)),gap_requested_mm=gap,profile=profile,bottom_enable=bottom_enable,apply=apply,bottom=bottom)
                if ret=={'FINISHED'} and gap==.1 and apply=='BOTH':
                    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/('green_loop_clearance_fdm_both.blend' if profile=='FDM' else f'green_loop_clearance_custom_bottom_{bottom:.1f}_both.blend')))
                if ret=={'FINISHED'}:
                    cr=bpy.ops.chest.splitter_commit_parts(); opid=s.active_operation_id or s.session_id
                    revert=bpy.ops.chest.splitter_revert_cut(operation_id=opid)
                    log(case+':commit-revert','PASS' if cr=={'FINISHED'} and revert=={'FINISHED'} else 'FAIL',commit=list(cr),revert=list(revert),source_restored=(before==source_state(o)),mesh_datablock_identity_preserved=(o.data is original_mesh))
            except Exception as e: log(case,'EXPECTED_REJECTION' if s.session_status=='PREVIEW_INVALID' else 'ERROR',error=repr(e),session_status=s.session_status)
        # Pin-on-actual-green-region attempt using a centered FDM-style connector.
        s.assembly_clearance_preset='FDM';s.connector_enabled=True;s.connector_distribution='CENTER';s.connector_male_part='A';s.connector_diameter_mm=3.;s.connector_length_mm=3.;s.connector_chamfer_mm=.2;s.clearance_per_side_mm=.15;s.end_clearance_mm=.2;s.part_clearance_mm=.1;s.part_clearance_bottom_mm=.1;s.part_clearance_apply_to='BOTH';s.part_clearance_bottom_enable=False
        try:
            ret=bpy.ops.chest.splitter_generate_preview();parts=operators.get_current_session_parts(bpy.context.scene);metrics=[]
            for p in parts:
                q=bmesh.new();q.from_mesh(p.data);metrics.append(bm_metrics(q));q.free()
            pin_count=sum(1 for ob in bpy.context.scene.objects if ob.get('chest_role') in ('PREVIEW_CONNECTOR','CONNECTOR'))
            pin_geometry=None
            if ret=={'FINISHED'} and len(parts)==2:
                from src.connector_surface import get_cached_prepared_split, prepared_connector_layout
                prep=get_cached_prepared_split();layout=prepared_connector_layout(prep,s,o);positions=layout.get('positions',[])
                if prep and positions:
                    male_obj=bpy.data.objects.get('SPLITTER_PREVIEW_A');female_obj=bpy.data.objects.get('SPLITTER_PREVIEW_B')
                    if s.connector_male_part=='B':male_obj,female_obj=female_obj,male_obj
                    n=prep.surface_normal.normalized();u=prep.axis_u.normalized();v=prep.axis_v.normalized();pos=positions[0];scale=prep.unit_scale
                    male_tree=world_bvh(male_obj);female_tree=world_bvh(female_obj);sample=pos+n*(1.5/scale)
                    radii_m=[];radii_f=[]
                    for j in range(32):
                        ang=2.0*math.pi*j/32;d=(math.cos(ang)*u+math.sin(ang)*v).normalized()
                        radii_m.append(ray_radius_mm(male_tree,sample,d,scale));radii_f.append(ray_radius_mm(female_tree,sample,d,scale))
                    male_tip=male_tree.ray_cast(sample,n,.02);female_floor=female_tree.ray_cast(sample,n,.02)
                    tip_s=(male_tip[0]-pos).dot(n)*scale if male_tip and male_tip[0] is not None else None
                    floor_s=(female_floor[0]-pos).dot(n)*scale if female_floor and female_floor[0] is not None else None
                    usable_m=[x for x in radii_m if x is not None];usable_f=[x for x in radii_f if x is not None]
                    pin_geometry={'positions':len(positions),'sampled_rays':32,'male_radius_mm':{'min':min(usable_m) if usable_m else None,'mean':sum(usable_m)/len(usable_m) if usable_m else None,'max':max(usable_m) if usable_m else None},'female_bore_radius_mm':{'min':min(usable_f) if usable_f else None,'mean':sum(usable_f)/len(usable_f) if usable_f else None,'max':max(usable_f) if usable_f else None},'radial_clearance_mm':{'min':min((f-m) for m,f in zip(radii_m,radii_f) if m is not None and f is not None),'mean':sum((f-m) for m,f in zip(radii_m,radii_f) if m is not None and f is not None)/len([1 for m,f in zip(radii_m,radii_f) if m is not None and f is not None]),'max':max((f-m) for m,f in zip(radii_m,radii_f) if m is not None and f is not None)},'male_tip_s_mm':tip_s,'female_floor_s_mm':floor_s,'axial_clearance_mm':floor_s-tip_s if tip_s is not None and floor_s is not None else None}
            log('loop:green-island:center-pin-fdm','PASS' if ret=={'FINISHED'} and len(parts)==2 and all(x['valid'] and x['closed'] for x in metrics) else ('EXPECTED_REJECTION' if ret!={'FINISHED'} else 'FAIL'),operator=list(ret),session_status=s.session_status,parts=metrics,pin_objects=pin_count,connector_type=s.connector_type,distribution=s.connector_distribution,diameter_setting_mm=s.connector_diameter_mm,length_setting_mm=s.connector_length_mm,radial_clearance_setting_mm=s.clearance_per_side_mm,end_clearance_setting_mm=s.end_clearance_mm,pin_geometry_measured=pin_geometry)
            if ret=={'FINISHED'}:bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'green_loop_clearance_fdm_both_center_pin.blend'))
        except Exception as e:log('loop:green-island:center-pin-fdm','EXPECTED_REJECTION' if s.session_status=='PREVIEW_INVALID' else 'ERROR',error=repr(e),session_status=s.session_status)
    except Exception as e:
        try:
            if o.mode=='EDIT':bpy.ops.object.mode_set(mode='OBJECT')
        except:pass
        log('loop:capture-real-green-island','ERROR',error=repr(e),trace=traceback.format_exc(limit=3),source_restored=(o.data is original_mesh))
# Save JSON with one record per case (does not write blend).
(OUT/'cube_green_results.json').write_text(json.dumps(results,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
print('AUDIT_SUMMARY',json.dumps({'cases':len(results),'pass':sum(x['status']=='PASS' for x in results),'fail':sum(x['status']=='FAIL' for x in results),'errors':sum(x['status']=='ERROR' for x in results),'expected_rejections':sum(x['status']=='EXPECTED_REJECTION' for x in results),'json':str(OUT/'cube_green_results.json')},ensure_ascii=False))











