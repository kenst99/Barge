# Đường tim (trục giữa) của một mặt nước sông: Voronoi trên biên đã làm dày -> đồ thị -> đường ngắn nhất giữa 2 đầu
import json, math, heapq, collections
from shapely.geometry import shape, Point, LineString
from shapely.ops import unary_union
from scipy.spatial import Voronoi
def centerline(polys, start, end, step=0.0008):
    poly = unary_union(polys)
    if poly.geom_type == 'MultiPolygon':
        poly = max(poly.geoms, key=lambda g: g.area)
    pts = []
    for ring in [poly.exterior] + list(poly.interiors):
        L = ring.length; n = max(8, int(L/step))
        pts += [ring.interpolate(i*L/n).coords[0] for i in range(n)]
    vor = Voronoi(pts)
    inside = [poly.contains(Point(v)) for v in vor.vertices]
    G = collections.defaultdict(dict)
    for a, b in vor.ridge_vertices:
        if a < 0 or b < 0 or not inside[a] or not inside[b]: continue
        pa, pb = vor.vertices[a], vor.vertices[b]
        d = math.hypot(pa[0]-pb[0], pa[1]-pb[1])
        # ưu tiên đi giữa dòng: phạt cạnh gần bờ
        clear = poly.exterior.distance(Point((pa[0]+pb[0])/2, (pa[1]+pb[1])/2)) + 1e-6
        w = d / clear
        G[a][b] = w; G[b][a] = w
    nodes = list(G)
    near = lambda p: min(nodes, key=lambda i: (vor.vertices[i][0]-p[0])**2 + (vor.vertices[i][1]-p[1])**2)
    s, t = near(start), near(end)
    dist = {s: 0}; prev = {}; pq = [(0, s)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == t: break
        if d > dist[u]: continue
        for v, w in G[u].items():
            if d+w < dist.get(v, 1e18): dist[v] = d+w; prev[v] = u; heapq.heappush(pq, (d+w, v))
    path = [t]
    while path[-1] != s: path.append(prev[path[-1]])
    line = LineString([tuple(vor.vertices[i]) for i in path[::-1]]).simplify(0.0003)
    return [list(c) for c in line.coords]
if __name__ == '__main__':
    import sys
    P = json.load(open(sys.argv[1]))
    name = sys.argv[2]; start = tuple(map(float, sys.argv[3].split(','))); end = tuple(map(float, sys.argv[4].split(',')))
    polys = [shape(f['geometry']).buffer(0) for f in P['features'] if (f['properties'].get('name') or '') == name]
    print(len(polys), 'polygons', [round(p.area*111*111, 2) for p in polys])
    cl = centerline(polys, start, end)
    print(len(cl), 'pts', cl[0], cl[-1])
    json.dump(cl, open(sys.argv[5], 'w'))
