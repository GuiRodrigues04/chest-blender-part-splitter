"""Double-precision local surface checks for sub-micrometre imported facets.

BVH float queries can skip nearly collinear triangles even on identical input.
Unchanged faces are verified exactly; changed patches use scalar double math.
"""
import bmesh


def sub(a,b): return tuple(x-y for x,y in zip(a,b))
def dot(a,b): return sum(x*y for x,y in zip(a,b))
def cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])


def triangle_distance_squared(p, triangle):
    a,b,c=triangle
    def segment(x,y):
        edge=sub(y,x);length=dot(edge,edge)
        t=max(0.,min(1.,dot(sub(p,x),edge)/length)) if length else 0.
        residual=tuple(v-t*e for v,e in zip(sub(p,x),edge))
        return dot(residual,residual)
    normal=cross(sub(b,a),sub(c,a));length=dot(normal,normal)
    if length:
        height=dot(sub(p,a),normal)
        projected=tuple(x-height*n/length for x,n in zip(p,normal))
        if all(dot(cross(sub(y,x),sub(projected,x)),normal)>=0. for x,y in ((a,b),(b,c),(c,a))):
            return height*height/length
    return min(segment(a,b),segment(b,c),segment(c,a))


def surface_samples_within(before, after, tolerance):
    def signature(face):
        return face.material_index, tuple(sorted(tuple(v.co) for v in face.verts))
    def triangles(bm):
        copy=bm.copy()
        try:
            bmesh.ops.triangulate(copy,faces=copy.faces[:])
            return [(f.material_index,tuple(tuple(v.co) for v in f.verts)) for f in copy.faces]
        finally:copy.free()
    for source,target in ((before,after),(after,before)):
        exact={signature(f) for f in target.faces}
        changed=[f for f in source.faces if signature(f) not in exact]
        if not changed:continue
        target_triangles=triangles(target)
        # Triangulate a disposable patch only to obtain on-surface samples.
        patch=source.copy()
        try:
            unchanged=[f for f in patch.faces if signature(f) in exact]
            if unchanged:
                bmesh.ops.delete(patch,geom=unchanged,context='FACES_ONLY')
            changed_triangles=triangles(patch)
        finally:patch.free()
        by_material={}
        for mat,tri in target_triangles:
            bounds=tuple((min(p[i] for p in tri)-tolerance,
                          max(p[i] for p in tri)+tolerance) for i in range(3))
            by_material.setdefault(mat,[]).append((tri,bounds))
        limit=tolerance*tolerance
        for material,triangle in changed_triangles:
            samples=list(triangle)+[tuple(sum(p[i] for p in triangle)/3 for i in range(3))]
            candidates=by_material.get(material,[])
            for point in samples:
                if not any(all(lo<=point[i]<=hi for i,(lo,hi) in enumerate(bounds))
                           and triangle_distance_squared(point,tri)<=limit
                           for tri,bounds in candidates):
                    return False
    return True
