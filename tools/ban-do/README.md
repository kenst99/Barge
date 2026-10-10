# Dữ liệu bản đồ đường thủy (`map-data.json`)

Bản đồ điều phối dùng dữ liệu sông, kênh **thật** từ OpenStreetMap (bản xuất của HOT, giấy phép ODbL –
trong app có ghi nguồn "© OpenStreetMap"). File `map-data.json` ở thư mục gốc được dựng sẵn bằng script này:

- mặt nước sông lớn, hồ (bề rộng thật), sông/kênh chia 3 mức chi tiết theo độ phóng,
- nhãn tên sông, luồng biển (Gành Rái, ven biển, ra Phú Quốc – OSM không có, vẽ thêm),
- 33 tuyến vận chuyển tính đường ngắn nhất trên mạng sông OSM (ưu tiên sông lớn, kênh chính).

## Cập nhật khi OSM có dữ liệu mới

```bash
pip install shapely scipy
mkdir -p /tmp/osm && cd /tmp/osm
B=https://s3.dualstack.us-east-1.amazonaws.com/production-raw-data-api/ISO3/VNM/waterways
curl -O $B/lines/hotosm_vnm_waterways_lines_geojson.zip
curl -O $B/polygons/hotosm_vnm_waterways_polygons_geojson.zip
unzip -o '*.zip'
cd -   # về thư mục repo
python3 -I tools/ban-do/build_water.py /tmp/osm index.html map-data.json
```

Sau đó tăng `VERSION` trong `sw.js` để máy đã cài app tải bản đồ mới.

Sửa tuyến: danh sách `ROUTES` và các điểm `N` (tọa độ + tên sông để bắt điểm) trong `build_water.py`.
