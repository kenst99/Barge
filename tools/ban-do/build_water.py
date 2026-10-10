# Dựng map-data.json (mạng đường thủy thật từ OpenStreetMap) cho bản đồ điều phối sà lan.
# Xem tools/ban-do/README.md. Chạy:
#   python3 -I tools/ban-do/build_water.py <thư mục chứa 2 file geojson HOT> index.html map-data.json
import json, math, sys, os, re, heapq, collections, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shapely.geometry import shape, Polygon, MultiPolygon, LineString
from shapely.geometry.polygon import orient
from skeleton import centerline

DATA, HTML, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
DEBUG = sys.argv[4] if len(sys.argv) > 4 else None
html = open(HTML, encoding='utf-8').read()
MAP = json.loads(re.search(r'^const MAP = (.*);\s*$', html, re.M).group(1))
B, LS, SC = MAP['bounds'], MAP['lonscale'], MAP['scale']
def xy(lon, lat): return ((lon - B['minlon']) * LS * SC, (B['maxlat'] - lat) * SC)
NFC = lambda s: unicodedata.normalize('NFC', s or '').strip()
def km(a, b):
    R = 6371.0; la1, lo1, la2, lo2 = map(math.radians, (a[1], a[0], b[1], b[0]))
    h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(h))

Q = 0.05                     # lượng tử tọa độ (đơn vị bản đồ ~ 25 m)
TOL_LINE = {0: 0.04, 1: 0.05, 2: 0.07}
TOL_AREA = {0: 0.045, 1: 0.07}

# ── mã hóa polyline (thuật toán Google trên số nguyên) ──
def enc_num(v):
    v = ~(v << 1) if v < 0 else (v << 1)
    s = ''
    while v >= 0x20:
        s += chr((0x20 | (v & 0x1f)) + 63); v >>= 5
    return s + chr(v + 63)
def encode(pts):
    out, px, py = [], 0, 0
    for x, y in pts:
        ix, iy = int(round(x / Q)), int(round(y / Q))
        if out and ix == px and iy == py: continue
        out.append(enc_num(ix - px) + enc_num(iy - py)); px, py = ix, iy
    return ''.join(out)
def rdp(pts, eps):
    if len(pts) < 3: return pts
    keep = [False]*len(pts); keep[0] = keep[-1] = True; st = [(0, len(pts)-1)]
    while st:
        a, b = st.pop(); (x1, y1), (x2, y2) = pts[a], pts[b]
        dx, dy = x2-x1, y2-y1; L = math.hypot(dx, dy)
        dmax, idx = 0, -1
        for i in range(a+1, b):
            x0, y0 = pts[i]
            d = abs(dy*x0 - dx*y0 + x2*y1 - y2*x1)/L if L else math.hypot(x0-x1, y0-y1)
            if d > dmax: dmax, idx = d, i
        if dmax > eps: keep[idx] = True; st += [(a, idx), (idx, b)]
    return [p for p, k in zip(pts, keep) if k]

# ═══ 1. đọc OSM ═══
BB = (B['minlon'], B['minlat'], B['maxlon'], B['maxlat'])
def _in_box(f):
    g = f.get('geometry')
    if not g: return False
    def walk(c):
        if isinstance(c[0], (int, float)): return BB[0] <= c[0] <= BB[2] and BB[1] <= c[1] <= BB[3]
        return any(walk(x) for x in c)
    return walk(g['coordinates'])
LINES = [f for f in json.load(open(os.path.join(DATA, 'hotosm_vnm_waterways_lines_geojson.geojson')))['features'] if _in_box(f)]
POLYS = [f for f in json.load(open(os.path.join(DATA, 'hotosm_vnm_waterways_polygons_geojson.geojson')))['features'] if _in_box(f)]
print('OSM trong khung bản đồ:', len(LINES), 'đường,', len(POLYS), 'mặt nước')
def geom_lines(f):
    g = f['geometry']
    if not g: return []
    return g['coordinates'] if g['type'] == 'MultiLineString' else [g['coordinates']]

MAJOR_RIVERS = {'Sông Tiền','Sông Hậu','Sông Cổ Chiên','Sông Hàm Luông','Sông Ba Lai','Sông Cửa Đại','Sông Cửa Tiểu','Sông Mỹ Tho',
  'Sông Vàm Cỏ','Sông Vàm Cỏ Đông','Sông Vàm Cỏ Tây','Sông Soài Rạp','Sông Nhà Bè','Sông Lòng Tàu','Sông Sài Gòn','Sông Đồng Nai',
  'Sông Thị Vải','Sông Cái Mép','Sông Dinh','Sông Vàm Nao','Sông Mang Thít','Sông Cái Lớn','Sông Cái Bé','Sông Gành Hào','Sông Cửa Lớn',
  'Sông Bảy Háp','Sông Ông Đốc','Sông Bé','Sông Giang Thành','Sông Đồng Tranh','Sông Cần Thơ','Sông La Ngà','Sông Dừa','Sông Long Hồ',
  'Sông Cần Giuộc','Sông Bảo Định','Sông Kiên','Sông Quản Lộ','Sông Bạc Liêu','Sông Ray','Sông Thị Tính','Sông Đồng Môn'}
MAJOR_CANALS = {'Kênh Chợ Gạo','Kênh Vĩnh Tế','Kênh Rạch Giá-Long Xuyên','Kênh Cái Sắn','Kênh Quản Lộ - Phụng Hiệp','Kênh Lấp Vò',
  'Kênh Thủ Thừa','Kênh Nước Mặn','Kênh Tẻ','Kênh Đôi','Kênh Tháp Mười','Kinh Cái Côn','Rạch Kỳ Hôn','Rạch Lá - Tắc Tây Đen','Rạch Ông Lớn',
  'Kênh Xáng Xà No','Kênh Xà No','Kinh Xáng'}
def base_name(n):  # "Sông Hậu / ទន្លេបាសាក់" -> phần tiếng Việt
    parts = [p.strip() for p in n.split('/')]
    for p in parts:
        if re.search(r'[A-Za-zÀ-ỹ]', p): return p
    return parts[0]

name_len = collections.Counter()
for f in LINES:
    p = f['properties']; w = p.get('waterway')
    if w not in ('river', 'canal') or not p.get('name'): continue
    n = base_name(NFC(p['name']))
    name_len[(w, n)] += sum(km(a, b) for l in geom_lines(f) for a, b in zip(l, l[1:]))

def line_class(w, n):
    """trả (lod, kiểu): lod 0 luôn hiện, 1 khi phóng vừa, 2 khi phóng lớn"""
    if w == 'river':
        if n in MAJOR_RIVERS or name_len[(w, n)] >= 45: return 0, 'r'
        return (1 if n else 2), 'r'
    if n in MAJOR_CANALS or (n and name_len[(w, n)] >= 30): return 0, 'c'
    return (1 if n else 2), 'c'

# ═══ 2. đồ thị đi tuyến ═══
FACT = {('r',0): 1.0, ('c',0): 1.05, ('r',1): 1.35, ('c',1): 1.6, ('r',2): 1.6, ('c',2): 1.9, 'tidal': 1.9, 'stream': 4.0, 'sea': 1.0, 'link': 1.5}
G = collections.defaultdict(dict)
def key(c): return (round(c[0], 7), round(c[1], 7))
def add_edge(u, v, name, kind, fac):
    if u == v: return
    d = km(u, v); w = d*fac
    if v not in G[u] or G[u][v][0] > w:
        G[u][v] = (w, d, name, kind); G[v][u] = (w, d, name, kind)
way_ends = []
for f in LINES:
    p = f['properties']; w = p.get('waterway')
    if w not in ('river', 'canal', 'tidal_channel', 'stream'): continue
    n = base_name(NFC(p.get('name')))
    if w in ('river', 'canal'): lod, t = line_class(w, n); fac = FACT[(t, lod)]
    else: fac = FACT['tidal' if w == 'tidal_channel' else 'stream']
    for l in geom_lines(f):
        ks = [key(c) for c in l]
        for a, b in zip(ks, ks[1:]): add_edge(a, b, n, w, fac)
        if len(ks) > 1: way_ends += [ks[0], ks[-1]]

# vá chỗ đứt: đầu mút (bậc 1) cách mạng khác < 120 m thì nối vào nút gần nhất
CELL = 0.002
grid = collections.defaultdict(list)
for u in G: grid[(int(u[0]/CELL), int(u[1]/CELL))].append(u)
def nearest(p, maxkm, pred=None, exclude=None):
    best, bd = None, maxkm
    r = int(maxkm/(CELL*111)) + 1; cx, cy = int(p[0]/CELL), int(p[1]/CELL)
    for i in range(cx-r, cx+r+1):
        for j in range(cy-r, cy+r+1):
            for q in grid.get((i, j), ()):
                if (exclude and q in exclude) or (pred and not pred(q)): continue
                d = km(p, q)
                if d < bd: best, bd = q, d
    return best, bd
links = 0
for e in set(way_ends):
    if len(G[e]) != 1: continue
    nb = set(G[e]) | {e}
    q, d = nearest(e, 0.12, exclude=nb)
    if q: add_edge(e, q, '', 'link', FACT['link']); links += 1
print('graph nodes', len(G), 'links added', links)

# đường tim Lòng Tàu dựng từ mặt nước OSM (OSM chưa có đường tim)
LT = centerline([shape(f['geometry']).buffer(0) for f in POLYS if NFC(f['properties'].get('name')) == 'Sông Lòng Tàu'],
                (106.76, 10.69), (106.975, 10.46))
lt = [key(c) for c in LT]
for a, b in zip(lt, lt[1:]): add_edge(a, b, 'Sông Lòng Tàu', 'river', 1.0)
for end in (lt[0], lt[-1]):
    q, d = nearest(end, 1.5, pred=lambda q: q not in lt)
    if q: add_edge(end, q, 'Sông Lòng Tàu', 'river', 1.0)
for u in lt: grid[(int(u[0]/CELL), int(u[1]/CELL))].append(u)
# các rạch/sông nhánh chạm bờ Lòng Tàu (OSM không nối vào đường tim) -> nối vào điểm gần nhất trên đường tim
ltl = LineString(LT); ltd = [key(ltl.interpolate(i*0.0008).coords[0]) for i in range(int(ltl.length/0.0008)+1)]
for a, b in zip(ltd, ltd[1:]): add_edge(a, b, 'Sông Lòng Tàu', 'river', 1.0)
for u in ltd: grid[(int(u[0]/CELL), int(u[1]/CELL))].append(u)
ltset = set(ltd) | set(lt); side = 0
for e in set(way_ends):
    if len(G[e]) != 1 or e in ltset: continue
    if ltl.distance(LineString([e, e]).centroid) > 0.008: continue
    q, d = nearest(e, 0.8, pred=lambda q: q in ltset)
    if q: add_edge(e, q, '', 'link', FACT['link']); side += 1
print('Lòng Tàu side links', side)
EXTRA_LINES = [('Sông Lòng Tàu', 'river', LT)]

# luồng biển (không có trong OSM): nối hai đầu vào nút sông gần nhất
# (tên, điểm, gợi ý tên sông ở đầu, ở cuối) – đầu mút được bắt vào nút sông OSM thật gần nhất
SEA = [
 ('Luồng vịnh Gành Rái', [(106.9238216,10.5309742),(106.955,10.498),(106.9907238,10.4501201),(107.025,10.425),(107.065,10.402),(107.095,10.405),(107.1180508,10.4137693)], 'Sông Đồng Tranh', 'Sông Dinh'),
 ('Luồng ven biển Soài Rạp – Vũng Tàu', [(106.800,10.388),(106.870,10.360),(106.950,10.345),(107.030,10.362),(107.065,10.402)], 'Sông Soài Rạp', ''),
 ('Luồng Rạch Giá – Phú Quốc', [(105.075,10.012),(105.030,10.020),(104.900,10.050),(104.700,10.085),(104.450,10.115),(104.220,10.140),(104.100,10.150),(104.041,10.154)], 'Kênh Rạch Giá-Long Xuyên|Sông Kiên', ''),
 ('Luồng ven biển Rạch Giá – Hà Tiên', [(105.075,10.012),(105.000,10.045),(104.900,10.060),(104.820,10.130),(104.750,10.170),(104.680,10.130),(104.620,10.115),(104.565,10.160),(104.545,10.250),(104.505,10.300),(104.470,10.355),(104.482,10.378)], 'Kênh Rạch Giá-Long Xuyên|Sông Kiên', 'Sông Giang Thành'),
 ('Luồng Hà Tiên – Phú Quốc', [(104.482,10.378),(104.440,10.350),(104.360,10.300),(104.230,10.250),(104.120,10.200),(104.060,10.165),(104.041,10.154)], 'Sông Giang Thành', ''),
]
WATERY = lambda q: any(G[q][v][3] in ('river','canal','tidal_channel') for v in G[q])
def snap_end(p, hint):
    hs = [NFC(h) for h in hint.split('|')] if hint else []
    if hs:
        q, d = nearest(p, 4.0, pred=lambda q: any(G[q][v][2] in hs for v in G[q]))
        if q: return q
    q, d = nearest(p, 0.05)
    if q: return q
    q, d = nearest(p, 3.0, pred=WATERY)
    return q or p
sea_out = []
for name, pts, h0, h1 in SEA:
    ks = [key(c) for c in pts]
    ks[0] = snap_end(ks[0], h0)
    if h1 or not any(k == ks[-1] for k in G): ks[-1] = snap_end(ks[-1], h1) if h1 else ks[-1]
    for a, b in zip(ks, ks[1:]): add_edge(a, b, name, 'sea', FACT['sea'])
    for u in ks: grid[(int(u[0]/CELL), int(u[1]/CELL))].append(u)
    sea_out.append({'name': name, 'line': encode([xy(*c) for c in ks])})

def snap(p, hint):
    hs = [NFC(h) for h in hint.split('|')] if hint else []
    if hs:
        q, d = nearest(p, 6.0, pred=lambda q: any(any(h == G[q][v][2] for h in hs) for v in G[q]))
        if q: return q
    q, d = nearest(p, 3.0)
    if not q: raise SystemExit('không bắt được điểm %s %s' % (p, hint))
    return q
def dijkstra(s, t):
    dist = {s: 0}; prev = {}; pq = [(0, s)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == t: break
        if d > dist[u]: continue
        for v, (w, _, _, _) in G[u].items():
            nd = d+w
            if nd < dist.get(v, 1e18): dist[v] = nd; prev[v] = u; heapq.heappush(pq, (nd, v))
    if t not in dist: raise SystemExit('không có đường %s -> %s' % (s, t))
    path = [t]
    while path[-1] != s: path.append(prev[path[-1]])
    return path[::-1]

N = {
 'VX': ((105.190,10.905),'Sông Tiền'), 'HONGNGU': ((105.330,10.795),'Sông Tiền'), 'MYTHO': ((106.380,10.345),'Sông Tiền|Sông Mỹ Tho'),
 'CHOGAO': ((106.455,10.362),'Kênh Chợ Gạo'), 'VAMCO': ((106.625,10.453),'Sông Vàm Cỏ'), 'SOAIRAP': ((106.738,10.585),'Sông Soài Rạp'),
 'SOAIMOUTH': ((106.800,10.388),'Sông Soài Rạp'), 'NHABE': ((106.757,10.692),'Sông Nhà Bè'), 'CATLAI': ((106.798,10.762),'Sông Đồng Nai'),
 'BIENHOA': ((106.810,10.945),'Sông Đồng Nai'), 'LONGTAU': ((106.80,10.655),'Sông Lòng Tàu'), 'GODAU': ((107.015,10.655),'Sông Thị Vải'),
 'PHUMY': ((107.005,10.595),'Sông Thị Vải'), 'VUNGTAU': ((107.1180508,10.4137693),'Sông Dinh'), 'GRBAY': ((106.9238216,10.5309742),'Sông Đồng Tranh'), 'BARIA': ((107.168,10.495),'Sông Dinh'),
 'TANAN': ((106.415,10.535),'Sông Vàm Cỏ Tây'), 'BENLUC': ((106.490,10.640),'Sông Vàm Cỏ Đông'), 'LAPORT': ((106.748,10.550),'Sông Soài Rạp'),
 'CANGIUOC': ((106.672,10.608),''), 'KENHTE': ((106.700,10.752),'Kênh Tẻ'),
 'SAIGON': ((106.722,10.757),'Sông Sài Gòn'), 'TDM': ((106.648,10.972),'Sông Sài Gòn'), 'VINHLONG': ((105.975,10.258),'Sông Cổ Chiên|Sông Tiền'),
 'TRAVINH': ((106.390,9.950),'Sông Cổ Chiên'), 'HAMLUONG': ((106.270,10.290),'Sông Hàm Luông'), 'BENTRE': ((106.338,10.228),'Sông Hàm Luông'),
 'CANTHO': ((105.790,10.040),'Sông Hậu'), 'TRAON': ((105.915,9.935),'Sông Hậu'), 'MANGTHIT': ((106.045,10.115),'Sông Mang Thít'),
 'VAMNAO': ((105.350,10.580),'Sông Vàm Nao'), 'LONGXUYEN': ((105.455,10.385),'Sông Hậu'), 'RGLX': ((105.250,10.200),'Kênh Rạch Giá-Long Xuyên'),
 'RACHGIA': ((105.075,10.012),'Kênh Rạch Giá-Long Xuyên|Sông Kiên'), 'HATIEN': ((104.482,10.378),'Sông Giang Thành'), 'BAIVONG': ((104.041,10.154),''),
 'CHAUDOC': ((105.130,10.710),'Sông Hậu'), 'VINHTE': ((104.850,10.520),'Kênh Vĩnh Tế'), 'KIENTUONG': ((105.925,10.775),'Sông Vàm Cỏ Tây'),
 'CAICON': ((105.850,9.880),'Kinh Cái Côn'), 'QLPH': ((105.600,9.560),'Kênh Quản Lộ - Phụng Hiệp'), 'CAMAU': ((105.150,9.180),'Sông Quản Lộ|Kênh Quản Lộ - Phụng Hiệp'),
 'SOCTRANG': ((105.980,9.603),''), 'HAUSOC': ((106.10,9.70),'Sông Hậu'),
}
LBL = {'VX':'Vĩnh Xương','BIENHOA':'Biên Hòa','CATLAI':'Nhơn Trạch – Phú Hữu','GODAU':'Gò Dầu – Long Thành','PHUMY':'Phú Mỹ – Cái Mép',
 'VUNGTAU':'Vũng Tàu (sông Dinh)','BARIA':'Bà Rịa','TANAN':'Tân An','BENLUC':'Bến Lức','LAPORT':'Cảng Long An','CANGIUOC':'Cần Giuộc',
 'SAIGON':'TP.HCM (Tân Thuận)','TDM':'Thủ Dầu Một','VINHLONG':'TP. Vĩnh Long','TRAVINH':'Trà Vinh','BENTRE':'Bến Tre','CANTHO':'Cần Thơ',
 'RACHGIA':'Rạch Giá','HATIEN':'Hà Tiên','BAIVONG':'Phú Quốc (Bãi Vòng)','CAMAU':'Cà Mau','MYTHO':'Mỹ Tho','SOCTRANG':'Sóc Trăng (cảng nhà)'}
SNAP = {k: snap(p, h) for k, (p, h) in N.items()}
VXH = ['VX','MYTHO','CHOGAO','VAMCO','SOAIRAP','NHABE']
GR = 'Qua vịnh Gành Rái – kiểm tra cấp sà lan trước khi chạy.'
ROUTES = [
 ('dn-bienhoa','Đồng Nai', VXH+['CATLAI','BIENHOA'], ''),
 ('dn-nhontrach','Đồng Nai', VXH+['CATLAI'], ''),
 ('dn-godau','Đồng Nai', VXH+['GODAU'], ''),
 ('vt-song-dinh','Vũng Tàu', VXH+['LONGTAU','GRBAY','VUNGTAU'], GR),
 ('vt-phumy','Vũng Tàu', VXH+['PHUMY'], ''),
 ('vt-baria','Vũng Tàu', VXH+['LONGTAU','GRBAY','VUNGTAU','BARIA'], GR),
 ('vt-venbien','Vũng Tàu', ['VX','MYTHO','CHOGAO','VAMCO','SOAIMOUTH','VUNGTAU'], 'Đi biển ven bờ từ cửa Soài Rạp – cần sà lan đăng kiểm VR-SB.'),
 ('vt-bienhoa','Vũng Tàu', ['BIENHOA','CATLAI','NHABE','LONGTAU','GRBAY','VUNGTAU'], GR),
 ('la-tanan','Long An', ['VX','MYTHO','CHOGAO','VAMCO','TANAN'], ''),
 ('la-benluc','Long An', ['VX','MYTHO','CHOGAO','VAMCO','BENLUC'], ''),
 ('la-port','Long An', ['VX','MYTHO','CHOGAO','VAMCO','LAPORT'], ''),
 ('la-cangiuoc','Long An', ['VX','MYTHO','CHOGAO','VAMCO','CANGIUOC'], ''),
 ('la-dtm','Long An', ['VX','HONGNGU','KIENTUONG','TANAN'], 'Tuyến kênh Đồng Tháp Mười – hợp sà lan tải nhỏ, mùa nước.'),
 ('vl-vinhlong','Vĩnh Long', ['VX','VINHLONG'], ''),
 ('vl-travinh','Vĩnh Long', ['VX','VINHLONG','TRAVINH'], ''),
 ('vl-bentre','Vĩnh Long', ['VX','HAMLUONG','BENTRE'], ''),
 ('vl-cantho','Vĩnh Long', ['CANTHO','TRAON','MANGTHIT','VINHLONG'], ''),
 ('st-vx','Sóc Trăng', ['VX','VAMNAO','CANTHO','HAUSOC','SOCTRANG'], ''),
 ('st-bienhoa','Sóc Trăng', ['BIENHOA','CATLAI','NHABE','SOAIRAP','VAMCO','CHOGAO','MYTHO','VINHLONG','MANGTHIT','TRAON','HAUSOC','SOCTRANG'], ''),
 ('st-vungtau','Sóc Trăng', ['VUNGTAU','GRBAY','LONGTAU','NHABE','SOAIRAP','VAMCO','CHOGAO','MYTHO','VINHLONG','MANGTHIT','TRAON','HAUSOC','SOCTRANG'], GR),
 ('st-vungtau-bien','Sóc Trăng', ['VUNGTAU','SOAIMOUTH','VAMCO','CHOGAO','MYTHO','VINHLONG','MANGTHIT','TRAON','HAUSOC','SOCTRANG'], 'Đi biển ven bờ Vũng Tàu – cửa Soài Rạp – cần sà lan đăng kiểm VR-SB.'),
 ('st-cantho','Sóc Trăng', ['CANTHO','HAUSOC','SOCTRANG'], ''),
 ('hcm-tanthuan','TP.HCM', ['VX','MYTHO','CHOGAO','VAMCO','CANGIUOC','KENHTE','SAIGON'], ''),
 ('hcm-tdm','TP.HCM', VXH+['SAIGON','TDM'], ''),
 ('hcm-cantho','TP.HCM', ['CANTHO','TRAON','MANGTHIT','VINHLONG','MYTHO','CHOGAO','VAMCO','CANGIUOC','KENHTE','SAIGON'], ''),
 ('mt-cantho','Miền Tây', ['VX','VAMNAO','CANTHO'], ''),
 ('mt-rachgia','Miền Tây', ['VX','VAMNAO','LONGXUYEN','RGLX','RACHGIA'], ''),
 ('mt-camau','Miền Tây', ['CANTHO','CAICON','QLPH','CAMAU'], ''),
 ('mt-hatien','Miền Tây', ['RACHGIA','HATIEN'], 'Đi biển ven bờ Hòn Đất – Kiên Lương – cần sà lan đăng kiểm VR-SB.'),
 ('pq-vx','Phú Quốc', ['VX','VAMNAO','LONGXUYEN','RGLX','RACHGIA','BAIVONG'], 'Đoạn Rạch Giá – Phú Quốc đi biển – cần sà lan đăng kiểm VR-SB.'),
 ('pq-vx-hatien','Phú Quốc', ['VX','VAMNAO','CHAUDOC','VINHTE','HATIEN','BAIVONG'], 'Kênh Vĩnh Tế hợp sà lan tải nhỏ; đoạn Hà Tiên – Phú Quốc đi biển (VR-SB).'),
 ('pq-rachgia','Phú Quốc', ['RACHGIA','BAIVONG'], 'Đi biển – cần sà lan đăng kiểm VR-SB.'),
 ('pq-hatien','Phú Quốc', ['HATIEN','BAIVONG'], 'Đi biển – cần sà lan đăng kiểm VR-SB.'),
]
routes_out, dbg = [], {'routes': []}
for rid, grp, via, note in ROUTES:
    seq = [SNAP[v] for v in via]
    path = [seq[0]]
    for s, t in zip(seq, seq[1:]): path += dijkstra(s, t)[1:]
    runs = []
    dist = 0; sea = False
    for u, v in zip(path, path[1:]):
        w, d, n, kind = G[u][v]; dist += d; sea |= kind == 'sea'
        if runs and runs[-1][0] == n: runs[-1][1] += d
        else: runs.append([n, d])
    names = []
    for n, d in runs:
        if not n or d < 1.5: continue
        if names and names[-1] == n: continue
        names.append(n)
    if len(names) > 9: names = [n for n, d in runs if n and d >= 6]; names = [n for i, n in enumerate(names) if i == 0 or names[i-1] != n]
    P = rdp([xy(*c) for c in path], 0.04)
    xs = [p[0] for p in P]; ys = [p[1] for p in P]
    routes_out.append({'id': rid, 'grp': grp, 'from': LBL[via[0]], 'to': LBL[via[-1]], 'via': ' → '.join(names), 'km': round(dist),
        'sea': sea, 'note': note, 'line': encode(P), 'box': [round(min(xs),1), round(min(ys),1), round(max(xs),1), round(max(ys),1)]})
    dbg['routes'].append({'id': rid, 'km': round(dist), 'via': ' → '.join(names), 'pts': [[c[1], c[0]] for c in path]})
    print('%-15s %4d km %s %s' % (rid, dist, 'BIỂN' if sea else '    ', ' → '.join(names)))

# ═══ 3. lớp hiển thị ═══
groups = collections.defaultdict(list)     # (lod, kiểu, tên) -> [chuỗi mã hóa]
npts = collections.Counter()
for f in LINES:
    p = f['properties']; w = p.get('waterway')
    if w not in ('river', 'canal', 'tidal_channel'): continue
    n = base_name(NFC(p.get('name')))
    lod, t = line_class('canal' if w == 'tidal_channel' else w, n)
    for l in geom_lines(f):
        P = rdp([xy(*c) for c in l], TOL_LINE[lod])
        if len(P) < 2: continue
        if len(P) == 2 and math.hypot(P[0][0]-P[1][0], P[0][1]-P[1][1]) < 0.15: continue
        groups[(lod, t, n)].append(encode(P)); npts[lod] += len(P)
for n, t, pts in EXTRA_LINES:
    P = rdp([xy(*c) for c in pts], TOL_LINE[0]); groups[(0, 'r', n)].append(encode(P)); npts[0] += len(P)
print('line points by lod', dict(npts))

WATER_OK = {'river','canal','oxbow','lagoon','lake','reservoir','riverbank','lock','moat',None}
areas = collections.defaultdict(list); apts = collections.Counter()
for f in POLYS:
    p = f['properties']
    if p.get('natural') == 'wetland' or p.get('water') not in WATER_OK: continue
    if p.get('waterway') in ('dam', 'weir', 'boatyard', 'dock'): continue
    if p.get('natural') != 'water' and p.get('waterway') not in ('riverbank', 'river', 'canal'): continue
    g = f['geometry']
    polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
    is_river = p.get('water') in ('river', 'canal', 'oxbow', 'riverbank') or p.get('waterway') in ('riverbank', 'river', 'canal')
    for poly in polys:
        rings = [[xy(*c) for c in r] for r in poly]
        try: sp = Polygon(rings[0], rings[1:]).buffer(0)
        except Exception: continue
        a_km2 = sp.area / (SC*SC) * 111 * 111 * math.cos(math.radians(10))
        if a_km2 < (0.05 if is_river else 0.6): continue
        lod = 0 if a_km2 >= 2.5 else 1
        sp = sp.simplify(TOL_AREA[lod], preserve_topology=True)
        if sp.is_empty: continue
        geoms = sp.geoms if sp.geom_type == 'MultiPolygon' else [sp]
        for gg in geoms:
            if gg.geom_type != 'Polygon' or gg.area < 0.03: continue
            gg = orient(gg, 1.0)   # vòng ngoài/vòng trong ngược chiều -> tô 'nonzero' đúng lỗ (cồn, cù lao)
            rs = [list(gg.exterior.coords)] + [list(r.coords) for r in gg.interiors if Polygon(r).area > 0.01]
            areas[lod].append([encode(r) for r in rs]); apts[lod] += sum(len(r) for r in rs)
print('area points by lod', dict(apts))

# nhãn tên sông lớn: giữa đoạn dài nhất, xoay theo hướng dòng
labels = []
by_name = collections.defaultdict(list)
for f in LINES:
    p = f['properties']; w = p.get('waterway')
    if w not in ('river', 'canal'): continue
    n = base_name(NFC(p.get('name')))
    if not n or line_class(w, n)[0] != 0: continue
    for l in geom_lines(f): by_name[n].append([xy(*c) for c in l])
by_name['Sông Lòng Tàu'].append([xy(*c) for c in LT])
TOP = {'Sông Tiền','Sông Hậu','Sông Sài Gòn','Sông Đồng Nai','Sông Vàm Cỏ','Sông Cổ Chiên','Sông Soài Rạp','Sông Hàm Luông','Sông Vàm Cỏ Đông','Sông Vàm Cỏ Tây','Sông Cái Lớn'}
for n, ls in by_name.items():
    l = max(ls, key=lambda q: sum(math.hypot(a[0]-b[0], a[1]-b[1]) for a, b in zip(q, q[1:])))
    seg = [math.hypot(a[0]-b[0], a[1]-b[1]) for a, b in zip(l, l[1:])]; L = sum(seg)
    if L < 6: continue
    half, acc, i = L/2, 0, 0
    while i < len(seg)-1 and acc+seg[i] < half: acc += seg[i]; i += 1
    t = (half-acc)/seg[i] if seg[i] else 0
    x = l[i][0] + (l[i+1][0]-l[i][0])*t; y = l[i][1] + (l[i+1][1]-l[i][1])*t
    j0, j1 = max(0, i-3), min(len(l)-1, i+4)
    ang = math.degrees(math.atan2(l[j1][1]-l[j0][1], l[j1][0]-l[j0][0]))
    if ang > 90: ang -= 180
    if ang < -90: ang += 180
    labels.append([n, round(x, 1), round(y, 1), round(ang), 0 if n in TOP else 1])

lines_out = [[lod, t, n, segs] for (lod, t, n), segs in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2]))]
out = {'v': 1, 'q': Q, 'src': 'OpenStreetMap (HOT export 06/05/2026)', 'areas': [areas[0], areas[1]],
       'lines': lines_out, 'sea': sea_out, 'labels': labels, 'routes': routes_out}
s = json.dumps(out, ensure_ascii=False, separators=(',', ':'))
open(OUT, 'w', encoding='utf-8').write(s)
print('OUT', OUT, len(s)//1024, 'KB; lines groups', len(lines_out), 'labels', len(labels))
if DEBUG: json.dump(dbg, open(DEBUG, 'w'), ensure_ascii=False)
