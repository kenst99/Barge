# Tải đối tượng Overture Maps trong khung bản đồ bằng cách đọc từng phần (HTTP range), chỉ lấy nhóm dòng chạm khung.
# Chạy: python3 tools/ban-do/tai_overture.py release/<bản>/ <theme> <type> <file .parquet ra> <cột,cột,...>
import sys, re, json, pickle, requests, fsspec, pyarrow.parquet as pq, pyarrow as pa, pyarrow.compute as pc
REL, THEME, TYPE, OUT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
COLS = sys.argv[5].split(',')
X0, Y0, X1, Y1 = 102.8, 8.3, 107.7, 12.4
base = 'https://overturemaps-us-west-2.s3.amazonaws.com/'
x = requests.get(base, params={'list-type': 2, 'prefix': f'{REL}theme={THEME}/type={TYPE}/'}, timeout=60).text
keys = re.findall(r'<Key>([^<]*\.parquet)</Key>', x)
fs = fsspec.filesystem('https', block_size=4*1024*1024)
tabs = []; n = 0
for k in keys:
    f = fs.open(base + k, cache_type='readahead')
    pf = pq.ParquetFile(f)
    md = pf.metadata; sch = pf.schema_arrow
    names = [md.schema.column(i).path for i in range(md.num_columns)]
    ix = {p: i for i, p in enumerate(names)}
    rgs = []
    for r in range(md.num_row_groups):
        rg = md.row_group(r)
        try:
            s = {p: rg.column(ix['bbox.' + p]).statistics for p in ('xmin', 'xmax', 'ymin', 'ymax')}
            if s['xmin'].min > X1 or s['xmax'].max < X0 or s['ymin'].min > Y1 or s['ymax'].max < Y0: continue
        except Exception: pass
        rgs.append(r)
    print(k.split('/')[-1][:10], 'row groups', md.num_row_groups, '->', len(rgs), flush=True)
    for r in rgs:
        t = pf.read_row_group(r, columns=COLS + ['bbox'])
        b = t['bbox'].combine_chunks()
        m = pc.and_(pc.and_(pc.less_equal(b.field('xmin'), X1), pc.greater_equal(b.field('xmax'), X0)),
                    pc.and_(pc.less_equal(b.field('ymin'), Y1), pc.greater_equal(b.field('ymax'), Y0)))
        t = t.filter(m)
        if t.num_rows: tabs.append(t.drop(['bbox'])); n += t.num_rows
    f.close()
print('rows', n)
pq.write_table(pa.concat_tables(tabs), OUT)
