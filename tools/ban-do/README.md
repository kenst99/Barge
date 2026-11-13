# Dữ liệu bản đồ đường thủy (`map-data.json`)

Bản đồ điều phối dùng dữ liệu sông, kênh **thật** từ OpenStreetMap (bản xuất của HOT, giấy phép ODbL –
trong app có ghi nguồn "© OpenStreetMap"). File `map-data.json` ở thư mục gốc được dựng sẵn bằng script này:

- mặt nước sông lớn, hồ (bề rộng thật), sông/kênh chia 3 mức chi tiết theo độ phóng,
- nhãn tên sông, luồng biển (Gành Rái, ven biển, ra Phú Quốc – OSM không có, vẽ thêm),
- đất Campuchia/Thái Lan và đường biên giới (Natural Earth), tên cửa sông, Biển Đông, Vịnh Thái Lan,
- mạng tuyến gộp (vẽ nét đứt) và điểm đầu/cuối tuyến,
- 43 tuyến vận chuyển tính đường ngắn nhất trên mạng sông OSM (ưu tiên sông lớn, kênh chính), gồm các tuyến theo nhật ký chở hàng và Sóc Trăng → Trà Nóc / cảng Hoàng Diệu / Cái Cui (Cần Thơ),
- `route-graph.json`: mạng sông rút gọn (~13 nghìn nút) để app tự tìm đường giữa hai điểm bất kỳ, có tuyến thay thế. App chỉ tải file này khi bấm tìm đường.

## Cập nhật khi OSM có dữ liệu mới

```bash
pip install shapely scipy
mkdir -p /tmp/osm && cd /tmp/osm
B=https://s3.dualstack.us-east-1.amazonaws.com/production-raw-data-api/ISO3/VNM/waterways
curl -O $B/lines/hotosm_vnm_waterways_lines_geojson.zip
curl -O $B/polygons/hotosm_vnm_waterways_polygons_geojson.zip
unzip -o '*.zip'
# (tùy chọn) sông lớn phía Campuchia + đất nước láng giềng, biên giới
mkdir -p /tmp/khm && cd /tmp/khm
K=https://s3.dualstack.us-east-1.amazonaws.com/production-raw-data-api/ISO3/KHM/waterways
curl -O $K/lines/hotosm_khm_waterways_lines_geojson.zip && curl -O $K/polygons/hotosm_khm_waterways_polygons_geojson.zip && unzip -o '*.zip'
curl -o /tmp/ne_countries.geojson https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_admin_0_countries.geojson
cd -   # về thư mục repo
python3 -I tools/ban-do/build_water.py /tmp/osm index.html map-data.json --khm=/tmp/khm --ne=/tmp/ne_countries.geojson --graph=route-graph.json
```

## Mặt nước sông lớn + lớp chi tiết khi phóng to (`map-tiles/`)

Bản xuất HOT **thiếu mặt nước các sông lớn** (sông Hậu, sông Tiền, Cổ Chiên… là quan hệ đa vùng rất lớn trong OSM), nên
mặt nước lấy từ **Overture Maps** (theme `base/water`, cùng gốc OpenStreetMap, giấy phép ODbL). Overture cũng cho đường bộ
(`transportation/segment`) và tên địa danh (`divisions/division`).

```bash
pip install shapely scipy pyarrow fsspec aiohttp requests
R=release/2026-10-21.0/      # bản mới nhất: xem https://docs.overturemaps.org/release/latest/
python3 tools/ban-do/tai_overture.py $R base water /tmp/ov_water.parquet id,geometry,subtype,class,names,is_intermittent,sources
python3 tools/ban-do/tai_overture.py $R transportation segment /tmp/ov_seg.parquet id,geometry,subtype,class,names,road_flags,subclass
python3 tools/ban-do/tai_overture.py $R divisions division /tmp/ov_div.parquet id,geometry,subtype,class,names,population,country
# 1) bản đồ nền: thêm --ov=... vào lệnh build_water.py ở trên
python3 -I tools/ban-do/build_water.py /tmp/osm index.html map-data.json --khm=/tmp/khm --ne=/tmp/ne_countries.geojson --graph=route-graph.json --ov=/tmp/ov_water.parquet
# 2) các ô chi tiết (app chỉ tải ô đang xem khi phóng lớn): bờ sông thật, cồn, kênh nhỏ, đường lớn, phà, tên sông kênh, địa danh
python3 -I tools/ban-do/build_tiles.py /tmp/osm index.html map-data.json map-tiles --water=/tmp/ov_water.parquet --seg=/tmp/ov_seg.parquet --div=/tmp/ov_div.parquet
```

Không dùng (và không được vẽ lại từ) Google Maps: dữ liệu của Google có bản quyền, điều khoản cấm sao chép / đồ lại.

Sau đó tăng `VERSION` trong `sw.js` để máy đã cài app tải bản đồ mới.

Sửa tuyến: danh sách `ROUTES` và các điểm `N` (tọa độ + tên sông để bắt điểm) trong `build_water.py`.


Tên sông OSM còn thiếu nhiều (vd. sông quanh cảng nhà Sóc Trăng): trong app nhấn giữ trên sông → "Đặt tên sông / kênh ở đây". Tên lưu trên máy, nằm trong file Xuất dữ liệu, và được dùng khi tìm đường.
