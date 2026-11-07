"""Offset all marked contacts together, preserving their shared corner constraints."""
import bpy
import bmesh
from .geometry_region import CONTACT, PATCH, mesh_tree, Containment
from .localized_errors import LocalizedGeometryError


def _offset_contact_vertices(mesh, amount_mm, scale):
    """Move a copy by local contact/exterior plane constraints, then validate it.

    Each contact normal requests the full gap. Adjacent exterior planes
    prevent outward expansion. In particular, two
    perpendicular contacts move their common vertex along both axes, rather
    than averaging the normals or constructing a Solidify miter.
    """
    if amount_mm <= 0:
        return
    import math
    from mathutils import Vector
    from .diagnostic import validate_bmesh_mesh_geometry
    from .geometry_plane import evaluate_bmesh_metrics
    from .geometry_clearance import cap_crossing_pairs
    from .geometry_solid import ensure_solid_outward_normals
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        bm.normal_update()
        marker = bm.faces.layers.int.get(CONTACT)
        contacts = [f for f in bm.faces if marker and f[marker]]
        if not contacts:
            raise ValueError('Não há superfícies de contato para aplicar a folga.')
        before = abs(bm.calc_volume())
        original_tree = mesh_tree(mesh)
        contains = Containment(original_tree, .0001/scale)
        gap = amount_mm/scale
        proposals = {}
        for vert in {v for f in contacts for v in f.verts}:
            rows, values = [], []
            for face in vert.link_faces:
                n = face.normal
                target = -gap if face[marker] else 0.0
                # Repeated coplanar triangles must not change the solution.
                if any(abs(target-old)<gap*1e-7 and n.dot(Vector(row))>1-1e-7
                       for row,old in zip(rows,values)):
                    continue
                rows.append(tuple(n));values.append(target)
            tolerance = max(.0002/scale, gap*.005)
            # Dykstra projection gives the smallest displacement satisfying ALL
            # contact halfspaces. Exterior facets constrain it inward rather
            # than forcing incompatible equalities at curved/creased rims.
            normals=[Vector(n) for n in rows]
            move=Vector();corrections=[Vector() for _ in normals]
            for iteration in range(256):
                previous=move.copy()
                for i,(normal,limit) in enumerate(zip(normals,values)):
                    candidate=move+corrections[i]
                    offset=max(0.0,normal.dot(candidate)-limit)
                    move=candidate-normal*offset
                    corrections[i]=candidate-move
                if ((move-previous).length<tolerance*.01 and
                    max(n.dot(move)-v for n,v in zip(normals,values))<tolerance*.01):
                    break
            if (not all(math.isfinite(x) for x in move) or
                max(n.dot(move)-v for n,v in zip(normals,values))>tolerance):
                raise LocalizedGeometryError('geometry.contact_gap_infeasible')
            if move.length > gap*8:
                raise LocalizedGeometryError('geometry.contact_gap_miter')
            point = vert.co+move
            if not contains(point):
                raise ValueError('A folga ultrapassou a peça original.')
            proposals[vert] = point
        for vert,point in proposals.items():
            vert.co = point
        bm.normal_update()
        # Contacts must keep their orientation, with no overturned triangles.
        report = validate_bmesh_mesh_geometry(bm,scale)
        metrics = evaluate_bmesh_metrics(bm,scale)
        if (not report['is_valid'] or not metrics['is_manifold'] or
                metrics['components']!=1 or any(not v.is_manifold for v in bm.verts) or
                abs(bm.calc_volume())>=before):
            raise ValueError('Esta folga não preserva uma peça fechada. Reduza a folga entre peças.')
        if cap_crossing_pairs(bm,contacts,.0001/scale):
            raise LocalizedGeometryError('geometry.contact_gap_crossing')
        # Test the actual interior of each moved face, not only its vertices.
        if any(not contains(f.calc_center_median()) for f in bm.faces):
            raise ValueError('A folga ultrapassou a peça original.')
        ensure_solid_outward_normals(bm)
        bm.to_mesh(mesh)
        mesh.update()
    finally:
        bm.free()


def shrink_contact(mesh, amount_mm, scale):
    """Try topology-preserving constraints, or a validated trim at tight rims."""
    if amount_mm<=0:return
    try:
        _offset_contact_vertices(mesh,amount_mm,scale)
        return
    except ValueError as direct_error:
        # A pin seat can contain a thin transition whose topology must change.
        # Keep the input untouched until the independent trim also passes.
        candidate=mesh.copy()
        try:
            _trim_contact_band(candidate,amount_mm,scale)
            original=bmesh.new()
            try:
                original.from_mesh(mesh);original.normal_update()
                marker=original.faces.layers.int.get(CONTACT)
                contacts=[f for f in original.faces if marker and f[marker]]
                tolerance=max(.001,amount_mm*.02)/scale
                for face in contacts:
                    n=face.normal;d=n.dot(face.verts[0].co)
                    # Supporting contact planes must retreat everywhere. This
                    # detects the unchanged corner teeth of the old band path.
                    if all(n.dot(v.co)<=d+tolerance for v in original.verts):
                        if any(n.dot(v.co)>d-amount_mm/scale+tolerance for v in candidate.vertices):
                            raise LocalizedGeometryError('geometry.contact_gap_corner')
                tree=mesh_tree(candidate)
                boundary=[e for e in original.edges if sum(f in contacts for f in e.link_faces)==1]
                from mathutils.geometry import intersect_point_line
                for face in contacts:
                    p=face.calc_center_median()
                    near_rim=False
                    for edge in boundary:
                        a,b=(v.co for v in edge.verts)
                        _,fraction=intersect_point_line(p,a,b)
                        nearest=a+(b-a)*max(0.,min(1.,fraction))
                        if (p-nearest).length<2*amount_mm/scale:
                            near_rim=True;break
                    if near_rim:continue
                    # Contact interiors must not silently remain at zero gap.
                    epsilon=.001/scale
                    hit=tree.ray_cast(p+face.normal*epsilon,-face.normal)
                    if hit[0] is None or hit[3]-epsilon<(amount_mm-max(.002,amount_mm*.02))/scale:
                        raise LocalizedGeometryError('geometry.contact_gap_missing')
            finally:original.free()
            bm=bmesh.new()
            try:bm.from_mesh(candidate);bm.to_mesh(mesh)
            finally:bm.free()
        except ValueError as trim_error:
            raise trim_error from direct_error
        finally:bpy.data.meshes.remove(candidate)


def enforce_seat_plane(mesh,interface,shift_mm,scale,inside,exterior_tree):
    """Restore an exact plane after solidify's corner miters, only at internal vertices."""
    from .geometry_region import _validate_caps
    n=interface.normal_a_to_b_world
    origin=interface.origin_world+n*(shift_mm/scale)
    footprint=mesh_tree_from_triangles(interface.interface_triangles_world)
    bm=bmesh.new()
    try:
        bm.from_mesh(mesh);bm.normal_update()
        marker=bm.faces.layers.int.get(CONTACT) or bm.faces.layers.int.new(CONTACT)
        for face in bm.faces:
            hit=exterior_tree.find_nearest(face.calc_center_median())
            face[marker]=int(hit[3]>.001/scale or face.normal.dot(hit[1])<.99)
        selected=[]
        for face in bm.faces:
            p=face.calc_center_median();projected=p-n*(p-interface.origin_world).dot(n)
            if (abs(face.normal.dot(n))>.995 and footprint.find_nearest(projected)[3]<=.001/scale
                    and abs((p-origin).dot(n))*scale<=max(.05,abs(shift_mm)*.5)):
                selected.append(face)
        if not selected:raise ValueError('A folga removeu a área plana de montagem.')
        for vert in {v for f in selected for v in f.verts}:
            point=vert.co-n*(vert.co-origin).dot(n)
            if (point-vert.co).length*scale>.0001 and exterior_tree.find_nearest(vert.co)[3]*scale<.001:
                raise ValueError('A folga não permite manter a área plana sem alterar o exterior.')
            if not inside(point):raise ValueError('A área plana com folga ultrapassou a peça original.')
            vert.co=point
        bm.normal_update()
        marker=bm.faces.layers.int.get(CONTACT)
        _validate_caps(bm,[f for f in bm.faces if marker and f[marker]],inside,scale)
        bm.to_mesh(mesh)
    finally:bm.free()


def retained_seat(mesh,interface,scale,shift_mm=0):
    """Measure the actual parallel plane after trimming; preserve the nominal UV frame."""
    from .geometry_clearance import final_contact_patch
    bm=bmesh.new()
    try:
        bm.from_mesh(mesh);bm.normal_update()
        marker=bm.faces.layers.int.get(CONTACT) or bm.faces.layers.int.new(CONTACT)
        # The actual seat may lie on either side of the nominal plane.
        n=interface.normal_a_to_b_world
        expected_origin=interface.origin_world+n*(shift_mm/scale)
        tree=mesh_tree_from_triangles(interface.interface_triangles_world)
        for face in bm.faces:
            p=face.calc_center_median();projected=p-n*(p-interface.origin_world).dot(n)
            near=tree.find_nearest(projected)
            face[marker]=int(abs(face.normal.dot(n))>.999999 and near[0] is not None and near[3]<.001/scale
                and max(abs((v.co-expected_origin).dot(n))*scale for v in face.verts)<=.001)
        direction=n if sum(f.calc_area()*f.normal.dot(n) for f in bm.faces if f[marker])>=0 else -n
        patch=final_contact_patch(bm,direction,scale)
        if patch is None:raise ValueError('A folga removeu a superfície plana dos pinos.')
        if abs(patch['normal'].dot(n))<.999999:raise ValueError('A folga inclinou a superfície de montagem.')
        if max(abs((p-patch['origin']).dot(n))*scale for tri in patch['triangles'] for p in tri)>.001:
            raise ValueError('A folga deixou a superfície de montagem fora do plano. Reduza a folga.')
        return patch
    finally:bm.free()


def mesh_tree_from_triangles(triangles):
    from mathutils.bvhtree import BVHTree
    return BVHTree.FromPolygons([v for tri in triangles for v in tri],[(3*i,3*i+1,3*i+2) for i in range(len(triangles))],all_triangles=True)


def _trim_contact_band(mesh, amount_mm, scale):
    if amount_mm<=0:return
    from .geometry_clearance import triangulated_source_mesh, remove_boolean_wires, weld_boolean_roundoff
    from .diagnostic import validate_bmesh_mesh_geometry, sanitize_mesh_micro_degeneracies
    from .geometry_plane import evaluate_bmesh_metrics
    from .geometry_solid import ensure_solid_outward_normals
    objects=[];meshes=[];evaluated=[]
    source=bmesh.new();band=bmesh.new()
    try:
        source.from_mesh(mesh);source.normal_update()
        reference_tree=mesh_tree(mesh)
        reference_triangles=list(mesh.loop_triangles)
        layer=source.faces.layers.int.get(CONTACT)
        contacts=[f for f in source.faces if layer and f[layer]]
        original_volume=abs(source.calc_volume())
        if not contacts:raise ValueError('Não há superfícies de contato para aplicar a folga.')
        vertices={}
        for face in contacts:
            points=[]
            for vert in face.verts:
                if vert not in vertices:vertices[vert]=band.verts.new(vert.co)
                points.append(vertices[vert])
            band.faces.new(points)
        # Build the inner skin from the same halfspace constraints as the
        # topology-preserving path. Unlike Solidify's averaged normals, every
        # incident contact requests the full perpendicular distance.
        from mathutils import Vector
        selected=set(contacts);inner={};gap=amount_mm/scale
        for vert in vertices:
            normals=[]
            for face in vert.link_faces:
                if face in selected and not any(face.normal.dot(n)>1-1e-7 for n in normals):normals.append(face.normal.copy())
            move=Vector();corrections=[Vector() for _ in normals]
            for _ in range(256):
                previous=move.copy()
                for i,n in enumerate(normals):
                    candidate=move+corrections[i];move=candidate-n*max(0.,n.dot(candidate)+gap);corrections[i]=candidate-move
                if (move-previous).length<gap*1e-7:break
            if max(n.dot(move)+gap for n in normals)>max(.0002/scale,gap*.005) or move.length>8*gap:
                raise LocalizedGeometryError('geometry.contact_gap_infeasible')
            inner[vert]=band.verts.new(vert.co+move)
        for face in contacts:
            band.faces.new(tuple(inner[v] for v in reversed(list(face.verts))))
            for loop in face.loops:
                if sum(f in selected for f in loop.edge.link_faces)==1:
                    a=loop.vert;b=loop.link_loop_next.vert
                    band.faces.new((vertices[b],vertices[a],inner[a],inner[b]))
        band.normal_update()
        band_mesh=bpy.data.meshes.new('_interface_gap_band');meshes.append(band_mesh);band.to_mesh(band_mesh)
        closed=triangulated_source_mesh(band_mesh);meshes.append(closed)
        check=bmesh.new()
        try:
            check.from_mesh(closed);ensure_solid_outward_normals(check)
            if any(not e.is_manifold for e in check.edges):raise ValueError('A faixa de folga não é fechada.')
            check.to_mesh(closed)
        finally:check.free()
        operand=bpy.data.objects.new('_interface_gap_operand',closed);objects.append(operand);bpy.context.scene.collection.objects.link(operand)
        work_mesh=triangulated_source_mesh(mesh);meshes.append(work_mesh)
        work=bpy.data.objects.new('_interface_gap_source',work_mesh);objects.append(work);bpy.context.scene.collection.objects.link(work)
        modifier=work.modifiers.new('Trim physical clearance','BOOLEAN');modifier.operation='DIFFERENCE';modifier.solver='MANIFOLD' if 'MANIFOLD' in {item.identifier for item in bpy.types.BooleanModifier.bl_rna.properties['solver'].enum_items} else 'EXACT';modifier.object=operand
        bpy.context.view_layer.update();ev=work.evaluated_get(bpy.context.evaluated_depsgraph_get());evaluated.append(ev)
        result=triangulated_source_mesh(ev.to_mesh());meshes.append(result);bm=bmesh.new()
        try:
            bm.from_mesh(result);remove_boolean_wires(bm);weld_boolean_roundoff(bm,scale)
            sanitize_mesh_micro_degeneracies(bm,scale)
            remove_boolean_wires(bm);ensure_solid_outward_normals(bm)
            validation=validate_bmesh_mesh_geometry(bm,scale);metrics=evaluate_bmesh_metrics(bm,scale)
            if not validation['is_valid'] or not metrics['is_manifold'] or any(not v.is_manifold for v in bm.verts) or metrics['components']!=1 or abs(bm.calc_volume())>=original_volume:
                raise ValueError('Esta folga não preserva uma peça fechada. Reduza a folga entre peças.')
            inside=Containment(mesh_tree(mesh),.001/scale)
            if not all(inside(v.co) for v in bm.verts):raise ValueError('A folga ultrapassou a peça original.')
            # Boolean operands use explicit tessellation, so restore physical-area
            # labels by projection instead of relying on modifier face indices.
            contact=bm.faces.layers.int.get(CONTACT) or bm.faces.layers.int.new(CONTACT)
            labels=bm.faces.layers.int.get(PATCH) or bm.faces.layers.int.new(PATCH)
            old_contact=mesh.attributes.get(CONTACT);old_labels=mesh.attributes.get(PATCH)
            for face in bm.faces:
                hit=reference_tree.find_nearest(face.calc_center_median())
                index=reference_triangles[hit[2]].polygon_index if hit[2] is not None else -1
                valid=index>=0 and hit[3]<=amount_mm*4/scale and hit[1].dot(face.normal)>.9
                face[contact]=int(valid and old_contact is not None and old_contact.data[index].value)
                face[labels]=old_labels.data[index].value if valid and old_labels is not None else 0
            bm.to_mesh(mesh);mesh.update()
        finally:bm.free()
    finally:
        for ev in reversed(evaluated):ev.to_mesh_clear()
        for obj in reversed(objects):bpy.data.objects.remove(obj,do_unlink=True)
        for data in reversed(meshes):
            if data.users==0:bpy.data.meshes.remove(data)
        source.free();band.free()



