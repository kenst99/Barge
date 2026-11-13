# Dựng lớp chi tiết cho bản đồ (thư mục map-tiles/): app chỉ tải ô nào đang xem khi phóng lớn.
# Mỗi ô ~26 km: bờ sông thật + cồn (sai số ~6 m), sông/kênh nét mảnh, tên sông kênh, đường lớn, bến phà, tên địa danh.
# Nguồn: OpenStreetMap (bản xuất HOT + Overture Maps – cùng gốc OSM, giấy phép ODbL). Xem README.md. Chạy:
#   python3 -I tools/ban-do/build_tiles.py <thư mục geojson HOT> index.html map-data.json map-tiles \
#       --water=ov_water.parquet --seg=ov_seg.parquet --div=ov_div.parquet
import json, math, sys, os, re, collections, unicodedata, shutil
import pyarrow.parquet as pq, shapely
from shapely.geometry import box, LineString
from shapely.geometry.polygon import orient

DATA, HTML, BASE, OUT = sys.argv[1:5]
OPT = dict(a[2:].split('=', 1) for a in sys.argv[5:] if a.startswith('--') and '=' in a)
html = open(HTML, encoding='utf-8').read()
MAP = json.loads(re.search(r'^const MAP = (.*);\s*$', html, re.M).group(1))
B, LS, SC = MAP['bounds'], MAP['lonscale'], MAP['scale']
NFC = lambda s: unicodedata.normalize('NFC', s or '').strip()
def to_xy(g):                                   # kinh/vĩ độ -> đơn vị bản đồ (giống mpXY trong app)
    return shapely.transform(g, lambda a: (a - [B['minlon'], B['maxlat']]) * [LS*SC, -SC])
BOXLL = box(B['minlon'], B['minlat'], B['maxlon'], B['maxlat'])
KM_U = 111.32 / SC                              # km trên 1 đơn vị bản đồ
Q = 0.01                                        # lượng tử ~5 m
TOL = 6 / 1000 / KM_U                           # đơn giản hóa ~6 m
CELL = 50.0                                     # cạnh ô (đơn vị bản đồ) ~26 km
LAP = 0.08                                      # các ô chờm nhau ~40 m để không hở khe khi tô

def enc_num(v):
    v = ~(v << 1) if v < 0 else (v << 1)
    s = ''
    while v >= 0x20:
        s += chr((0x20 | (v & 0x1f)) + 63); v >>= 5
    return s + chr(v + 63)
def encode(pts, q=Q):
    out, px, py = [], 0, 0
    for x, y in pts:
        ix, iy = int(round(x / q)), int(round(y / q))
        if out and ix == px and iy == py: continue
        out.append(enc_num(ix - px) + enc_num(iy - py)); px, py = ix, iy
    return ''.join(out)

tiles = collections.defaultdict(lambda: {'a': [], 'l': collections.defaultdict(list), 'n': [], 'r': collections.defaultdict(list), 'p': []})
def cells(g):
    x0, y0, x1, y1 = g.bounds
    for cx in range(int(x0 // CELL), int(x1 // CELL) + 1):
        for cy in range(int(y0 // CELL), int(y1 // CELL) + 1):
            yield cx, cy, box(cx*CELL - LAP, cy*CELL - LAP, (cx+1)*CELL + LAP, (cy+1)*CELL + LAP)
def parts(g, kind):
    return [x for x in (g.geoms if hasattr(g, 'geoms') else [g]) if x.geom_type == kind and not x.is_empty]

# ═══ 1. mặt nước (Overture base/water) ═══
K2 = KM_U * KM_U
n_a = 0
for r in pq.read_table(OPT['water']).to_pylist():
    if r['subtype'] in ('pond', 'human_made', 'ocean', 'physical', 'spring') or r['class'] in ('basin', 'wastewater', 'swimming_pool', 'salt_pond', 'fishpond', 'moat'): continue
    g = shapely.from_wkb(r['geometry'])
    if g.geom_type not in ('Polygon', 'MultiPolygon'): continue
    if not g.is_valid: g = g.buffer(0)
    g = to_xy(g.intersection(BOXLL))
    if g.is_empty: continue
    is_river = r['subtype'] in ('river', 'canal', 'stream')
    if g.area * K2 < (0.002 if is_river else 0.15): continue
    g = g.simplify(TOL, preserve_topology=True)
    for cx, cy, bx in cells(g):
        for gg in parts(g.intersection(bx), 'Polygon'):
            if gg.area < 0.002: continue
            gg = orient(gg, 1.0)
            rs = [list(gg.exterior.coords)] + [list(h.coords) for h in gg.interiors if shapely.Polygon(h).area > 0.0008]
            tiles[cx, cy]['a'].append([encode(x) for x in rs]); n_a += sum(len(x) for x in rs)
print('mặt nước: điểm', n_a)

# ═══ 2. sông, kênh dạng nét + tên (HOT lines; phân hạng lấy theo map-data.json để cùng kiểu vẽ) ═══
base = json.load(open(BASE, encoding='utf-8'))
cls_of = {(t, n): lod for lod, t, n, _ in base['lines']}
def base_name(n):
    ps = [p.strip() for p in n.split('/')]
    for p in ps:
        if re.search(r'[A-Za-zÀ-ỹ]', p): return p
    return ps[0]
best = {}                                        # (ô, tên) -> (độ dài, x, y, góc)
n_l = 0
for f in json.load(open(os.path.join(DATA, 'hotosm_vnm_waterways_lines_geojson.geojson')))['features']:
    p = f['properties']; w = p.get('waterway'); gj = f.get('geometry')
    if w not in ('river', 'canal', 'tidal_channel') or not gj: continue
    g = shapely.geometry.shape(gj)
    if not g.intersects(BOXLL): continue
    n = base_name(NFC(p.get('name'))); t = 'r' if w == 'river' else 'c'
    lod = cls_of.get((t, n), 2)
    g = to_xy(g.intersection(BOXLL)).simplify(TOL)
    for cx, cy, bx in cells(g):
        for ln in parts(g.intersection(bx), 'LineString'):
            if ln.length < 0.03: continue
            tiles[cx, cy]['l'][f'{t} l{lod}'].append(encode(ln.coords)); n_l += len(ln.coords)
            if n and ln.length >= 2.5 and ln.length > best.get((cx, cy, n), (0,))[0]:
                m = ln.interpolate(0.5, normalized=True); a = ln.interpolate(0.42, normalized=True); b = ln.interpolate(0.58, normalized=True)
                ang = math.degrees(math.atan2(b.y - a.y, b.x - a.x))
                if ang > 90: ang -= 180
                if ang < -90: ang += 180
                best[cx, cy, n] = (ln.length, round(m.x, 2), round(m.y, 2), round(ang), lod)
for (cx, cy, n), (L, x, y, a, lod) in best.items():
    if cx*CELL <= x < (cx+1)*CELL and cy*CELL <= y < (cy+1)*CELL: tiles[cx, cy]['n'].append([n, x, y, a, lod, round(L, 1)])
for t in tiles.values():                          # mỗi ô giữ tối đa 16 tên: sông lớn trước, rồi theo độ dài
    t['n'] = [x[:4] for x in sorted(t['n'], key=lambda x: (x[4], -x[5]))[:16]]
print('nét sông kênh: điểm', n_l, 'tên', sum(len(t['n']) for t in tiles.values()))

# ═══ 3. đường bộ lớn + tuyến phà (Overture transportation/segment) ═══
RC = {'motorway': 'h', 'trunk': 'h', 'primary': 'p', 'secondary': 's', 'tertiary': 's'}
roads_base = collections.defaultdict(list); n_r = 0
if OPT.get('seg'):
    tb = pq.read_table(OPT['seg'], columns=['geometry', 'subtype', 'class']).to_pylist()
    for r in tb:
        k = 'f' if r['subtype'] == 'water' else RC.get(r['class']) if r['subtype'] == 'road' else None
        if not k: continue
        g = shapely.from_wkb(r['geometry'])
        if g.geom_type != 'LineString' or not g.intersects(BOXLL): continue
        g = to_xy(g.intersection(BOXLL))
        if g.is_empty: continue
        if k in ('h', 'p'): roads_base[k].extend(parts(g, 'LineString'))
        g = g.simplify(TOL)
        for cx, cy, bx in cells(g):
            for ln in parts(g.intersection(bx), 'LineString'):
                if ln.length < 0.03: continue
                tiles[cx, cy]['r'][k].append(encode(ln.coords)); n_r += len(ln.coords)
    print('đường bộ: điểm', n_r)

# ═══ 4. tên địa danh (Overture divisions) ═══
RANK = {'city': 0, 'town': 1, 'village': 2, None: 2, 'hamlet': 3}
places_base = []; seen = collections.defaultdict(list)
CITY = {NFC(c['name']) for c in MAP['cities']}      # đã có sẵn nhãn trong app
if OPT.get('div'):
    rows = []
    for r in pq.read_table(OPT['div']).to_pylist():
        if r['subtype'] != 'locality' or r['country'] not in ('VN', 'KH'): continue
        nm = NFC((r['names'] or {}).get('primary'))
        g = shapely.from_wkb(r['geometry'])
        if not nm or g.geom_type != 'Point' or not BOXLL.contains(g): continue
        nm = re.sub(r'^(Xã|Phường|Thị trấn|Thành phố|Thị xã|Huyện|Quận) ', '', nm)
        if nm in CITY: continue
        pt = to_xy(g); rows.append((RANK.get(r['class'], 2), nm, pt.x, pt.y))
    for rk, nm, x, y in sorted(rows):               # trùng tên trong ~10 km (đơn vị cũ/mới sau sáp nhập): giữ nhãn hạng cao nhất
        if any(math.hypot(x - a, y - b) < 20 for a, b in seen[nm]): continue
        seen[nm].append((x, y))
        tiles[int(x // CELL), int(y // CELL)]['p'].append([nm, round(x, 2), round(y, 2), rk])
        if rk <= 1: places_base.append([nm, round(x, 1), round(y, 1), rk])
    for t in tiles.values(): t['p'] = sorted(t['p'], key=lambda x: x[3])[:40]
    print('địa danh:', sum(len(t['p']) for t in tiles.values()), '· thị trấn/thành phố', len(places_base))

# ═══ 5. ghi file ═══
if os.path.isdir(OUT): shutil.rmtree(OUT)
os.makedirs(OUT)
keys, total = [], 0
for (cx, cy), t in sorted(tiles.items()):
    o = {'a': t['a'], 'l': [[k, v] for k, v in sorted(t['l'].items())], 'n': t['n'], 'r': [[k, v] for k, v in sorted(t['r'].items())], 'p': t['p']}
    if not (o['a'] or o['l'] or o['r'] or o['p']): continue
    s = json.dumps(o, ensure_ascii=False, separators=(',', ':'))
    open(os.path.join(OUT, f'{cx}_{cy}.json'), 'w', encoding='utf-8').write(s)
    keys.append(f'{cx}_{cy}'); total += len(s.encode())
# lớp nền cho mức phóng vừa: đường cao tốc / quốc lộ / tỉnh lộ chính (gộp đoạn, đơn giản hóa ~30 m)
from shapely.ops import linemerge
QB = 0.05; rb = []
for k in ('h', 'p'):
    m = linemerge(roads_base[k]) if roads_base[k] else LineString()
    segs = [encode(ln.simplify(0.06).coords, QB) for ln in parts(m, 'LineString') if ln.length >= 0.6]
    rb.append([k, segs])
idx = {'v': 1, 'q': Q, 'cell': CELL, 'tiles': keys, 'qb': QB, 'roads': rb, 'places': places_base,
       'src': 'OpenStreetMap (HOT export, Overture Maps)'}
s = json.dumps(idx, ensure_ascii=False, separators=(',', ':'))
open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8').write(s)
sizes = sorted(os.path.getsize(os.path.join(OUT, k + '.json')) for k in keys)
print(f'OUT {OUT}: {len(keys)} ô, tổng {total//1024} KB, ô lớn nhất {sizes[-1]//1024} KB, trung vị {sizes[len(sizes)//2]//1024} KB; index.json {len(s)//1024} KB')
