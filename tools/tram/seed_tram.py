# Dựng dữ liệu trạm + nhật ký chuyến từ sổ tay viết tay (ảnh do chủ tàu gửi, 10/2026).
# Chạy: python3 tools/tram/seed_tram.py  → in ra JSON để nhúng vào index.html (MP_SEED_TRAM).
# Mỗi khoản đã cộng lại để đối chiếu với số tổng ghi trong sổ.
import json, re, sys
from collections import Counter

# id, tên, tỉnh (sau sáp nhập 2025), sông, ghi chú
ST = [
 ('cv-vl','Cảng vụ Vĩnh Long','Vĩnh Long','Sông Cổ Chiên',''),
 ('cuc-vl','Trạm Cục Vĩnh Long','Vĩnh Long','Sông Cổ Chiên',''),
 ('mang-thit','Trạm Mang Thít','Vĩnh Long','Sông Măng Thít',''),
 ('phong-vl','Trạm Phòng Vĩnh Long','Vĩnh Long','Sông Cổ Chiên',''),
 ('tram-vl','Trạm Vĩnh Long','Vĩnh Long','Sông Tiền',''),
 ('ben-tre','Trạm Bến Tre','Vĩnh Long','Sông Tiền','Bến Tre cũ'),
 ('rau-ram','Trạm Rau Răm','Vĩnh Long','Sông Tiền','Vị trí chưa rõ'),
 ('cho-lach','Trạm Chợ Lách','Vĩnh Long','Sông Cổ Chiên','Bến Tre cũ'),
 ('giao-hoa','Trạm Giao Hòa (?)','Vĩnh Long','Sông Tiền','Chữ trong sổ chưa rõ'),
 ('tam-binh','Trạm Tam Bình','Vĩnh Long','Sông Măng Thít',''),
 ('cuc-vl-hau','Trạm Cục Vĩnh Long (sông Hậu)','Vĩnh Long','Sông Hậu','Khu Trà Ôn'),
 ('binh-minh','Trạm Bình Minh','Vĩnh Long','Sông Hậu',''),
 ('dong-tam','Trạm Đồng Tâm','Đồng Tháp','Sông Tiền','Tiền Giang cũ'),
 ('my-tho','Trạm Mỹ Tho','Đồng Tháp','Sông Tiền','Tiền Giang cũ'),
 ('phong-tg','Trạm Phòng Tiền Giang (Mỹ Tho)','Đồng Tháp','Sông Tiền','Tiền Giang cũ'),
 ('ky-hon','Trạm Kỳ Hôn','Đồng Tháp','Rạch Kỳ Hôn','Đi Kỳ Hôn hoặc Chợ Gạo'),
 ('cho-gao','Trạm Chợ Gạo','Đồng Tháp','Kênh Chợ Gạo',''),
 ('cai-be','Trạm Cái Bè','Đồng Tháp','Sông Tiền',''),
 ('sa-dec','Trạm Sa Đéc','Đồng Tháp','Sông Tiền',''),
 ('cai-sach','Trạm Cái Sách (?)','','','Chữ trong sổ chưa rõ, sau Tam Bình'),
 ('knm','Trạm Kinh Nước Mặn','Tây Ninh','Kênh Nước Mặn','Long An cũ'),
 ('ben-luc','Trạm Bến Lức','Tây Ninh','Sông Vàm Cỏ Đông','Long An cũ'),
 ('tay-ninh','Trạm Tây Ninh','Tây Ninh','Sông Vàm Cỏ Đông',''),
 ('cv-duchoa','Cảng vụ Đức Hòa','Tây Ninh','Sông Vàm Cỏ Đông','Sổ ghi kèm tiền xe ôm'),
 ('doi2','Trạm Đội 2 (Vàm Sát)','TP.HCM','Sông Vàm Sát',''),
 ('tram1','Trạm 1 (TP.HCM)','TP.HCM','',''),
 ('tram2','Trạm 2','TP.HCM','',''),
 ('tram5','Trạm 5','TP.HCM','',''),
 ('tram6','Trạm 6 (TP.HCM)','TP.HCM','',''),
 ('cuc-hcm','Trạm Cục (TP.HCM)','TP.HCM','',''),
 ('t363sg','Trạm 363 Sài Gòn','TP.HCM','',''),
 ('t363vt','Trạm 363 Vũng Tàu','TP.HCM','','Vũng Tàu cũ'),
 ('tram8vt','Trạm 8 Vũng Tàu','TP.HCM','','Vũng Tàu cũ'),
 ('cv-vt','Cảng vụ Vũng Tàu','TP.HCM','Sông Dinh','Vũng Tàu cũ'),
 ('can-xac','Cần Xác (?)','TP.HCM','','Chữ trong sổ chưa rõ, khoản chi đầu chuyến Vũng Tàu'),
 ('bp-caimep','Biên phòng Cái Mép','TP.HCM','Sông Thị Vải',''),
 ('bp-thiengl','Biên phòng Thiềng Liềng','TP.HCM','','Cần Giờ'),
 ('bp-cangio','Biên phòng Cần Giờ','TP.HCM','',''),
 ('bp-donghoa','Biên phòng Đông Hòa','TP.HCM','','Cần Giờ'),
 ('cvhh','Cảng vụ Hàng hải (Cần Giờ)','TP.HCM','',''),
 ('cv-bd','Cảng vụ Bình Dương','TP.HCM','','Bình Dương cũ'),
 ('doi3-bd','Trạm Đội 3 Bình Dương','TP.HCM','','Bình Dương cũ'),
 ('tram-bd','Trạm Bình Dương','TP.HCM','','Bình Dương cũ'),
 ('t363bd','Trạm 363 Bình Dương','TP.HCM','','Bình Dương cũ'),
 ('binh-loi','Trạm Bình Lợi (?)','TP.HCM','Sông Sài Gòn','Chữ trong sổ chưa rõ'),
 ('cv-dn','Cảng vụ Đồng Nai','Đồng Nai','Sông Đồng Nai',''),
 ('tau','Trạm Tàu','Đồng Nai','','Sổ ghi "Trạm Tàu Đồng Nai"'),
 ('tram4','Trạm 4','Đồng Nai','','Sổ ghi "Trạm 4 Đồng Nai"'),
 ('phong-dn','Trạm Phòng (Đồng Nai)','Đồng Nai','','Sổ thường ghi tắt "Phòng"'),
 ('thanhtra-dn','Thanh tra Đồng Nai','Đồng Nai','',''),
 ('go-dau','Trạm Gò Dầu','Đồng Nai','Sông Thị Vải',''),
 ('cv-st','Cảng vụ Sóc Trăng','Cần Thơ','Sông Hậu','Sóc Trăng cũ'),
 ('dai-ngai','Trạm Đại Ngãi','Cần Thơ','Sông Hậu','Sóc Trăng cũ'),
 ('nhon-my','Trạm Nhơn Mỹ','Cần Thơ','Sông Hậu','Sóc Trăng cũ'),
 ('cai-con','Trạm Cái Côn','Cần Thơ','Sông Hậu',''),
 ('cuc-ct','Trạm Cục Cần Thơ','Cần Thơ','Sông Hậu',''),
 ('phong-ct','Trạm Phòng Cần Thơ','Cần Thơ','Sông Hậu',''),
 ('tram-ct','Trạm Cần Thơ','Cần Thơ','Sông Hậu',''),
 ('o-mon','Trạm Ô Môn','Cần Thơ','Sông Hậu',''),
 ('binh-thuy','Trạm Bình Thủy','Cần Thơ','Sông Hậu',''),
 ('cv-ct','Cảng vụ Cần Thơ','Cần Thơ','Sông Hậu','Cảng vụ nơi giao hàng'),
 ('cai-san','Trạm Cái Sắn','An Giang','Kênh Cái Sắn',''),
 ('cv-caisan','Cảng vụ (Cái Sắn)','An Giang','Kênh Cái Sắn','Cảng vụ nơi giao hàng'),
]
SID = {s[0] for s in ST}

GVL = 'Gạch Vĩnh Long → Cần Giờ'
def gach(k7, cucvl=500, phong_vl=400, extra=None):
    # danh sách chuẩn của tàu ST-06128 tuyến gạch (ghi giống nhau mỗi chuyến)
    L = [('cv-vl','Cảng vụ',500),('cuc-vl','Cục Vĩnh Long',cucvl),('mang-thit','Mang Thít',400),('phong-vl','Phòng Vĩnh Long',phong_vl),
         ('ben-tre','Bến Tre',400),('rau-ram','Rau Răm',400),k7,('knm','Kinh Nước Mặn',500),('doi2','Đội 2',500),('tram1','Trạm 1',500),
         ('t363sg','363 Sài Gòn',1000),('cuc-hcm','Cục',500),('tau','Tàu',500),('tram4','Trạm 4',500),('tram6','Trạm 6',500),
         ('phong-dn','Phòng',500),('tram5','Trạm 5',500),('t363vt','363 Vũng Tàu',800),('bp-cangio','Biên phòng Cần Giờ',1000),
         ('bp-donghoa','Biên phòng Đông Hòa',1000),('cvhh','Cảng vụ Hàng hải',2000)]
    return L
KH = ('ky-hon','Kỳ Hôn',300); CG = ('cho-gao','Chợ Gạo',300)
K = lambda n,a: ('',n,a)     # chi phí khác (không phải trạm)

TRIPS = [
 dict(id='nk-0629', d='2026-06-29', b='ST-06128', r=GVL, rid='hcm-cangio', c='Gạch, 485 kiện', w=13200000, items=gach(KH),
      n='26/06 20h Cần Giờ → 27/06 13h Vĩnh Long · nhận gạch 27/06–29/06 15h · 29/06 15h chạy → 30/06 19h Cần Giờ · vô giao 01/07 18h, giao xong 12h 03/07. Bơm 800 lít + 500 lít còn = 1.300 lít dầu (27/06). Cô Hằng chuyển 21.500.000 − 13.200.000 = 8.300.000 (29/06).'),
 dict(id='nk-0715', d='2026-07-15', b='ST-06128', r=GVL, rid='hcm-cangio', c='Gạch, 485 kiện', w=13200000, items=gach(CG),
      n='07/07 17h Vĩnh Thạnh → 08/07 17h Vĩnh Long · nhận gạch 09/07 12h30 → 15/07 10h xong · 15/07 10h chạy → 16/07 16h Cần Giờ · giao xong 5h 18/07. Bơm 1.300 lít dầu (07/07). Cô Hằng chuyển 22.000.000 − 13.200.000 = 8.800.000 (10/07).'),
 dict(id='nk-0722', d='2026-07-22', b='ST-06128', r='Đá Vũng Tàu → Cái Sắn', rid='mt-caisan', c='Đá 1x2, 996 tấn', w=13900000, items=[
   ('cv-vt','Cảng vụ',700),('can-xac','Cần Xác',1000),('tram8vt','Trạm 8 Vũng Tàu',700),('bp-caimep','Biên phòng Cái Mép',300),('go-dau','Gò Dầu',500),
   ('bp-thiengl','Biên phòng Thiềng Liềng',300),('tram5','Trạm 5',700),('tram2','Trạm 2',500),('t363vt','363 Vũng Tàu',700),('tram1','Trạm 1',500),
   ('phong-dn','Phòng',500),('tram4','Trạm 4',500),('cuc-hcm','Cục',500),('tau','Tàu',500),('t363sg','363 Sài Gòn',700),('knm','Kinh Nước Mặn',500),
   ('cho-gao','Chợ Gạo',300),('my-tho','Mỹ Tho',300),('ben-tre','Bến Tre',300),('cai-be','Cái Bè',300),('tram-vl','Vĩnh Long',400),('sa-dec','Sa Đéc',300),
   ('cai-san','Cái Sắn',500),('cv-caisan','Cảng vụ',600),K('Bồi dưỡng cập',1800)],
      n='18/07 5h Cần Giờ → 11h Vũng Tàu · nhận đá xong 9h 22/07 · 22/07 9h Vũng Tàu → 24/07 16h Cái Sắn · cập xong 16h 25/07.'),
 dict(id='nk-0802', d='2026-08-02', b='ST-06128', r=GVL, rid='hcm-cangio', c='Gạch, 485 kiện', w=13200000, items=gach(CG),
      n='25/07 16h Cái Sắn → 26/07 18h Vĩnh Long · 29/07 15h vô nhận hàng → 02/08 9h xong · 10h đi Cần Giờ (sổ ghi 03/07, có lẽ 03/08) · giao xong 06h 04/08. Bơm 1.300 lít dầu (25/07). Cô Hằng chuyển 22 triệu (29/07).'),
 dict(id='nk-0901', d='2026-09-01', b='ST-06128', r=GVL, rid='hcm-cangio', c='Gạch, 485 kiện', w=13200000, items=gach(CG),
      n='25/08 15h Trần Đề → 20h Đại Ngãi, hàn tàu · 28/08 → 15h 29/08 Vĩnh Long · 30/08 nhận gạch → 01/09 16h xong · 02/09 16h Cần Giờ, giao xong 07h (ngày giao trong sổ chưa rõ). Cô Hằng chuyển 22 triệu (30/08).'),
 dict(id='nk-0906', d='2026-09-06', b='', r=GVL, rid='hcm-cangio', c='Gạch', w=15500000, items=[
   ('cv-vl','Cảng vụ Vĩnh Long',500),('phong-vl','Trạm phòng Vĩnh Long',400),('cuc-vl','Trạm Cục',400),('cho-lach','Trạm Lách',400),
   ('rau-ram','Trạm Rau Răm',400),('dong-tam','Trạm Đồng Tâm',400),('ky-hon','Trạm Kỳ Hôn',400),('knm','Trạm Kinh Nước Mặn',400),
   ('doi2','Đội 2 Vàm Sát Sài Gòn',500),('cuc-hcm','Trạm Cục',500),('t363sg','Trạm 363 Sài Gòn',800),('tram1','Trạm 1',500),('tram4','Trạm 4',500),
   ('phong-dn','Trạm phòng',600),('tram5','Trạm 5',500),('tau','Trạm Tàu',500),('t363vt','Trạm 363 Vũng Tàu',800),('bp-cangio','Biên phòng Cần Giờ',1000),
   ('cvhh','Cảng vụ Hàng hải',2000),('bp-donghoa','Biên phòng cảng Đông Hòa',2000),K('Bồi dưỡng tài công',2000)],
      n='Sổ "Phí gạch Vĩnh Long – Cần Giờ" 06/09/2026 (chữ khác, không ghi tàu). Tổng phí trạm 13.500.000 + bồi dưỡng tài công 2.000.000.'),
 dict(id='nk-0910', d='2026-09-10', b='ST-06128', r=GVL, rid='hcm-cangio', c='Gạch, 485 kiện', w=13200000, items=gach(CG),
      n='07/09 15h Vĩnh Thạnh → 08/09 07h Vĩnh Long nhận gạch · 10/09 15h xong → 11/09 17h Cần Giờ · giao xong 23h 14/09. Bơm 1.300 lít dầu (07/09). Cô Hằng chuyển 22 triệu (08/09).'),
 dict(id='nk-0922', d='2026-09-22', b='ST-06128', r=GVL, rid='hcm-cangio', c='Gạch, 485 kiện', w=13200000, items=[
   ('cv-vl','Cảng vụ',500),('cuc-vl','Cục Vĩnh Long',400),('phong-vl','Phòng Vĩnh Long',400),('mang-thit','Mang Thít',400),('ben-tre','Bến Tre',400),
   ('my-tho','Mỹ Tho',400),('cho-gao','Chợ Gạo',300),('knm','Kinh Nước Mặn',500),('doi2','Đội 2',500),('tram1','Trạm 1',500),('t363sg','363 Sài Gòn',1000),
   ('cuc-hcm','Cục',500),('tau','Tàu',500),('tram4','Trạm 4',500),('tram6','Trạm 6',500),('phong-dn','Phòng',500),('tram5','Trạm 5',500),
   ('t363vt','363 Vũng Tàu',800),('bp-cangio','Biên phòng Cần Giờ',1000),('bp-donghoa','Biên phòng Đông Hòa',1000),('cvhh','Cảng vụ Hàng hải',2000)],
      n='20/09 17h Ngã 5 → 21/09 12h Vĩnh Long · nhận gạch xong 12h 22/09 → 23/09 Cần Giờ · giao xong 8h 24/09. Bơm 1.300 lít dầu (20/09). Cô Hằng chuyển 23 triệu (21/09).'),
 dict(id='nk-0928', d='2026-09-28', b='', r='Sóc Trăng → Cần Thơ', rid='st-cantho', c='', w=6750000, items=[
   K('Mua bình nước (?)',550),('cv-st','Cảng vụ Sóc Trăng',500),('dai-ngai','Trạm Đại Ngãi',300),('nhon-my','Trạm Nhơn Mỹ',300),('cuc-vl-hau','Trạm Cục Vĩnh',400),
   ('cai-con','Trạm Cái Côn',300),('phong-ct','Trạm Phòng Cần Thơ',400),('cuc-ct','Trạm Cục Cần Thơ',400),('binh-minh','Trạm Bình Minh',300),
   ('binh-thuy','Trạm Bình Thủy',300),K('Phí cảng',1000),('cv-ct','Cảng vụ',500),K('Bồi dưỡng cần cẩu',1500)],
      n='Sổ "Chuyến 5". 23/09 nhận phí ở bến nhà · 25/09 đổ dầu Bình Thủy 1.300 lít · 26/09 tới cảng Cần Thơ · 28/09 cảng … Ứng phí đi đường 6.000.000.'),
 dict(id='nk-251201', d='2025-12-01', b='', r='Đá Đồng Nai → Sóc Trăng', rid='st-bienhoa', c='Đá (chị Phương)', w=None, items=[
   ('cv-dn','Cảng vụ Đồng Nai',700),('doi3-bd','Trạm Đội 3 Bình Dương',500),('phong-dn','Trạm phòng Đồng Nai',500),('tram4','Trạm 4 Đồng Nai',500),
   ('tau','Trạm Tàu Đồng Nai',500),('thanhtra-dn','Thanh tra Đồng Nai',300),('t363bd','Trạm 363 Bình Dương',1000),('tram6','Trạm 6 Thành phố',500),
   ('cuc-hcm','Trạm Cục Thành phố',500),('t363sg','Trạm 363 Thành phố',1000),('tram1','Trạm 1 Thành phố',500),('doi2','Trạm Đội 2 Thành phố',500),
   ('knm','Trạm Kinh Nước Mặn',500),('ky-hon','Trạm Kỳ Hôn',300),('phong-tg','Trạm phòng Tiền Giang',300),('ben-tre','Trạm Bến Tre',300),
   ('rau-ram','Trạm Rau Răm',400),('phong-vl','Trạm phòng Vĩnh Long',300),('mang-thit','Trạm Mang Thít',400),('tam-binh','Trạm Tam Bình',400),
   ('cai-sach','Trạm Cái Sách',500)],
      n='Trang sổ ngày 01/12/2025, chưa có trang sau nên chưa có tổng.'),
 dict(id='nk-251016', d='2025-10-16', b='', r='Đá Bình Dương → Đức Hòa', rid='la-duchoa-bd', c='Đá', w=12050000, items=[
   ('cv-bd','Cảng vụ Bình Dương',700),('doi3-bd','Trạm Đội 3 Bình Dương',500),('tau','Trạm Tàu Đồng Nai',500),('tram4','Trạm 4 Đồng Nai',500),
   ('phong-dn','Trạm phòng Đồng Nai',500),('thanhtra-dn','Thanh tra Đồng Nai',400),('cuc-hcm','Trạm Cục',500),('tram6','Trạm 6 Thành phố',500),
   ('t363sg','Trạm 363',1000),('tram1','Trạm 1 Thành phố',500),('doi2','Trạm Đội 2 Thành phố',500),('knm','Trạm Kinh Nước Mặn',500),
   ('ben-luc','Trạm Bến Lức',500),('tay-ninh','Trạm Tây Ninh',500),K('Bồi dưỡng máng',400),K('Bồi dưỡng thợ cẩu',1700),
   ('cv-duchoa','Cảng vụ Đức Hòa + xe ôm',850),K('Tài công + vét đá',1500)],
      n='Chi chuyến phí đi 12.000.000 (13/10/2025).'),
 dict(id='nk-251008', d='2025-10-08', b='', r='Đá Bình Dương → Đức Hòa', rid='la-duchoa-bd', c='Đá', w=12050000, items=[
   ('cv-bd','Cảng vụ Bình Dương',700),('doi3-bd','Trạm Đội 3 Bình Dương',500),('tau','Trạm Tàu Đồng Nai',500),('tram4','Trạm 4 Đồng Nai',500),
   ('phong-dn','Trạm phòng Đồng Nai',500),('thanhtra-dn','Thanh tra Đồng Nai',400),('t363sg','Trạm 363',1000),('cuc-hcm','Trạm Cục',500),
   ('tram6','Trạm 6 Thành phố',500),('tram1','Trạm 1 Thành phố',500),('doi2','Trạm Đội 2',500),('knm','Trạm Kinh Nước Mặn',500),
   ('ben-luc','Trạm Bến Lức',500),('tay-ninh','Trạm Tây Ninh',500),('cv-duchoa','Cảng vụ Đức Hòa + xe ôm',850),K('Bồi dưỡng máng',400),
   K('Bồi dưỡng cập cẩu',1700),K('Tài công + vét đá',1500)],
      n='Chi chuyến ứng 22.000.000 (07/10/2025), còn lại em ứng 9.950.000.'),
 dict(id='nk-dn-dh', d='', b='', r='Đá Đồng Nai → Đức Hòa', rid='la-duchoa-dn', c='', w=10100000, items=[
   ('cv-dn','Cảng vụ Đồng Nai',800),K('Bồi dưỡng cập (1.500 đ/m³)',900),('tram-bd','Trạm Bình Dương',400),('phong-dn','Trạm phòng',500),
   ('binh-loi','Trạm Bình Lợi',400),('tau','Trạm Tàu',500),('tram4','Trạm 4',500),('cuc-hcm','Trạm Cục',500),('tram6','Trạm 6',500),
   ('tram1','Trạm 1',500),('knm','Trạm Kinh',500),('ben-luc','Trạm Bến Lức',500),('cv-duchoa','Cảng vụ Đức Hòa',800),
   K('Bồi dưỡng cập lên',1800),K('Tài công',1000)],
      n='Trang sổ không ghi ngày.'),
 dict(id='nk-dn-st', d='', b='', r='Đá Đồng Nai → Sóc Trăng', rid='st-bienhoa', c='', w=10500000, items=[
   ('cv-dn','Cảng vụ Đồng Nai',800),('tram-bd','Trạm Bình Dương',300),('binh-loi','Trạm Bình Lợi',400),('tau','Trạm Tàu',500),('phong-dn','Trạm phòng',500),
   ('cuc-hcm','Trạm Cục',500),('tram4','Trạm 4',500),('tram6','Trạm 6',500),('tram1','Trạm 1',500),('knm','Trạm Kinh',500),('cho-gao','Trạm Chợ Gạo',400),
   ('phong-tg','Trạm phòng Mỹ Tho',300),('giao-hoa','Trạm Giao Hòa',400),('cho-lach','Trạm Lách BT',400),('tram-vl','Trạm Vĩnh Long',400),
   ('mang-thit','Trạm Mang Thít',400),('tam-binh','Trạm Tam Bình',400),('cuc-vl-hau','Trạm Cục VL',400),('nhon-my','Trạm Nhơn Mỹ',500),
   ('dai-ngai','Trạm Đại Ngãi',500),('cv-st','Cảng vụ ST',600),K('Bồi dưỡng cập (1.500 đ/m³)',800)],
      n='Trang sổ không ghi ngày.'),
 dict(id='nk-0530', d='2026-05-30', b='', r='Sóc Trăng → Cần Thơ', rid='st-cantho', c='', w=7300000, items=[
   ('cv-st','Cảng vụ ST',500),('dai-ngai','Trạm Đại Ngãi',300),('nhon-my','Trạm Nhơn Mỹ',300),('cuc-ct','Cục Cần Thơ',400),('phong-ct','Phòng',200),
   ('cai-con','Trạm Cái Côn',300),('o-mon','Trạm Ô Môn',300),('tram-ct','Trạm Cần Thơ',300),('binh-minh','Trạm Bình Minh',300),('binh-thuy','Trạm Bình Thủy',300),
   ('cv-ct','Cảng vụ',500),K('Bến cảng',1100),K('Bồi dưỡng cập',1500),K('Thuyền trưởng',1000)],
      n='Sổ "Chuyến 1". Ứng phí 10.000.000 − 7.300.000 = 2.700.000. Đổ dầu Hưng Phú 1.150 lít (31/05), đổ 5 can dầu ở bãi nhà.'),
]

# kiểm tra: mã trạm hợp lệ, tổng khớp sổ
bad = 0
for t in TRIPS:
    s = 0
    for it in t['items']:
        assert it[0]=='' or it[0] in SID, (t['id'], it)
        s += it[2]
    s *= 1000
    if t['w'] and s != t['w']:
        print(f"⚠ {t['id']}: cộng {s:,} ≠ sổ ghi {t['w']:,}", file=sys.stderr); bad += 1
    else:
        print(f"✓ {t['id']}: {s:,}", file=sys.stderr)

# tuyến trên bản đồ: theo chuyến (rid) + trạm trên Kênh Chợ Gạo / Rạch Kỳ Hôn đi chung nhiều tuyến
mapd = json.load(open('map-data.json', encoding='utf-8'))
via_cg = [r['id'] for r in mapd['routes'] if 'Kênh Chợ Gạo' in r['via']]
obs, rts = {}, {}
for t in TRIPS:
    for it in t['items']:
        if it[0]:
            obs.setdefault(it[0], []).append((t['d'] or '0000', it[2]*1000))
            if t['rid']: rts.setdefault(it[0], set()).add(t['rid'])
for sid in ('cho-gao','ky-hon'): rts.setdefault(sid,set()).update(via_cg)

out_st = []
for sid, name, prov, river, note in ST:
    o = obs.get(sid, [])
    cnt = Counter(a for _, a in o)
    top = max(cnt.values()) if cnt else 0
    # số tiền mặc định = mức gặp nhiều nhất; hòa thì lấy mức của chuyến gần nhất
    fee = max((a for a in cnt if cnt[a]==top), key=lambda a: max(d for d, x in o if x==a)) if o else 0
    out_st.append(dict(id='s-'+sid, prov=prov, river=river, name=name, fee=fee, routes=sorted(rts.get(sid, [])), note=note, lat=None, lon=None))
out_tr = []
for t in TRIPS:
    out_tr.append(dict(id=t['id'], d=t['d'], b=t['b'], r=t['r'], rid=t['rid'], c=t['c'], w=t['w'], n=t['n'],
        items=[{'t':('s-'+i[0]) if i[0] else '', 'n':i[1], 'a':i[2]*1000} for i in t['items']]))
print(json.dumps({'v':1,'stations':out_st,'trips':out_tr}, ensure_ascii=False, separators=(',',':')))
