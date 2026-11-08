"""Local, measured clearance bands for an already validated natural interface.

The zero-gap cut defines the shape once. A closed blade trims each selected
side without forcing shared vertices to satisfy unrelated exterior planes.
"""
import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from types import SimpleNamespace
from .localized_errors import LocalizedGeometryError


def _triangles(bm):
    """Use Blender's visible diagonals, including nonplanar editable quads."""
    marker = bm.faces.layers.int.get('splitter_contact_surface')
    if marker is None:
        return []
    marked = [bool(face[marker]) for face in bm.faces]
    mesh = bpy.data.meshes.new('_measured_contact')
    try:
        bm.to_mesh(mesh)
        mesh.calc_loop_triangles()
        return [tuple(mesh.vertices[i].co.copy() for i in tri.vertices)
                for tri in mesh.loop_triangles if marked[tri.polygon_index]]
    finally:
        bpy.data.meshes.remove(mesh)


def _tree(triangles):
    if not triangles:
        raise LocalizedGeometryError('geometry.clearance_unresolved')
    return BVHTree.FromPolygons([p for t in triangles for p in t],
        [(3*i,3*i+1,3*i+2) for i in range(len(triangles))],all_triangles=True)


def _samples(triangles):
    for tri in triangles:
        for weights in ((1/3,1/3,1/3),(.6,.2,.2),(.2,.6,.2),(.2,.2,.6)):
            yield sum((p*w for p,w in zip(tri,weights)),Vector())


def _visible_source(bm):
    from .geometry_loop import _triangulate_retained_source_faces
    mesh=bpy.data.meshes.new('_blade_reference')
    source=bm.copy()
    try:
        source.to_mesh(mesh)
        _triangulate_retained_source_faces(source,
            SimpleNamespace(data=mesh,matrix_world=Matrix.Identity(4)),range(len(mesh.polygons)))
        source.normal_update()
        return source
    except Exception:
        source.free()
        raise
    finally:
        bpy.data.meshes.remove(mesh)


def trim_contact_blade(bm, source_object, gap_mm, scale, reference=None, outward=False):
    from .geometry_material import _order_boundary_loops, _get_orthonormal_basis
    from .geometry_contract import boundary_normal
    from .geometry_loop import _point_in_poly_2d, _restore_retained_source_faces
    from .geometry_clearance import subtract_closed_region, remove_boolean_wires
    source=_visible_source(bm)
    surface=None
    sheet=bmesh.new();knife=None;mesh=None;evaluated=None;cutter=None;result=None
    try:
        surface=_visible_source(reference) if reference is not None else source
        marker=surface.faces.layers.int.get('splitter_contact_surface')
        caps=[f for f in surface.faces if marker and f[marker]]
        if not caps:
            raise LocalizedGeometryError('geometry.clearance_unresolved')
        cap_set=set(caps)
        source_marker=source.faces.layers.int.get('splitter_contact_surface')
        source_template=next((f for f in source.faces if source_marker and f[source_marker]),None)
        if source_template is None:
            raise LocalizedGeometryError('geometry.clearance_unresolved')
        edges=[e for e in surface.edges if sum(f in cap_set for f in e.link_faces)==1]
        loops=_order_boundary_loops(edges)
        if len(loops)!=1 or not caps:
            raise LocalizedGeometryError('geometry.clearance_unresolved')
        loop=loops[0]
        normal=sum((f.normal*f.calc_area() for f in caps),Vector()).normalized()
        if normal.length<.9:
            raise LocalizedGeometryError('geometry.clearance_unresolved')
        if boundary_normal([v.co for v in loop]).dot(normal)<0:loop.reverse()
        center=sum((v.co for v in loop),Vector())/len(loop)
        u,v=_get_orthonormal_basis(normal)
        polygon=[Vector(((p.co-center).dot(u),(p.co-center).dot(v))) for p in loop]
        if any(not _point_in_poly_2d(point*t,polygon) for point in polygon for t in (.25,.5,.75)):
            raise LocalizedGeometryError('geometry.clearance_unresolved')
        extent=max((p.co-center).length for p in loop)*2
        extension=max(4*gap_mm/scale,.05*extent,.5/scale)
        names=list(source.faces.layers.int.keys())
        layers={name:sheet.faces.layers.int.new(name) for name in names}
        lookup={p:sheet.verts.new(p.co) for p in {p for f in caps for p in f.verts}}
        def face(vertices,template):
            if reference is not None:template=source_template
            created=sheet.faces.new(vertices);created.material_index=template.material_index
            for name,layer in layers.items():created[layer]=template[source.faces.layers.int[name]]
            return created
        for f in caps:face([lookup[p] for p in f.verts],f)
        outer=[]
        for p in loop:
            direction=p.co-center;direction-=normal*direction.dot(normal)
            outer.append(sheet.verts.new(p.co+direction.normalized()*extension))
        for i,p in enumerate(loop):
            j=(i+1)%len(loop)
            adjacent=next(f for f in p.link_faces if f in cap_set)
            face([lookup[p],outer[i],outer[j],lookup[loop[j]]],adjacent)
        # Refine only the cutter. The supporting surface and exterior stay fixed.
        bmesh.ops.triangulate(sheet,faces=list(sheet.faces))
        bmesh.ops.subdivide_edges(sheet,edges=list(sheet.edges),cuts=3,use_grid_fill=True)
        sheet.normal_update()
        mesh=bpy.data.meshes.new('_clearance_blade');sheet.to_mesh(mesh)
        knife=bpy.data.objects.new('_clearance_blade',mesh);bpy.context.scene.collection.objects.link(knife)
        modifier=knife.modifiers.new('Local clearance','SOLIDIFY')
        modifier.solidify_mode='NON_MANIFOLD';modifier.nonmanifold_thickness_mode='CONSTRAINTS'
        modifier.thickness=gap_mm/scale;modifier.offset=1 if outward else -1;modifier.thickness_clamp=0
        modifier.use_even_offset=True;modifier.use_quality_normals=True
        bpy.context.view_layer.update()
        evaluated=knife.evaluated_get(bpy.context.evaluated_depsgraph_get())
        cutter=bmesh.new();cutter.from_mesh(evaluated.to_mesh());cutter.normal_update()
        if any(not e.is_manifold for e in cutter.edges):
            raise LocalizedGeometryError('geometry.clearance_unresolved')
        result=subtract_closed_region(source,cutter,scale)
        if abs(result.calc_volume())>=abs(source.calc_volume()) or abs(result.calc_volume())*scale**3<1e-4:
            raise LocalizedGeometryError('geometry.clearance_excessive')
        _restore_retained_source_faces(result,source_object)
        remove_boolean_wires(result)
        if any(not e.is_manifold for e in result.edges):
            raise LocalizedGeometryError('geometry.clearance_unresolved')
        returned=result;result=None
        return returned
    finally:
        if result is not None:result.free()
        if cutter is not None:cutter.free()
        if evaluated is not None:evaluated.to_mesh_clear()
        if knife is not None:bpy.data.objects.remove(knife,do_unlink=True)
        if mesh is not None:bpy.data.meshes.remove(mesh)
        sheet.free();source.free()
        if reference is not None and surface is not None:surface.free()


def measure_gap(a,b,reference,requested,scale):
    triangles=[_triangles(part) for part in (a,b)];trees=[_tree(t) for t in triangles]
    distances=[];interior=[]
    ref_tree=_tree(_triangles(reference))
    marker=reference.faces.layers.int.get('splitter_contact_surface')
    boundary=[e for e in reference.edges if sum(bool(f[marker]) for f in e.link_faces)==1]
    def boundary_distance(p):
        values=[]
        for edge in boundary:
            x,y=(v.co for v in edge.verts);d=y-x
            t=max(0.,min(1.,(p-x).dot(d)/d.length_squared))
            values.append((p-(x+d*t)).length)
        return min(values,default=0.)
    for source,tree in ((triangles[0],trees[1]),(triangles[1],trees[0])):
        for p in _samples(source):
            value=tree.find_nearest(p)[3]*scale;distances.append(value)
            if boundary_distance(ref_tree.find_nearest(p)[0])*scale>.001:
                interior.append(value)
    normal_distances=[];misses=0;epsilon=.0001/scale
    for tri in _triangles(reference):
        normal=(tri[1]-tri[0]).cross(tri[2]-tri[0]).normalized()
        for p in _samples([tri]):
            hit_a=trees[0].ray_cast(p+normal*epsilon,-normal)
            hit_b=trees[1].ray_cast(p-normal*epsilon,normal)
            if hit_a[0] is None or hit_b[0] is None:misses+=1;continue
            normal_distances.append((hit_a[3]+hit_b[3]-2*epsilon)*scale)
    tolerance=max(.005,.05*requested)
    import os
    if os.environ.get('SPLITTER_BLADE_DEBUG'):
        print('BLADE_MEASURE', requested, (min(distances), max(distances)),
              (min(interior), max(interior)) if interior else None,
              (min(normal_distances), max(normal_distances)) if normal_distances else None,
              'misses', misses, flush=True)
    # The extended sheet also cuts the outside rim. Those faces can project
    # beyond the original contact footprint and have no opposing surface.
    # Validate the shared interior; retain the unfiltered range for reporting.
    if (not normal_distances or not interior or misses or min(distances)<=0
            or min(interior)<requested-tolerance or max(interior)>requested+tolerance
            or min(normal_distances)<requested-tolerance or max(normal_distances)>requested+tolerance):
        raise LocalizedGeometryError('geometry.clearance_unresolved')
    return dict(requested_mm=requested,minimum_mm=min(distances),maximum_mm=max(distances),
        normal_minimum_mm=min(normal_distances),normal_maximum_mm=max(normal_distances),
        interior_minimum_mm=min(interior),interior_maximum_mm=max(interior),
        tolerance_mm=tolerance,samples=len(distances),interior_samples=len(interior),
        normal_samples=len(normal_distances))


def apply_blade_pair(a,b,obj,gap,apply_to,scale):
    factors={'PART':(1.,0.),'CAVITY':(0.,1.),'BOTH':(.5,.5)}
    if apply_to not in factors:raise LocalizedGeometryError('geometry.clearance_unresolved')
    results=[]
    try:
        for side,(source,fraction) in enumerate(zip((a,b),factors[apply_to])):
            results.append(trim_contact_blade(source,obj,gap*fraction,scale,
                reference=a if side else None,outward=bool(side)) if fraction else source.copy())
        measured=measure_gap(*results,a,gap,scale)
        return (*results,measured)
    except Exception:
        for part in results:part.free()
        raise


def validate_natural_surface(result,obj,scale):
    from .geometry_region import Containment,mesh_tree
    contains=Containment(mesh_tree(obj.data,obj.matrix_world),.0001/scale)
    triangles = [_triangles(part) for part in result]
    if any(not contains(p) for side in triangles for p in _samples(side)):
        raise LocalizedGeometryError('geometry.closing_outside')
    if not getattr(result.interface, 'clearance_applied', False):
        for source, target in ((triangles[0], triangles[1]), (triangles[1], triangles[0])):
            tree = _tree(target)
            if any(tree.find_nearest(p)[3]*scale > .0001 for p in _samples(source)):
                raise LocalizedGeometryError('geometry.clearance_unresolved')


def paired_contact_patches(a,b,axis,scale):
    """Select a common local planar footprint rather than flattening the cut."""
    from .geometry_region import contact_patches
    from .geometry_plane import common_planar_interface,PlaneSliceError
    meshes=[]
    try:
        groups=[]
        for part,direction in ((a,axis),(b,-axis)):
            copy=_visible_source(part)
            try:
                mesh=bpy.data.meshes.new('_local_pin_contacts');meshes.append(mesh);copy.to_mesh(mesh)
            finally:copy.free()
            patches=contact_patches(mesh,scale)
            groups.append([p for p in patches if Vector(p['normal']).dot(direction)>.2][:16])
        best=None
        for pa in groups[0]:
            ia=pa['interface'];na=ia.normal_a_to_b_world
            for pb in groups[1]:
                ib=pb['interface'];nb=ib.normal_a_to_b_world
                if na.dot(nb)>-.999:continue
                la=[[ia.uv_to_world(*p) for p in poly] for poly in ia.outer_contours_uv+ia.hole_contours_uv]
                lb=[[ib.uv_to_world(*p) for p in poly] for poly in ib.outer_contours_uv+ib.hole_contours_uv]
                try:common=common_planar_interface(la,lb,ia.origin_world,na,scale,include_triangles=True)
                except (PlaneSliceError,ValueError):continue
                triangles=common.interface_triangles_world
                area=sum((t[1]-t[0]).cross(t[2]-t[0]).length/2 for t in triangles)
                if area<=1e-10 or (best and area<=best[0]):continue
                loops=[[common.uv_to_world(*p) for p in poly] for poly in common.outer_contours_uv+common.hole_contours_uv]
                def patch(origin,normal,project):
                    rings=[[project(p) for p in loop] for loop in loops]
                    return dict(origin=origin.copy(),normal=normal.copy(),loops=rings,
                        boundary=max(rings,key=len),triangles=[tuple(project(p) for p in (t if normal.dot(na)>0 else tuple(reversed(t)))) for t in triangles])
                def project_b(p):return p+na*((ib.origin_world-p).dot(nb)/na.dot(nb))
                best=(area,patch(common.origin_world,na,lambda p:p.copy()),
                      patch(project_b(common.origin_world),nb,project_b))
        return (best[1],best[2]) if best else (None,None)
    finally:
        for mesh in meshes:bpy.data.meshes.remove(mesh)
