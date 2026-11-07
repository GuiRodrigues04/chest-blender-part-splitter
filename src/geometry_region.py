"""Split a captured surface using identical, contained closing triangles.

No dilation, second skin, hole filling of the input, or mapping through modifiers.
Every candidate is validated before it can replace a preview.
"""
import hashlib
import math
import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

CONTACT = 'splitter_contact_surface'
PATCH = 'splitter_contact_patch'


def mesh_signature(mesh):
    from .input_state import update_mesh_hash
    digest = hashlib.sha256()
    update_mesh_hash(digest, mesh)
    return digest.hexdigest()


def mesh_tree(mesh, matrix=None):
    mesh.calc_loop_triangles()
    points = [matrix @ v.co if matrix is not None else v.co.copy() for v in mesh.vertices]
    return BVHTree.FromPolygons(points, [tuple(t.vertices) for t in mesh.loop_triangles], all_triangles=True)


class Containment:
    def __init__(self, tree, tolerance):
        self.tree = tree
        self.tolerance = tolerance
        self.directions = [Vector(v).normalized() for v in ((.317,.433,.843),(-.733,.271,.613),(.431,-.847,.311))]

    def __call__(self, point):
        nearest = self.tree.find_nearest(point)
        if nearest[0] is None:
            return False
        if nearest[3] <= self.tolerance:
            return True
        votes = 0
        for direction in self.directions:
            current = point.copy()
            count = 0
            for _ in range(256):
                hit = self.tree.ray_cast(current, direction)
                if hit[0] is None:
                    break
                count += 1
                current = hit[0] + direction * self.tolerance
            else:
                return False
            votes += count % 2
        return votes >= 2


WEIGHTS = ((1/3,1/3,1/3),(.6,.2,.2),(.2,.6,.2),(.2,.2,.6))


def closing_triangles(coords, normal, va, vb, a, b, contains, scale):
    n = len(coords)
    if n > 128:
        raise ValueError('O contorno tem mais de 128 vértices. Simplifique a borda em uma cópia antes de capturar.')
    cost = [[float('inf')]*n for _ in range(n)]
    splits = {}
    for i in range(n-1):
        cost[i][i+1] = 0.
    for width in range(2,n):
        for i in range(n-width):
            j = i+width
            for k in range(i+1,j):
                if not math.isfinite(cost[i][k]+cost[k][j]):
                    continue
                if a.faces.get((va[i],va[k],va[j])) or b.faces.get((vb[i],vb[k],vb[j])):
                    continue
                points = (coords[i],coords[k],coords[j])
                cross = (points[1]-points[0]).cross(points[2]-points[0])
                if cross.dot(normal)*scale*scale <= 1e-6:
                    continue
                if not all(contains(sum((p*w for p,w in zip(points,weights)),Vector())) for weights in WEIGHTS):
                    continue
                value = cost[i][k]+cost[k][j]+cross.length*.5
                if value < cost[i][j]:
                    cost[i][j] = value
                    splits[i,j] = k
    if (0,n-1) not in splits:
        raise ValueError('Não foi possível fechar o contorno dentro do corpo. Ajuste a seleção ou use um cortador modelado.')
    todo = [(0,n-1)]
    result = []
    while todo:
        i,j = todo.pop()
        if j-i<2:
            continue
        k = splits[i,j]
        result.append((i,k,j))
        todo.extend(((i,k),(k,j)))
    return result


def _repair_inherited_slivers(bm, caps, scale):
    """Repair only inherited roundoff on a copy; leave closing faces exact.

    Returns an owned candidate only on success. The caller still owns bm.
    An unsuccessful repair never invalidates the original face references.
    """
    from .diagnostic import (validate_bmesh_mesh_geometry,
                             sanitize_mesh_micro_degeneracies,
                             validate_mesh_repair_change)
    report = validate_bmesh_mesh_geometry(bm, scale)
    if report['is_valid']:
        return bm, caps
    cap_set = set(caps)
    if (any(bm.faces[i] in cap_set for i in report['degenerate_faces']) or
            any(any(f in cap_set for f in bm.edges[i].link_faces) for i in report['null_edges'])):
        return bm, caps
    def signature(face):
        return (tuple(sorted(tuple(v.co) for v in face.verts)), face.material_index)
    expected = sorted(signature(f) for f in caps)
    candidate = bm.copy()
    accepted = False
    try:
        if not sanitize_mesh_micro_degeneracies(candidate, scale):
            return bm, caps
        layer = candidate.faces.layers.int.get(CONTACT)
        repaired_caps = [f for f in candidate.faces if layer and f[layer]]
        if sorted(signature(f) for f in repaired_caps) != expected:
            return bm, caps
        if not validate_mesh_repair_change(bm, candidate, scale):
            return bm, caps
        accepted = True
        return candidate, repaired_caps
    finally:
        if not accepted:
            candidate.free()


def _validate_caps(bm, caps, contains, scale):
    from .geometry_clearance import cap_crossing_pairs
    from .diagnostic import validate_bmesh_mesh_geometry
    from .geometry_plane import evaluate_bmesh_metrics
    report = validate_bmesh_mesh_geometry(bm,scale)
    metrics = evaluate_bmesh_metrics(bm,scale)
    if not report['is_valid']:
        from .localized_errors import LocalizedGeometryError
        raise LocalizedGeometryError('geometry.region_degenerate', count=len(report['degenerate_faces']), edges=len(report['null_edges']))
    if not metrics['is_manifold'] or metrics['components']!=1 or metrics['volume_mm3']<=1e-4:
        raise ValueError('O fechamento não gerou uma peça única fechada com volume. Ajuste a seleção.')
    if any(not v.is_manifold for v in bm.verts):
        raise ValueError('O fechamento gerou um vértice não-manifold.')
    if cap_crossing_pairs(bm,caps,.0001/scale):
        raise ValueError('O fechamento atravessa a superfície do modelo. Ajuste a seleção.')
    bm.faces.index_update()
    tree = BVHTree.FromBMesh(bm)
    cap_indices = {f.index for f in caps}
    bm.faces.ensure_lookup_table()
    for i,j in tree.overlap(tree):
        if i>=j or i not in cap_indices or j not in cap_indices:
            continue
        if not set(bm.faces[i].verts).intersection(bm.faces[j].verts):
            raise ValueError('Os fechamentos se cruzam. Ajuste a seleção.')
    for face in caps:
        points = [v.co.copy() for v in face.verts]
        if not all(contains(sum((p*w for p,w in zip(points,weights)),Vector())) for weights in WEIGHTS):
            raise ValueError('O fechamento sai do corpo original. Ajuste a seleção.')
    return metrics


def contact_patches(mesh, scale, source_tree=None, partner_tree=None):
    """Connected coplanar physical contact regions, never exterior surfaces."""
    from .geometry_material import _order_boundary_loops
    from .geometry_contract import build_cut_interface
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.normal_update()
        marker = bm.faces.layers.int.get(CONTACT) or bm.faces.layers.int.new(CONTACT)
        labels = bm.faces.layers.int.get(PATCH) or bm.faces.layers.int.new(PATCH)
        for face in bm.faces:
            face[labels] = 0
        if source_tree is not None:
            for face in bm.faces:
                center = face.calc_center_median()
                partner = partner_tree.find_nearest(center) if partner_tree else None
                # Distance from the source alone can misclassify a narrow exterior
                # triangle through BVH roundoff. Require the opposing physical face.
                face[marker] = int(source_tree.find_nearest(center)[3] > .0001/scale
                    and partner is not None and partner[0] is not None
                    and partner[3] <= .001/scale and partner[1].dot(face.normal) < -.99)
        remaining = {f for f in bm.faces if f[marker]}
        groups = []
        tolerance = .001/scale
        while remaining:
            seed = max(remaining,key=lambda f:(f.calc_area(), tuple(sorted(tuple(v.co) for v in f.verts))))
            origin = seed.calc_center_median()
            normal = seed.normal.copy()
            group = {seed}
            remaining.remove(seed)
            stack = [seed]
            while stack:
                face = stack.pop()
                for edge in face.edges:
                    for other in edge.link_faces:
                        if other in remaining and other.normal.dot(normal)>.999999 and all(abs((v.co-origin).dot(normal))<=tolerance for v in other.verts):
                            remaining.remove(other)
                            group.add(other)
                            stack.append(other)
            edges = [e for e in bm.edges if sum(f in group for f in e.link_faces)==1]
            loops = _order_boundary_loops(edges)
            if not loops:
                continue
            coords = [[v.co.copy() for v in loop] for loop in loops]
            triangles = []
            ordered = sorted(group, key=lambda f:f.index)
            for face in ordered:
                from mathutils.geometry import tessellate_polygon
                points = [v.co.copy() for v in face.verts]
                triangles.extend(tuple(points[v].copy() if isinstance(v, int) else v.copy() for v in tri)
                                 for tri in tessellate_polygon([points]))
            area = math.fsum(f.calc_area() for f in ordered)
            center = Vector(tuple(math.fsum(float(f.calc_center_median()[axis])*f.calc_area() for f in ordered)/area for axis in range(3)))
            interface = build_cut_interface(center,normal,[],interface_triangles=triangles,boundary_loops_world=coords,unit_scale=scale,source_mode='REGION')
            groups.append((area,center,group,interface))
        groups.sort(key=lambda g:(-g[0],tuple(round(v*scale,4) for v in g[1])))
        result = []
        for index,(area,center,group,interface) in enumerate(groups):
            for face in group:
                face[labels] = index+1
            result.append(dict(index=index,area_mm2=area*scale*scale,center=list(center),normal=list(interface.normal_a_to_b_world),interface=interface))
        bm.to_mesh(mesh)
        return result
    finally:
        bm.free()


def attach_contacts(report, mesh_a, mesh_b, scale, chosen=-1, source_tree=None):
    patches = contact_patches(mesh_a,scale,source_tree,mesh_tree(mesh_b) if source_tree else None)
    trees = [BVHTree.FromPolygons([v for t in p['interface'].interface_triangles_world for v in t],
             [(i*3,i*3+1,i*3+2) for i in range(len(p['interface'].interface_triangles_world))],all_triangles=True) for p in patches]
    # Transfer A's labels to the matching surface of B by plane and position.
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh_b)
        bm.normal_update()
        label = bm.faces.layers.int.get(PATCH) or bm.faces.layers.int.new(PATCH)
        for face in bm.faces:
            face[label] = 0
            p = face.calc_center_median()
            for patch, tree in zip(patches, trees):
                iface = patch['interface']
                n = iface.normal_a_to_b_world
                if face.normal.dot(n)<-.999999 and abs((p-iface.origin_world).dot(n))<=.001/scale:
                    # Exact contact triangles avoid labeling other coplanar islands.
                    if tree.find_nearest(p)[3]<=.001/scale:
                        face[label] = patch['index']+1
                        break
        bm.to_mesh(mesh_b)
    finally:
        bm.free()
    report['contact_choices'] = [{k:v for k,v in p.items() if k!='interface'} for p in patches]
    if chosen>=0:
        if chosen>=len(patches):
            raise ValueError('O contato escolhido não existe mais. Escolha novamente na prévia.')
        iface = patches[chosen]['interface']
        report['interface'] = iface
        report['interfaces'] = {'A':iface,'B':iface}
    return report


def attach_region_contacts(report, mesh_a, mesh_b, settings, obj, scale, contains):
    """Broad physical regions first; prepare a flat, shared seat only on request."""
    from .geometry_seat import candidate_groups, prepare_planar_seat
    a=bmesh.new();b=bmesh.new()
    try:
        a.from_mesh(mesh_a);b.from_mesh(mesh_b)
        labels=a.faces.layers.int.get(PATCH) or a.faces.layers.int.new(PATCH)
        groups=candidate_groups(a,scale)
        choices=[]
        for f in a.faces:f[labels]=0
        mapping={}
        patch_trees=[]
        largest=groups[0]['area'] if groups else 0
        for index,g in enumerate(groups):
            # Tiny slivers are not offered as independent pin regions.
            eligible=g['axis'] is not None and g['area']>=largest*.01
            if eligible:
                choices.append(dict(index=index,area_mm2=g['area']*scale*scale,
                                    center=list(g['origin']),normal=list(g['axis'])))
            for f in g['faces']:
                f[labels]=index+1 if eligible else 0
                mapping[tuple(sorted(tuple(v.co) for v in f.verts))]=f[labels]
            if eligible:
                vertices=[];polygons=[]
                for face in sorted(g['faces'],key=lambda f:f.index):
                    start=len(vertices);vertices.extend(v.co.copy() for v in face.verts)
                    polygons.append(tuple(range(start,len(vertices))))
                patch_trees.append((index+1,BVHTree.FromPolygons(vertices,polygons)))
        other=b.faces.layers.int.get(PATCH) or b.faces.layers.int.new(PATCH)
        for face in b.faces:
            face[other]=mapping.get(tuple(sorted(tuple(v.co) for v in face.verts)),0)
            if not face[other]:
                # Complementary Boolean surfaces can use different diagonals.
                # Transfer physical contact identity, not an exact vertex tuple.
                center=face.calc_center_median()
                for label,tree in patch_trees:
                    hit=tree.find_nearest(center)
                    if hit[0] is not None and hit[3]*scale<=.001 and hit[1].dot(face.normal)<-.99:
                        face[other]=label;break
        a.to_mesh(mesh_a);b.to_mesh(mesh_b)
    finally:a.free();b.free()
    report['contact_choices']=choices
    chosen=settings.contact_patch_index
    if chosen>=0:
        if not any(p['index']==chosen for p in choices):
            raise ValueError('Esta superfície não permite um encaixe por inserção reta.')
        interface=prepare_planar_seat(mesh_a,mesh_b,chosen,scale,contains)
        report['interface']=interface
        report['interfaces']={'A':interface,'B':interface}
        for item in choices:
            if item['index']==chosen:item['area_mm2']=interface.area_mm2
    gap=settings.part_clearance_mm
    if gap>0:
        from .geometry_contact_gap import shrink_contact,retained_seat,enforce_seat_plane
        amount_a=gap if settings.part_clearance_apply_to=='PART' else gap/2 if settings.part_clearance_apply_to=='BOTH' else 0
        amount_b=gap if settings.part_clearance_apply_to=='CAVITY' else gap/2 if settings.part_clearance_apply_to=='BOTH' else 0
        inside_a=Containment(mesh_tree(mesh_a),.001/scale)
        inside_b=Containment(mesh_tree(mesh_b),.001/scale)
        shrink_contact(mesh_a,amount_a,scale);shrink_contact(mesh_b,amount_b,scale)
        if chosen>=0:
            exterior=mesh_tree(obj.data,obj.matrix_world)
            if amount_a:enforce_seat_plane(mesh_a,interface,-amount_a,scale,inside_a,exterior)
            if amount_b:enforce_seat_plane(mesh_b,interface,amount_b,scale,inside_b,exterior)
            interface.clearance_applied=True
            interface.final_contact_a=retained_seat(mesh_a,interface,scale,-amount_a)
            interface.final_contact_b=retained_seat(mesh_b,interface,scale,amount_b)
            interface.reference_origin_world=interface.origin_world.copy()
            interface.reference_axis_u_world=interface.axis_u_world.copy()
    # Refresh metrics after planar preparation / physical clearance.
    from .geometry_plane import evaluate_bmesh_metrics
    for side,mesh in (('A',mesh_a),('B',mesh_b)):
        bm=bmesh.new()
        try:
            bm.from_mesh(mesh);report[side]=evaluate_bmesh_metrics(bm,scale)
        finally:bm.free()
    report['sum_volume_mm3']=report['A']['volume_mm3']+report['B']['volume_mm3']
    return report


def slice_region(obj, settings, scene, mesh_a, mesh_b):
    from .diagnostic import get_scene_scale_to_mm
    from .geometry_clearance import triangulated_source_mesh
    from .geometry_solid import ensure_solid_outward_normals
    from .geometry_material import _order_boundary_loops
    from .geometry_contract import boundary_normal
    if obj.mode=='EDIT':
        obj.update_from_editmode()
    if settings.split_mode != 'MATERIAL' and (settings.region_target!=obj or mesh_signature(obj.data)!=settings.region_mesh_signature):
        raise ValueError('A malha mudou. Selecione e capture as faces novamente.')
    if any(m.show_viewport for m in obj.modifiers):
        raise ValueError('Aplique os modificadores em uma cópia antes de capturar a região de faces.')
    if settings.invert_sides:
        raise ValueError('Neste modo A é a região selecionada. Para trocar o lado do pino use Macho A/B.')
    if abs(obj.matrix_world.determinant())<1e-12:
        raise ValueError('O alvo possui escala nula.')
    selected = {int(i) for i in settings.region_face_indices.split(',') if i.strip()}
    if settings.split_mode == 'MATERIAL':
        from .geometry_material import get_material_regions
        bm=bmesh.new()
        try:
            bm.from_mesh(obj.data)
            groups=get_material_regions(bm,settings.material_split_index)
            if not 0<=settings.material_region_index<len(groups):raise ValueError('Escolha uma região de material válida.')
            selected=set(groups[settings.material_region_index])
        finally:bm.free()
    if not selected or min(selected)<0 or max(selected)>=len(obj.data.polygons) or len(selected)==len(obj.data.polygons):
        raise ValueError('Selecione uma região parcial da superfície para fechar.')
    scale = get_scene_scale_to_mm(scene)
    canonical = triangulated_source_mesh(obj.data)
    base = a = b = None
    try:
        obj.data.calc_loop_triangles()
        original_ids = [t.polygon_index for t in obj.data.loop_triangles]
        base = bmesh.new();base.from_mesh(canonical);base.transform(obj.matrix_world)
        ensure_solid_outward_normals(base)
        base.verts.index_update();base.faces.index_update()
        if any(not e.is_manifold for e in base.edges) or any(not v.is_manifold for v in base.verts):
            raise ValueError('Corrija os defeitos topológicos do alvo antes de fechar a região.')
        region = {f.index for f in base.faces if original_ids[f.index] in selected}
        boundary = [e for e in base.edges if sum(f.index in region for f in e.link_faces)==1]
        loops = _order_boundary_loops(boundary)
        if not loops:
            raise ValueError('A região precisa de contornos fechados sem bifurcações.')
        loops.sort(key=lambda loop:min(v.index for v in loop))
        contains = Containment(mesh_tree(canonical,obj.matrix_world),.0001/scale)
        # A contour with vanishing projected edges can require perpendicular
        # closure patches; a single projected triangulation cannot represent them.
        normals = [boundary_normal([v.co for v in loop]) for loop in loops]
        folded = any((q.co-p.co).cross(n).length <= max(1e-12, (q.co-p.co).length*1e-6)
                     for loop,n in zip(loops,normals)
                     for p,q in zip(loop,loop[1:]+loop[:1]))
        from .geometry_region_convex import projection_is_simple
        folded = folded or any(not projection_is_simple([v.co for v in loop],n,scale)
                               for loop,n in zip(loops,normals))
        nonplanar = any(max(abs((v.co-loop[0].co).dot(n))*scale for v in loop)>.001
                        for loop,n in zip(loops,normals))
        if folded or nonplanar:
            from .geometry_region_convex import complete
            completed = complete(obj, selected, scale)
            if completed is not None:
                part,rest = completed
                try:
                    for mesh in (mesh_a,mesh_b):
                        mesh.materials.clear()
                        for material in obj.data.materials:mesh.materials.append(material)
                    part_bm=bmesh.new();rest_bm=bmesh.new()
                    try:
                        part_bm.from_mesh(part);rest_bm.from_mesh(rest)
                        ma=_validate_caps(part_bm,[f for f in part_bm.faces if f[part_bm.faces.layers.int[CONTACT]]],contains,scale)
                        mb=_validate_caps(rest_bm,[f for f in rest_bm.faces if f[rest_bm.faces.layers.int[CONTACT]]],contains,scale)
                        part_bm.to_mesh(mesh_a);rest_bm.to_mesh(mesh_b)
                    finally:part_bm.free();rest_bm.free()
                    report=dict(A=ma,B=mb,sum_volume_mm3=ma['volume_mm3']+mb['volume_mm3'],interface=None,interfaces={})
                    report=attach_region_contacts(report,mesh_a,mesh_b,settings,obj,scale,contains)
                    apply_extracted_region_material(mesh_a,settings)
                    return report
                finally:
                    bpy.data.meshes.remove(part);bpy.data.meshes.remove(rest)
            if folded:
                from .localized_errors import LocalizedGeometryError
                raise LocalizedGeometryError('geometry.region_ambiguous_completion')
        a = base.copy();b = base.copy()
        for bm in (a,b):bm.verts.ensure_lookup_table();bm.faces.ensure_lookup_table()
        av = [[a.verts[v.index] for v in loop] for loop in loops]
        bv = [[b.verts[v.index] for v in loop] for loop in loops]
        bmesh.ops.delete(a,geom=[f for f in a.faces if f.index not in region],context='FACES')
        bmesh.ops.delete(b,geom=[f for f in b.faces if f.index in region],context='FACES')
        la = a.faces.layers.int.get(CONTACT) or a.faces.layers.int.new(CONTACT)
        lb = b.faces.layers.int.get(CONTACT) or b.faces.layers.int.new(CONTACT)
        from .interface_history import archive_contact_marks
        for bm,layer in ((a,la),(b,lb)):
            archive_contact_marks(bm)
        caps_a=[];caps_b=[]
        for loop,va,vb in zip(loops,av,bv):
            coords = [v.co.copy() for v in loop]
            triangles = closing_triangles(coords,boundary_normal(coords),va,vb,a,b,contains,scale)
            for i,j,k in triangles:
                fa=a.faces.new((va[i],va[j],va[k]));fa[la]=1;fa.material_index=0;caps_a.append(fa)
                fb=b.faces.new((vb[k],vb[j],vb[i]));fb[lb]=1;fb.material_index=0;caps_b.append(fb)
        for bm in (a,b):ensure_solid_outward_normals(bm)
        repaired, caps_a = _repair_inherited_slivers(a, caps_a, scale)
        if repaired is not a:
            a.free(); a = repaired
        repaired, caps_b = _repair_inherited_slivers(b, caps_b, scale)
        if repaired is not b:
            b.free(); b = repaired
        ma=_validate_caps(a,caps_a,contains,scale);mb=_validate_caps(b,caps_b,contains,scale)
        from .diagnostic import stable_signed_volume_mm3
        total=abs(stable_signed_volume_mm3(base,scale))
        error=abs(abs(stable_signed_volume_mm3(a,scale))+abs(stable_signed_volume_mm3(b,scale))-total)
        if error>max(.001,total*1e-8):
            raise ValueError('O fechamento não conservou o volume. Ajuste a seleção.')
        for bm,mesh in ((a,mesh_a),(b,mesh_b)):
            mesh.materials.clear()
            for mat in obj.data.materials:mesh.materials.append(mat)
            bm.to_mesh(mesh)
        report=dict(A=ma,B=mb,sum_volume_mm3=ma['volume_mm3']+mb['volume_mm3'],interface=None,interfaces={})
        report = attach_region_contacts(report,mesh_a,mesh_b,settings,obj,scale,contains)
        apply_extracted_region_material(mesh_a, settings)
        return report
    finally:
        for bm in (base,a,b):
            if bm is not None:bm.free()
        bpy.data.meshes.remove(canonical)


def apply_extracted_region_material(mesh, settings):
    """Color the entire material-region piece, including newly generated faces.

    Run again after connector Booleans, which can transfer the other part's
    material onto pin walls. Face-selection cuts keep their existing colors.
    """
    if (settings.split_mode == 'MATERIAL'
            and settings.material_extraction_mode == 'WHOLE'
            and settings.material_interface_mat_mode == 'EXTRACTED'):
        for face in mesh.polygons:
            face.material_index = settings.material_split_index
