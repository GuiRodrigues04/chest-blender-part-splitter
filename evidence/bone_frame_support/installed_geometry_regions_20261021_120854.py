"""Closed planar-support region cuts with one outer contour and interior holes."""
import math
import bpy
import bmesh
from mathutils import Vector
from mathutils.geometry import tessellate_polygon, intersect_line_line_2d
from .geometry_contract import boundary_normal, build_cut_interface, SplitResult
from .diagnostic import validate_bmesh_mesh_geometry, sanitize_mesh_micro_degeneracies


def area(poly):
    return .5 * math.fsum(a.x*b.y-b.x*a.y for a,b in zip(poly,poly[1:]+poly[:1]))


def validate_rings(rings):
    from .geometry_connectors import point_in_polygon_2d
    rings = sorted(rings, key=lambda p: -abs(area(p)))
    if not rings or any(len(p)<3 or abs(area(p))<1e-12 for p in rings):
        raise ValueError('Contorno de região degenerado.')
    segments=[(k,i,a,b) for k,p in enumerate(rings) for i,(a,b) in enumerate(zip(p,p[1:]+p[:1]))]
    for i,(k,e,a,b) in enumerate(segments):
        for l,f,c,d in segments[i+1:]:
            if k==l and (e==f or (e-f)%len(rings[k]) in (1,len(rings[k])-1)):
                continue
            if intersect_line_line_2d(a,b,c,d) is not None:
                raise ValueError('Os contornos se cruzam ou a folga colapsa a moldura.')
    for i,p in enumerate(rings[1:],1):
        if not point_in_polygon_2d(p[0].x,p[0].y,rings[0]):
            raise ValueError('A seleção possui regiões externas desconectadas.')
        for q in rings[1:i]:
            if point_in_polygon_2d(p[0].x,p[0].y,q) or point_in_polygon_2d(q[0].x,q[0].y,p):
                raise ValueError('Aberturas aninhadas não pertencem a uma única região selecionada.')
    return rings


def region_support(obj, face_indices, unit_scale, _source_bm=None):
    from .geometry_material import _order_boundary_loops, _get_orthonormal_basis
    bm=_source_bm.copy() if _source_bm is not None else bmesh.new()
    try:
        if _source_bm is None:bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world);bm.normal_update()
        if obj.matrix_world.determinant()<0:
            bmesh.ops.reverse_faces(bm,faces=bm.faces[:]);bm.normal_update()
        if any(not e.is_manifold for e in bm.edges):
            raise ValueError('A malha está aberta ou possui vértices separados; use Reparar Malha antes de extrair a moldura.')
        bm.faces.ensure_lookup_table();bm.faces.index_update();bm.verts.index_update()
        region={bm.faces[i] for i in face_indices}
        edges=[e for e in bm.edges if sum(f in region for f in e.link_faces)==1]
        loops=_order_boundary_loops(edges)
        if not loops or len(loops)<2:
            raise ValueError('A região precisa de um contorno externo e de abertura interna.')
        coords=[[v.co.copy() for v in loop] for loop in loops]
        # Largest Newell area, independent of the order returned by BMesh.
        def magnitude(poly):
            c=poly[0]
            return sum(((a-c).cross(b-c) for a,b in zip(poly,poly[1:]+poly[:1])),Vector()).length
        outer=max(coords,key=magnitude)
        normal=boundary_normal(outer)
        avg=sum((f.normal*f.calc_area() for f in region),Vector())
        if normal.dot(avg)<0:normal=-normal
        if normal.length<.9:raise ValueError('Não foi possível determinar o plano da moldura.')
        origin=sum(outer,Vector())/len(outer)
        # A frame can meet a recessed centre at a different height from its
        # outer edge. Parallel rings still define a unique extraction axis;
        # use the innermost support, retaining the complete selected relief.
        deviation=max(max(abs((p-poly[0]).dot(normal)) for p in poly) for poly in coords)*unit_scale
        if deviation>.25:
            raise ValueError('A moldura precisa de apoio planar (desvio superior a 0,25 mm).')
        origin+=normal*min((p-origin).dot(normal) for poly in coords for p in poly)
        u,v=_get_orthonormal_basis(normal)
        # The exposed cap can overhang the support edge slightly (a bevel or
        # recessed inner wall). Its footprint must also be extracted, otherwise
        # tiny strips of the selected colour remain on the receiver.
        front={f for f in region if f.normal.dot(normal)>.99}
        if front:
            forward=max(f.calc_center_median().dot(normal) for f in front)
            front={f for f in front if abs(f.calc_center_median().dot(normal)-forward)*unit_scale<=.001}
            front_loops=_order_boundary_loops([e for e in bm.edges if sum(f in front for f in e.link_faces)==1])
            if front_loops and len(front_loops)>1:
                coords=[[v.co.copy() for v in lp] for lp in front_loops]
        rings=validate_rings([[Vector(((p-origin).dot(u)*unit_scale,(p-origin).dot(v)*unit_scale)) for p in poly] for poly in coords])
        from .geometry_connectors import point_in_polygon_2d
        def near_edge(point,poly):
            for a,b in zip(poly,poly[1:]+poly[:1]):
                edge=b-a
                t=max(0.,min(1.,(point-a).dot(edge)/max(edge.length_squared,1e-24)))
                if (point-a-edge*t).length<=.0001:return True
            return False
        for vertex in {v for f in region for v in f.verts}:
            delta=vertex.co-origin;p=Vector((delta.dot(u)*unit_scale,delta.dot(v)*unit_scale))
            if (not point_in_polygon_2d(p.x,p.y,rings[0]) and not near_edge(p,rings[0])) or any(
                    point_in_polygon_2d(p.x,p.y,hole) and not near_edge(p,hole) for hole in rings[1:]):
                raise ValueError('A região atravessa o plano de apoio; use uma região superficial com projeção desimpedida.')
        boundary_world=[[origin+(p.x*u+p.y*v)/unit_scale for p in poly] for poly in rings]
        heights=[(vertex.co-origin).dot(normal)*unit_scale for face in region for vertex in face.verts]
        if min(heights)<-.01:
            raise ValueError('A região atravessa o plano de apoio; use uma região superficial com projeção desimpedida.')
        outside=[f.material_index for e in edges for f in e.link_faces if f not in region]
        return dict(origin=origin,normal=normal,u=u,v=v,rings=rings,loops=boundary_world,
                    height=max(heights),body_material=max(sorted(set(outside)),key=outside.count) if outside else 0,
                    region_faces=sorted(face_indices),deviation=deviation)
    finally:bm.free()


def ring_prism(support, bottom_mm, top_mm, offset_mm, unit_scale, name):
    from .geometry_material import offset_polygon_2d
    rings=[]
    for i,poly in enumerate(support['rings']):
        shifted,ok=offset_polygon_2d(poly,offset_mm if i==0 else -offset_mm)
        if not ok:raise ValueError('A folga colapsa um contorno da moldura.')
        rings.append(shifted)
    original_outer=rings[0]
    rings=validate_rings(rings)
    if rings[0] is not original_outer:
        raise ValueError('A folga colapsa a largura da moldura.')
    # Keep outer CCW and holes CW, in physical millimetres for tessellation.
    rings=[poly if (area(poly)>0)==(i==0) else list(reversed(poly)) for i,poly in enumerate(rings)]
    polygons=[[Vector((p.x,p.y,0)) for p in poly] for poly in rings]
    triangles=tessellate_polygon(polygons)
    flat=[p for poly in rings for p in poly]
    expected=abs(area(rings[0]))-sum(abs(area(p)) for p in rings[1:])
    measured=sum(abs(area([flat[i] for i in t])) for t in triangles)
    if expected<=1e-8 or abs(measured-expected)>max(1e-5,expected*1e-5):
        raise ValueError('Não foi possível triangular a moldura preservando suas aberturas.')
    o,n,u,v=(support[k] for k in ('origin','normal','u','v'))
    def world(p,height):return o+(u*p.x+v*p.y+n*height)/unit_scale
    vertices=[world(p,height) for height in (-bottom_mm,top_mm) for p in flat]
    count=len(flat)
    faces=[tuple(reversed(t)) for t in triangles]+[tuple(i+count for i in t) for t in triangles]
    first=0
    for poly in rings:
        for i in range(len(poly)):
            a=first+i;b=first+(i+1)%len(poly)
            faces.append((a,b,b+count,a+count))
        first+=len(poly)
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    obj=bpy.data.objects.new(name,mesh);bpy.context.scene.collection.objects.link(obj)
    cap_triangles=[tuple(world(flat[i],-bottom_mm) for i in t) for t in triangles]
    boundaries=[[world(p,-bottom_mm) for p in poly] for poly in rings]
    return obj,cap_triangles,boundaries


def _slice_surface_region(obj, face_indices, depth_mm, scene, mode='EXTRUDE',
                         clearance_mm=0., apply_to='PART', bottom_mm=None,
                         material_index=0, interface_mat_mode='SOURCE', source_mode='MATERIAL',through_cut=False,_solver='EXACT'):
    from .geometry_loop import LoopSliceResult
    from .geometry_clearance import triangulated_source_mesh, weld_boolean_roundoff
    from .geometry_material import _check_wall_thickness
    scale=scene.unit_settings.scale_length*1000
    if scene!=bpy.context.scene:
        raise ValueError('Ative a cena do modelo antes de extrair a moldura.')
    source=bmesh.new()
    try:
        source.from_mesh(obj.data);source.transform(obj.matrix_world)
        if obj.matrix_world.determinant()<0:bmesh.ops.reverse_faces(source,faces=source.faces[:])
        source_check=validate_bmesh_mesh_geometry(source,scale)
        if not source_check['is_valid'] or not source_check['is_manifold']:
            raise ValueError('A malha original precisa estar fechada e sem faces degeneradas para extrair a moldura.')
        source_volume=abs(source_check['volume_mm3'])
    finally:source.free()
    support=region_support(obj,face_indices,scale)
    depth=0. if mode=='BASE' else depth_mm
    if mode=='BASE' and support['height']<=.001:
        raise ValueError('A moldura é plana: escolha Profundidade para criar uma peça sólida.')
    bottom=clearance_mm if bottom_mm is None else max(0.,bottom_mm)
    available=depth+support['height']
    if bottom>=available-.001 or clearance_mm<0:
        raise ValueError('A folga de fundo excede a espessura disponível na moldura.')
    # Check wall thickness inside the annulus, never in its empty centre.
    temps=[];results=[];contacts=[]
    try:
        nominal,triangles,boundaries=ring_prism(support,depth,support['height']+1.,0.,scale,'_frame_nominal')
        temps.append(nominal)
        if not through_cut and depth>0:
            samples=[sum(t,Vector())/3+support['normal']*(depth/scale) for t in triangles]
            extra=bottom*(1. if apply_to=='CAVITY' else .5 if apply_to=='BOTH' else 0.)
            _check_wall_thickness(obj,samples[::max(1,len(samples)//64)],-support['normal'],depth+extra,scale,region_face_indices=face_indices)
        for side in ('A','B'):
            fraction=(1. if apply_to==('PART' if side=='A' else 'CAVITY') else .5 if apply_to=='BOTH' else 0.)
            sign=1 if side=='A' else -1
            # Coincident imported sidewalls may differ by a few float ULPs.
            # A physical 0.00002 mm outward guard on a relief receiver removes
            # zero-thickness coloured films. Keep A exact: expanding it would
            # add tiny fragments of the neighbouring body at a zero-gap seam.
            guard=.00002 if side=='B' and support['height']>.001 else 0.
            prism,_,actual_loops=ring_prism(support,depth-sign*fraction*bottom,support['height']+1.,sign*fraction*clearance_mm-guard,scale,'_frame_'+side)
            temps.append(prism)
            for mat in obj.data.materials:prism.data.materials.append(mat)
            interface_material=material_index if side=='A' and interface_mat_mode=='EXTRACTED' else support['body_material']
            for face in prism.data.polygons:face.material_index=interface_material
            candidate=obj.copy();candidate.data=triangulated_source_mesh(obj.data)
            candidate.hide_viewport=False;scene.collection.objects.link(candidate);temps.append(candidate)
            modifier=candidate.modifiers.new('FrameCut','BOOLEAN');modifier.solver=_solver
            modifier.operation='INTERSECT' if side=='A' else 'DIFFERENCE';modifier.object=prism
            bpy.context.view_layer.update();evaluated=candidate.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh=evaluated.to_mesh()
            try:
                bm=bmesh.new();bm.from_mesh(mesh);bm.transform(obj.matrix_world);bm.normal_update()
                if obj.matrix_world.determinant()<0:
                    bmesh.ops.reverse_faces(bm,faces=bm.faces[:]);bm.normal_update()
                results.append(bm)
            finally:evaluated.to_mesh_clear()
            weld_boolean_roundoff(bm,scale);sanitize_mesh_micro_degeneracies(bm,scale)
            check=validate_bmesh_mesh_geometry(bm,scale)
            if not check['is_valid'] or not check['is_manifold'] or check['volume_mm3']<=1e-4:
                raise RegionBooleanError('O corte da moldura não produziu dois sólidos válidos; ajuste profundidade ou folga.')
            from .geometry_connectors import point_in_polygon_2d
            from .geometry_clearance import final_contact_patch
            layer=bm.faces.layers.int.get('splitter_contact_surface') or bm.faces.layers.int.new('splitter_contact_surface')
            direction=-support['normal'] if side=='A' else support['normal']
            anchor=actual_loops[0][0]
            def uv(point):
                rel=point-support['origin']
                return (rel.dot(support['u'])*scale,rel.dot(support['v'])*scale)
            polygons=[[uv(p) for p in loop] for loop in actual_loops]
            for face in bm.faces:
                point=uv(face.calc_center_median())
                in_domain=point_in_polygon_2d(*point,polygons[0]) and not any(point_in_polygon_2d(*point,p) for p in polygons[1:])
                face[layer]=int(in_domain and face.normal.dot(direction)>.99 and
                                all(abs((v.co-anchor).dot(direction))*scale<=.001 for v in face.verts))
                if face[layer]:face.material_index=interface_material
            contacts.append(final_contact_patch(bm,direction,scale))
        from .geometry_plane import evaluate_bmesh_metrics
        metrics=[evaluate_bmesh_metrics(bm,scale) for bm in results]
        total=sum(abs(bm.calc_volume(signed=True))*scale**3 for bm in results)
        tolerance=max(.05,source_volume*1e-6)
        if total>source_volume+tolerance or (max(clearance_mm,bottom)==0 and abs(total-source_volume)>tolerance):
            raise RegionBooleanError('A extração da moldura não conservou o volume esperado; a fonte foi preservada.')
        interface=build_cut_interface(support['origin']-support['normal']*(depth/scale),-support['normal'],
                                      boundaries[0],triangles,scale,source_mode,boundary_loops_world=boundaries)
        interface.clearance_applied=clearance_mm>0 or bottom>0
        interface.final_contact_a,interface.final_contact_b=contacts
        if through_cut and not all(contacts):
            interface.outer_contours_uv=[];interface.hole_contours_uv=[];interface.interface_triangles_world=[]
        result=LoopSliceResult(results[0],results[1],SplitResult(metrics[0],metrics[1],interface))
        results=[]
        return result
    finally:
        for bm in results:bm.free()
        for temp in reversed(temps):
            mesh=temp.data;bpy.data.objects.remove(temp,do_unlink=True)
            if mesh.users==0:bpy.data.meshes.remove(mesh)


class RegionBooleanError(ValueError):
    pass


def slice_surface_region(*args, **kwargs):
    try:
        return _slice_surface_region(*args, **kwargs)
    except RegionBooleanError:
        solvers=bpy.types.BooleanModifier.bl_rna.properties['solver'].enum_items
        if 'MANIFOLD' not in {item.identifier for item in solvers}:
            raise
        return _slice_surface_region(*args, **kwargs, _solver='MANIFOLD')
