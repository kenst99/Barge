// api/ai.js — Vercel Function: trợ lý AI cho đội sà lan (Gemini / Claude / GPT).
// App gửi: POST /api/ai  {provider, model?, messages:[{role:'user'|'assistant', text}], context:{...}}
// Trả về: {text, marks:[{name,lat,lon,kind,...}], sources:[{title,url}], provider, model}
//
// Khóa API lấy theo thứ tự: header x-ai-key (người dùng tự nhập trong app) → biến môi trường
//   GEMINI_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY (đặt trong Vercel → Settings → Environment Variables).
// Nếu đặt biến AI_PASS, app phải gửi đúng mật khẩu đó (header x-app-pass) mới dùng được khóa của máy chủ.
//
// Công cụ cho AI: tìm cây xăng / chỗ sửa tàu / cảng thật trên OpenStreetMap (dọc tuyến hoặc quanh một điểm),
// tìm tọa độ địa danh, thời tiết + sóng biển (Open-Meteo), con nước (theo tuổi trăng), ghim lên bản đồ,
// và tìm kiếm web (giá dầu, giá cát…) bằng công cụ tìm kiếm có sẵn của từng hãng.

const UA = 'TrungHieuSaLan/1.0 (quanlysalan.vercel.app)';
const DEFAULT_MODEL = { gemini: 'gemini-3.8-flash', claude: 'claude-opus-5-5', openai: 'gpt-5.5' };
const ENV_KEY = { gemini: 'GEMINI_API_KEY', claude: 'ANTHROPIC_API_KEY', openai: 'OPENAI_API_KEY' };
const MAX_STEPS = 8;

// ─────────────── tiện ích chung ───────────────
const R = Math.PI / 180;
function km(a, b) { // a,b = [lat,lon]
  const dLat = (b[0] - a[0]) * R, dLon = (b[1] - a[1]) * R;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * R) * Math.cos(b[0] * R) * Math.sin(dLon / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(h));
}
function kmToLine(p, line) { // khoảng cách gần đúng từ điểm tới đường gấp khúc
  let best = Infinity;
  const kx = 111.32 * Math.cos(p[0] * R), ky = 110.57;
  for (let i = 0; i < line.length - 1; i++) {
    const ax = (line[i][1] - p[1]) * kx, ay = (line[i][0] - p[0]) * ky;
    const bx = (line[i + 1][1] - p[1]) * kx, by = (line[i + 1][0] - p[0]) * ky;
    const dx = bx - ax, dy = by - ay, l2 = dx * dx + dy * dy;
    const t = l2 ? Math.max(0, Math.min(1, -(ax * dx + ay * dy) / l2)) : 0;
    best = Math.min(best, Math.hypot(ax + t * dx, ay + t * dy));
  }
  return line.length === 1 ? km(p, line[0]) : best;
}
const num = (v, d) => (v === undefined || v === null || v === '' || !isFinite(+v)) ? d : +v;
const inVN = (lat, lon) => lat > 5 && lat < 24 && lon > 100 && lon < 112;

async function getJSON(url, opt = {}, ms = 20000) {
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms);
  try {
    const r = await fetch(url, Object.assign({ signal: ctl.signal }, opt));
    const txt = await r.text();
    let j; try { j = JSON.parse(txt); } catch (e) { j = null; }
    if (!r.ok) { const e = new Error((j && (j.error && (j.error.message || j.error))) || txt.slice(0, 300) || ('HTTP ' + r.status)); e.status = r.status; throw e; }
    return j;
  } finally { clearTimeout(t); }
}

// ─────────────── con nước theo tuổi trăng (cùng công thức với app) ───────────────
const SYN = 29.530588853, NEWMOON = Date.UTC(2000, 0, 6, 18, 14), DAY = 86400000, TZ = 7 * 3600000;
const moonAge = t => { const a = ((t - NEWMOON) / DAY) % SYN; return a < 0 ? a + SYN : a; };
const TIDE_ST = [
  { id: 'dinh-an', name: 'Định An (cửa sông Hậu)', lat: 9.560, lon: 106.350 },
  { id: 'vung-tau', name: 'Vũng Tàu', lat: 10.340, lon: 107.070 },
  { id: 'can-gio', name: 'Cần Giờ', lat: 10.400, lon: 106.960 },
  { id: 'sai-gon', name: 'Sài Gòn (Phú An)', lat: 10.770, lon: 106.710 },
  { id: 'ha-tien', name: 'Hà Tiên', lat: 10.370, lon: 104.470 },
];
function tideDay(t) {
  const age = moonAge(t), localDay = x => Math.floor((x + TZ) / DAY);
  const lunar = localDay(t) - localDay(t - age * DAY) + 1;
  let k;
  if (age < 4 || age >= 28.5 || (age >= 14.3 && age < 18.8)) k = 'Nước rong (triều cường): nước lớn cao, ròng sâu, chảy mạnh';
  else if ((age >= 6 && age < 10.3) || (age >= 20.8 && age < 25)) k = 'Nước kém: biên độ nhỏ, chảy yếu';
  else if (age < 6 || (age >= 18.8 && age < 20.8)) k = 'Nước giảm dần về kém';
  else k = 'Nước sinh, đang lớn dần lên rong';
  const d = new Date(t + TZ);
  return { ngay: `${String(d.getUTCDate()).padStart(2, '0')}/${String(d.getUTCMonth() + 1).padStart(2, '0')}/${d.getUTCFullYear()}`, am_lich_xap_xi: lunar, con_nuoc: k };
}
function toolTide({ lat, lon, days }) {
  days = Math.max(1, Math.min(15, Math.round(num(days, 3))));
  const out = { ghi_chu: 'Nhận định theo tuổi trăng, có thể lệch ±1 ngày. Giờ nước lớn/ròng chính xác xem link trạm.', ngay: [] };
  const now = Date.now();
  for (let i = 0; i < days; i++) out.ngay.push(tideDay(now + i * DAY));
  lat = num(lat, NaN); lon = num(lon, NaN);
  if (isFinite(lat) && isFinite(lon)) {
    let id = 'dinh-an';
    if (lon < 105.25 && lat < 10.45) id = 'ha-tien';
    else if (lon >= 106.95) id = 'vung-tau';
    else if (lon >= 106.75 && lat < 10.5) id = 'can-gio';
    else if (lon >= 106.3 && lat >= 10.45) id = 'sai-gon';
    const st = TIDE_ST.find(x => x.id === id), d = Math.round(km([lat, lon], [st.lat, st.lon]));
    out.tram_tham_chieu = { ten: st.name, cach_km: d, link_gio_nuoc: `https://thegioimoicau.com/dia-danh/${id}/trang-1`,
      luu_y: d > 60 ? 'Xa trạm: con nước tới trễ hơn và yếu hơn trạm ven biển.' : '' };
  }
  return out;
}

// ─────────────── thời tiết + sóng (Open-Meteo, không cần khóa) ───────────────
const WMO = { 0: 'Trời quang', 1: 'Ít mây', 2: 'Có mây', 3: 'Nhiều mây', 45: 'Sương mù', 48: 'Sương mù', 51: 'Mưa phùn nhẹ', 53: 'Mưa phùn', 55: 'Mưa phùn dày',
  61: 'Mưa nhỏ', 63: 'Mưa vừa', 65: 'Mưa to', 80: 'Mưa rào nhẹ', 81: 'Mưa rào', 82: 'Mưa rào rất to', 95: 'Dông', 96: 'Dông, mưa đá', 99: 'Dông mạnh, mưa đá' };
async function toolWeather({ lat, lon, days }) {
  lat = num(lat, NaN); lon = num(lon, NaN);
  if (!isFinite(lat) || !isFinite(lon)) return { loi: 'Thiếu tọa độ. Dùng find_location để lấy tọa độ địa danh trước.' };
  days = Math.max(1, Math.min(7, Math.round(num(days, 3))));
  const q = `latitude=${lat}&longitude=${lon}&timezone=Asia%2FHo_Chi_Minh&forecast_days=${days}`;
  const w = await getJSON(`https://api.open-meteo.com/v1/forecast?${q}&wind_speed_unit=kmh` +
    '&current=temperature_2m,weather_code,wind_speed_10m,wind_gusts_10m,precipitation' +
    '&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max');
  const out = { nguon: 'Open-Meteo', hien_tai: w.current && {
      nhiet_do_C: w.current.temperature_2m, troi: WMO[w.current.weather_code] || w.current.weather_code,
      gio_kmh: w.current.wind_speed_10m, gio_giat_kmh: w.current.wind_gusts_10m, mua_mm: w.current.precipitation },
    ngay: (w.daily && w.daily.time || []).map((t, i) => ({ ngay: t, troi: WMO[w.daily.weather_code[i]] || w.daily.weather_code[i],
      nhiet_do_C: `${w.daily.temperature_2m_min[i]}–${w.daily.temperature_2m_max[i]}`, mua_mm: w.daily.precipitation_sum[i],
      kha_nang_mua_pct: w.daily.precipitation_probability_max[i], gio_max_kmh: w.daily.wind_speed_10m_max[i], gio_giat_kmh: w.daily.wind_gusts_10m_max[i] })) };
  try { // sóng biển – chỉ có nghĩa ở cửa sông / ven biển
    const m = await getJSON(`https://marine-api.open-meteo.com/v1/marine?${q}&daily=wave_height_max`, {}, 8000);
    if (m && m.daily && m.daily.wave_height_max && m.daily.wave_height_max.some(v => v != null))
      out.song_bien_max_m = m.daily.time.map((t, i) => ({ ngay: t, m: m.daily.wave_height_max[i] }));
  } catch (e) { /* trong sông thường không có số liệu sóng */ }
  return out;
}

// ─────────────── tìm tọa độ địa danh (Nominatim) ───────────────
async function toolGeocode({ query }) {
  if (!query) return { loi: 'Thiếu tên địa danh' };
  const j = await getJSON('https://nominatim.openstreetmap.org/search?format=jsonv2&limit=5&countrycodes=vn&accept-language=vi&q=' +
    encodeURIComponent(query), { headers: { 'User-Agent': UA } }, 12000);
  return { ket_qua: (j || []).map(x => ({ ten: x.display_name, lat: +(+x.lat).toFixed(5), lon: +(+x.lon).toFixed(5), loai: x.type })) };
}

// ─────────────── tìm địa điểm thật trên OpenStreetMap (Overpass) ───────────────
const OVERPASS = ['https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter', 'https://overpass.kumi.systems/api/interpreter'];
const KIND_Q = {
  fuel: ['nwr["amenity"="fuel"]', 'nwr["waterway"="fuel"]', 'nwr["seamark:small_craft_facility:category"~"fuel"]'],
  repair: ['nwr["industrial"="shipyard"]', 'nwr["craft"~"boatbuilder|shipwright"]', 'nwr["waterway"="boatyard"]', 'nwr["shop"="boat"]',
    'nwr["name"~"sửa tàu|sửa ghe|sửa sà lan|sửa xà lan|đóng tàu|đóng ghe|ụ tàu|cơ khí tàu|cơ khí thủy|xưởng tàu|nhà máy tàu",i]'],
  port: ['nwr["landuse"="port"]', 'nwr["industrial"="port"]', 'nwr["harbour"]', 'nwr["amenity"="ferry_terminal"]',
    'nwr["man_made"="pier"]["name"]', 'nwr["name"~"^(cảng|bến) ",i]'],
};
async function overpass(q) {
  let err;
  for (const u of OVERPASS) {
    try { return await getJSON(u, { method: 'POST', headers: { 'User-Agent': UA, 'Content-Type': 'application/x-www-form-urlencoded' }, body: 'data=' + encodeURIComponent(q) }, 25000); }
    catch (e) { err = e; }
  }
  throw err || new Error('Overpass lỗi');
}
function sampleLine(pts, maxN) {
  if (pts.length <= maxN) return pts;
  const out = [], step = (pts.length - 1) / (maxN - 1);
  for (let i = 0; i < maxN; i++) out.push(pts[Math.round(i * step)]);
  return out;
}
async function toolPlaces(args, ctx) {
  const kinds = args.kind === 'all' || !args.kind ? ['fuel', 'repair', 'port'] : [args.kind].filter(k => KIND_Q[k]);
  if (!kinds.length) return { loi: 'kind phải là fuel, repair, port hoặc all' };
  let line = null, center = null, routeName = '';
  const rid = args.route_id === 'current' ? (ctx.selectedRoute || '') : args.route_id;
  if (rid) {
    const r = (ctx.routes || []).find(x => x.id === rid);
    if (!r || !Array.isArray(r.pts) || !r.pts.length) return { loi: `Không có tuyến "${rid}". Các tuyến: ${(ctx.routes || []).map(x => x.id).join(', ')}` };
    line = r.pts.filter(p => Array.isArray(p) && isFinite(p[0]) && isFinite(p[1])); routeName = r.name;
  } else {
    const lat = num(args.lat, NaN), lon = num(args.lon, NaN);
    if (!isFinite(lat) || !isFinite(lon)) return { loi: 'Cần route_id hoặc lat/lon (dùng find_location để lấy tọa độ địa danh).' };
    center = [lat, lon];
  }
  const rkm = Math.max(0.2, Math.min(line ? 5 : 30, num(args.radius_km, line ? 1.5 : 8)));
  const m = Math.round(rkm * 1000);
  let around;
  if (line) {
    const s = sampleLine(line, 120);
    around = `(around:${m},${s.map(p => p[0].toFixed(5) + ',' + p[1].toFixed(5)).join(',')})`;
  } else around = `(around:${m},${center[0]},${center[1]})`;
  const parts = kinds.flatMap(k => KIND_Q[k].map(s => s + around + ';'));
  if (args.keyword) parts.push(`nwr["name"~"${String(args.keyword).replace(/["\\]/g, '').slice(0, 60)}",i]${around};`);
  const j = await overpass(`[out:json][timeout:22];(${parts.join('')});out center tags 300;`);
  const kindOf = t => {
    if (t.amenity === 'fuel' || t.waterway === 'fuel' || /fuel/.test(t['seamark:small_craft_facility:category'] || '')) return 'fuel';
    if (t.industrial === 'shipyard' || /boatbuilder|shipwright/.test(t.craft || '') || t.waterway === 'boatyard' || t.shop === 'boat' ||
      /sửa|đóng tàu|đóng ghe|ụ tàu|cơ khí|xưởng tàu|nhà máy tàu/i.test(t.name || '')) return 'repair';
    if (t.landuse === 'port' || t.industrial === 'port' || t.harbour || t.amenity === 'ferry_terminal' || t.man_made === 'pier' || /^(cảng|bến) /i.test(t.name || '')) return 'port';
    return 'other';
  };
  const seen = new Set();
  const list = (j.elements || []).map(e => {
    const lat = e.lat != null ? e.lat : e.center && e.center.lat, lon = e.lon != null ? e.lon : e.center && e.center.lon, t = e.tags || {};
    if (lat == null || lon == null) return null;
    const p = [lat, lon], d = line ? kmToLine(p, line) : km(p, center);
    const name = t.name || t['name:vi'] || t.brand || t.operator || '';
    return { name: name || '(chưa có tên trên bản đồ)', kind: kindOf(t), lat: +lat.toFixed(5), lon: +lon.toFixed(5),
      cach_km: +d.toFixed(2), brand: t.brand || t.operator || undefined, phone: t.phone || t['contact:phone'] || undefined,
      address: [t['addr:housenumber'], t['addr:street'], t['addr:subdistrict'] || t['addr:village'], t['addr:district'], t['addr:city'] || t['addr:province']].filter(Boolean).join(', ') || undefined,
      opening_hours: t.opening_hours || undefined, osm: `https://www.openstreetmap.org/${e.type}/${e.id}` };
  }).filter(x => x && !seen.has(x.osm) && seen.add(x.osm) && x.cach_km <= rkm + 0.05)
    .sort((a, b) => (a.name.startsWith('(') - b.name.startsWith('(')) || a.cach_km - b.cach_km);
  return { nguon: 'OpenStreetMap (cộng đồng đóng góp, có thể thiếu hoặc cũ)', pham_vi: line ? `cách tuyến ${routeName} ≤ ${rkm} km` : `bán kính ${rkm} km`,
    tong: list.length, dia_diem: list.slice(0, 30),
    goi_y: list.length ? undefined : 'Không thấy. Thử tăng radius_km, đổi kind, hoặc tìm web (nhiều cây xăng nổi/xưởng ven sông chưa có trên OSM).' };
}

// ─────────────── định nghĩa công cụ (chung cho 3 hãng) ───────────────
const TOOLS = [
  { name: 'search_places', description: 'Tìm địa điểm THẬT trên OpenStreetMap: cây xăng/dầu (fuel), xưởng sửa – đóng tàu, ụ tàu (repair), cảng/bến (port). Tìm dọc một tuyến đường thủy (route_id, khoảng cách tính tới tim tuyến) hoặc quanh một điểm (lat/lon). Kết quả có tên, tọa độ, khoảng cách, số điện thoại nếu có.',
    parameters: { type: 'object', properties: {
      kind: { type: 'string', enum: ['fuel', 'repair', 'port', 'all'], description: 'Loại địa điểm' },
      route_id: { type: 'string', description: 'Mã tuyến trong danh sách tuyến của app, hoặc "current" = tuyến đang chọn trên bản đồ' },
      lat: { type: 'number' }, lon: { type: 'number' },
      radius_km: { type: 'number', description: 'Dọc tuyến mặc định 1.5 km (tối đa 5), quanh điểm mặc định 8 km (tối đa 30)' },
      keyword: { type: 'string', description: 'Lọc thêm theo tên, ví dụ "Petrolimex"' } }, required: ['kind'] } },
  { name: 'find_location', description: 'Tìm tọa độ của một địa danh ở Việt Nam (xã, thị trấn, cầu, chợ, bến…).',
    parameters: { type: 'object', properties: { query: { type: 'string', description: 'Tên địa danh, nên kèm tỉnh, ví dụ "Cái Răng, Cần Thơ"' } }, required: ['query'] } },
  { name: 'get_weather', description: 'Dự báo thời tiết (mưa, gió, gió giật, nhiệt độ) và độ cao sóng biển nếu ở ven biển, tối đa 7 ngày.',
    parameters: { type: 'object', properties: { lat: { type: 'number' }, lon: { type: 'number' }, days: { type: 'number', description: '1–7, mặc định 3' } }, required: ['lat', 'lon'] } },
  { name: 'get_tide', description: 'Con nước (rong / kém / sinh / giảm) theo tuổi trăng cho các ngày tới, kèm trạm thủy triều tham chiếu gần vị trí và link giờ nước lớn/ròng.',
    parameters: { type: 'object', properties: { lat: { type: 'number' }, lon: { type: 'number' }, days: { type: 'number', description: '1–15, mặc định 3' } } } },
  { name: 'mark_on_map', description: 'Ghim các địa điểm lên bản đồ của app để người dùng xem và bấm lưu. Chỉ ghim địa điểm có tọa độ lấy từ công cụ hoặc người dùng cung cấp, không tự bịa tọa độ.',
    parameters: { type: 'object', properties: { places: { type: 'array', items: { type: 'object', properties: {
      name: { type: 'string' }, lat: { type: 'number' }, lon: { type: 'number' }, kind: { type: 'string', enum: ['fuel', 'repair', 'port', 'other'] },
      note: { type: 'string', description: 'Ghi chú ngắn: cách tuyến bao xa, giờ mở cửa…' }, phone: { type: 'string' }, address: { type: 'string' } },
      required: ['name', 'lat', 'lon', 'kind'] } } }, required: ['places'] } },
];
const SEARCH_WEB = { name: 'search_web', description: 'Tìm kiếm Google cho thông tin mới: giá xăng dầu hôm nay, giá cát/đá, tin luồng lạch, thông báo hàng hải, cấm cầu…',
  parameters: { type: 'object', properties: { query: { type: 'string' } }, required: ['query'] } };

async function runTool(name, args, ctx, st) {
  try {
    if (name === 'search_places') return await toolPlaces(args || {}, ctx);
    if (name === 'find_location') return await toolGeocode(args || {});
    if (name === 'get_weather') return await toolWeather(args || {});
    if (name === 'get_tide') return toolTide(args || {});
    if (name === 'mark_on_map') {
      const ok = (args && Array.isArray(args.places) ? args.places : []).filter(p => p && p.name && inVN(+p.lat, +p.lon)).slice(0, 40)
        .map(p => ({ name: String(p.name).slice(0, 80), lat: +p.lat, lon: +p.lon, kind: ['fuel', 'repair', 'port'].includes(p.kind) ? p.kind : 'other',
          note: p.note ? String(p.note).slice(0, 200) : '', phone: p.phone ? String(p.phone).slice(0, 40) : '', address: p.address ? String(p.address).slice(0, 160) : '' }));
      st.marks.push(...ok);
      return { da_ghim: ok.length };
    }
    if (name === 'search_web' && st.searchWeb) return await st.searchWeb(args && args.query);
    return { loi: 'Không có công cụ ' + name };
  } catch (e) {
    return { loi: 'Công cụ ' + name + ' lỗi: ' + (e.name === 'AbortError' ? 'hết thời gian chờ' : e.message) };
  }
}

// ─────────────── lời dặn hệ thống ───────────────
function systemPrompt(ctx) {
  const now = new Date(Date.now() + TZ);
  const day = `${['Chủ nhật', 'Thứ hai', 'Thứ ba', 'Thứ tư', 'Thứ năm', 'Thứ sáu', 'Thứ bảy'][now.getUTCDay()]}, ${now.getUTCDate()}/${now.getUTCMonth() + 1}/${now.getUTCFullYear()} ${String(now.getUTCHours()).padStart(2, '0')}:${String(now.getUTCMinutes()).padStart(2, '0')}`;
  const L = [];
  L.push('Bạn là trợ lý điều phối của Công ty sà lan Trung Hiếu (chở cát bằng sà lan trên sông Tiền, sông Hậu, kênh rạch miền Tây, đi Đồng Nai, Long An, Vũng Tàu, Sóc Trăng…).');
  L.push('Người dùng là chủ tàu, tài công, điều độ. Trả lời bằng tiếng Việt, ngắn gọn, đi thẳng vào việc, dùng gạch đầu dòng khi liệt kê. Đơn vị km, km/h, mét.');
  L.push(`Bây giờ là ${day} (giờ Việt Nam).`);
  L.push('Quy tắc:');
  L.push('- Tìm cây xăng, chỗ sửa tàu, cảng: dùng search_places (dọc tuyến khi người dùng nói tuyến hoặc "trên đường đi"; quanh điểm khi nói một nơi). Sau đó gọi mark_on_map với các địa điểm phù hợp nhất (ưu tiên sát bờ sông, có tên) rồi tóm tắt danh sách: tên, cách tuyến/điểm bao xa, số điện thoại nếu có.');
  L.push('- Cây xăng trên OSM phần lớn là cây xăng đường bộ; nói rõ cái nào sát sông (≤ 0,3 km) mới có thể cập ghe/sà lan. Nếu không thấy, tìm web để gợi ý thêm, nhưng chỉ ghim khi có tọa độ đáng tin.');
  L.push('- Không bao giờ bịa tọa độ, số điện thoại, giá cả. Không có thì nói không có.');
  L.push('- Thời tiết: get_weather (lấy tọa độ từ ngữ cảnh hoặc find_location). Nhắc gió giật ≥ 40 km/h, dông, sóng ≥ 1,5 m là nguy hiểm cho sà lan, nhất là chặng biển.');
  L.push('- Con nước: get_tide, kèm link giờ nước của trạm tham chiếu.');
  L.push('- Giá cả (xăng dầu DO, giá cát, phí…) và tin mới: tìm web, ghi rõ nguồn và ngày áp dụng, nói đây là giá tham khảo.');
  L.push('- Khi người dùng hỏi tuyến/sà lan cụ thể, dùng dữ liệu ngữ cảnh bên dưới.');
  L.push('');
  L.push('NGỮ CẢNH TỪ APP:');
  const routes = ctx.routes || [];
  if (routes.length) L.push('Tuyến đường thủy (id: tên, km): ' + routes.map(r => `${r.id}: ${r.name}${r.km ? ', ' + r.km + ' km' : ''}${r.sea ? ', có chặng biển' : ''}`).join(' | '));
  if (ctx.selectedRoute) { const r = routes.find(x => x.id === ctx.selectedRoute); L.push(`Tuyến đang chọn trên bản đồ: ${ctx.selectedRoute}${r ? ' (' + r.name + ')' : ''}`); }
  if (Array.isArray(ctx.barges) && ctx.barges.length) L.push('Sà lan: ' + ctx.barges.map(b => `${b.code} ${b.label || ''}${b.lat != null ? ` tại ${(+b.lat).toFixed(4)},${(+b.lon).toFixed(4)}` : ' (chưa có vị trí)'}${b.status ? ', ' + b.status : ''}${b.ago ? ', cập nhật ' + b.ago : ''}`).join('; '));
  if (Array.isArray(ctx.pois) && ctx.pois.length) L.push('Địa điểm đã lưu: ' + ctx.pois.slice(0, 40).map(p => `${p.name} (${p.type}) ${(+p.lat).toFixed(4)},${(+p.lon).toFixed(4)}`).join('; '));
  if (ctx.center) L.push(`Tâm bản đồ đang xem: ${(+ctx.center[0]).toFixed(4)},${(+ctx.center[1]).toFixed(4)}`);
  if (ctx.speed) L.push(`Tốc độ sà lan mặc định: ${ctx.speed} km/h`);
  return L.join('\n');
}

// ─────────────── từng hãng ───────────────
async function runGemini(key, model, sys, msgs, ctx, st) {
  const base = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`;
  const headers = { 'Content-Type': 'application/json', 'x-goog-api-key': key };
  // Google Search chạy trong một lượt gọi riêng để kết hợp được với công cụ tự định nghĩa
  st.searchWeb = async (query) => {
    const j = await getJSON(base, { method: 'POST', headers, body: JSON.stringify({
      contents: [{ role: 'user', parts: [{ text: `Tìm và tóm tắt ngắn gọn bằng tiếng Việt, ghi rõ ngày và nguồn: ${query}` }] }],
      tools: [{ google_search: {} }] }) }, 45000);
    const c = j.candidates && j.candidates[0];
    const chunks = (c && c.groundingMetadata && c.groundingMetadata.groundingChunks) || [];
    chunks.forEach(ch => ch.web && st.sources.push({ title: ch.web.title || ch.web.uri, url: ch.web.uri }));
    return { tom_tat: ((c && c.content && c.content.parts) || []).map(p => p.text || '').join(''), nguon: chunks.map(ch => ch.web && ch.web.title).filter(Boolean) };
  };
  const contents = msgs.map(m => ({ role: m.role === 'assistant' ? 'model' : 'user', parts: [{ text: m.text }] }));
  const tools = [{ functionDeclarations: [...TOOLS, SEARCH_WEB].map(t => ({ name: t.name, description: t.description, parameters: t.parameters })) }];
  for (let step = 0; step < MAX_STEPS; step++) {
    const j = await getJSON(base, { method: 'POST', headers, body: JSON.stringify({
      systemInstruction: { parts: [{ text: sys }] }, contents, tools,
      generationConfig: { thinkingConfig: { thinkingLevel: 'low' } } }) }, 60000);
    const c = j.candidates && j.candidates[0];
    if (!c || !c.content) return (j.promptFeedback && j.promptFeedback.blockReason) ? 'Câu hỏi bị chặn bởi bộ lọc của Gemini.' : 'Gemini không trả lời.';
    const parts = c.content.parts || [];
    contents.push(c.content);                                  // giữ nguyên (có chữ ký suy nghĩ) để gọi tiếp
    const calls = parts.filter(p => p.functionCall);
    if (!calls.length) return parts.filter(p => p.text && !p.thought).map(p => p.text).join('');
    const res = await Promise.all(calls.map(async p => ({ functionResponse: Object.assign({ name: p.functionCall.name,
      response: { result: await runTool(p.functionCall.name, p.functionCall.args, ctx, st) } }, p.functionCall.id ? { id: p.functionCall.id } : {}) })));
    contents.push({ role: 'user', parts: res });
  }
  return 'Trợ lý cần quá nhiều bước, hãy hỏi cụ thể hơn.';
}

async function runClaude(key, model, sys, msgs, ctx, st) {
  const messages = msgs.map(m => ({ role: m.role === 'assistant' ? 'assistant' : 'user', content: m.text }));
  const tools = [...TOOLS.map(t => ({ name: t.name, description: t.description, input_schema: t.parameters })),
    { type: 'web_search_20260209', name: 'web_search', max_uses: 4, user_location: { type: 'approximate', country: 'VN', timezone: 'Asia/Ho_Chi_Minh' } }];
  const headers = { 'Content-Type': 'application/json', 'x-api-key': key, 'anthropic-version': '2023-06-01' };
  for (let step = 0; step < MAX_STEPS; step++) {
    const j = await getJSON('https://api.anthropic.com/v1/messages', { method: 'POST', headers, body: JSON.stringify({
      model, max_tokens: 16000, system: sys, messages, tools, output_config: { effort: 'low' } }) }, 120000);
    const content = j.content || [];
    content.forEach(b => {
      if (b.type === 'web_search_tool_result' && Array.isArray(b.content)) b.content.forEach(r => r.url && st.sources.push({ title: r.title || r.url, url: r.url }));
    });
    if (j.stop_reason === 'refusal') return 'Claude từ chối trả lời câu hỏi này.';
    messages.push({ role: 'assistant', content });              // giữ nguyên các khối (kể cả suy nghĩ) để gọi tiếp
    if (j.stop_reason === 'pause_turn') continue;               // tìm web dài, cho chạy tiếp
    const uses = content.filter(b => b.type === 'tool_use');
    if (j.stop_reason !== 'tool_use' || !uses.length) return content.filter(b => b.type === 'text').map(b => b.text).join('');
    const results = await Promise.all(uses.map(async b => ({ type: 'tool_result', tool_use_id: b.id,
      content: JSON.stringify(await runTool(b.name, b.input, ctx, st)) })));
    messages.push({ role: 'user', content: results });          // mọi kết quả trong một tin nhắn
  }
  return 'Trợ lý cần quá nhiều bước, hãy hỏi cụ thể hơn.';
}

async function runOpenAI(key, model, sys, msgs, ctx, st) {
  const headers = { 'Content-Type': 'application/json', Authorization: 'Bearer ' + key };
  const tools = [...TOOLS.map(t => ({ type: 'function', name: t.name, description: t.description, parameters: t.parameters })),
    { type: 'web_search', user_location: { type: 'approximate', country: 'VN', timezone: 'Asia/Ho_Chi_Minh' } }];
  let input = msgs.map(m => ({ role: m.role === 'assistant' ? 'assistant' : 'user', content: m.text })), prev = null;
  for (let step = 0; step < MAX_STEPS; step++) {
    const body = { model, instructions: sys, input, tools, reasoning: { effort: 'low' } };
    if (prev) body.previous_response_id = prev;
    const j = await getJSON('https://api.openai.com/v1/responses', { method: 'POST', headers, body: JSON.stringify(body) }, 120000);
    prev = j.id;
    const out = j.output || [];
    let text = '';
    out.forEach(o => {
      if (o.type === 'message') (o.content || []).forEach(c => {
        if (c.type === 'output_text') { text += c.text; (c.annotations || []).forEach(a => a.type === 'url_citation' && st.sources.push({ title: a.title || a.url, url: a.url })); }
        if (c.type === 'refusal') text += c.refusal;
      });
    });
    const calls = out.filter(o => o.type === 'function_call');
    if (!calls.length) return text;
    input = await Promise.all(calls.map(async c => {
      let args = {}; try { args = JSON.parse(c.arguments || '{}'); } catch (e) { /* để trống */ }
      return { type: 'function_call_output', call_id: c.call_id, output: JSON.stringify(await runTool(c.name, args, ctx, st)) };
    }));
  }
  return 'Trợ lý cần quá nhiều bước, hãy hỏi cụ thể hơn.';
}

// ─────────────── điểm vào ───────────────
module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  const send = (code, obj) => res.status(code).json(obj);
  if (req.method === 'GET') {   // app hỏi máy chủ đã có khóa nào
    return send(200, { server_keys: Object.fromEntries(Object.entries(ENV_KEY).map(([p, k]) => [p, !!process.env[k]])),
      need_pass: !!process.env.AI_PASS, models: DEFAULT_MODEL });
  }
  if (req.method !== 'POST') return send(405, { error: 'Chỉ nhận POST' });
  let b = req.body;
  if (typeof b === 'string') { try { b = JSON.parse(b); } catch (e) { b = null; } }
  if (!b || typeof b !== 'object') return send(400, { error: 'Dữ liệu gửi lên không hợp lệ' });
  const provider = DEFAULT_MODEL[b.provider] ? b.provider : 'gemini';
  const model = (typeof b.model === 'string' && /^[\w.\-:/]{2,80}$/.test(b.model)) ? b.model : DEFAULT_MODEL[provider];
  const msgs = (Array.isArray(b.messages) ? b.messages : []).filter(m => m && typeof m.text === 'string' && m.text.trim())
    .slice(-12).map(m => ({ role: m.role === 'assistant' ? 'assistant' : 'user', text: m.text.slice(0, 4000) }));
  while (msgs.length && msgs[0].role !== 'user') msgs.shift();
  if (!msgs.length || msgs[msgs.length - 1].role !== 'user') return send(400, { error: 'Thiếu câu hỏi' });

  let key = String(req.headers['x-ai-key'] || '').trim();
  if (!key) {
    if (process.env.AI_PASS && req.headers['x-app-pass'] !== process.env.AI_PASS) return send(401, { error: 'Sai hoặc thiếu mật khẩu trợ lý AI (cài đặt trong tab AI).' });
    key = process.env[ENV_KEY[provider]] || '';
  }
  if (!key) return send(400, { error: `Chưa có khóa API ${provider}. Nhập khóa trong phần Cài đặt của tab AI, hoặc đặt biến ${ENV_KEY[provider]} trên Vercel.` });

  const ctx = (b.context && typeof b.context === 'object') ? b.context : {};
  const st = { marks: [], sources: [] };
  try {
    const run = provider === 'claude' ? runClaude : provider === 'openai' ? runOpenAI : runGemini;
    const text = await run(key, model, systemPrompt(ctx), msgs, ctx, st);
    const seen = new Set();
    const sources = st.sources.filter(s => s.url && !seen.has(s.url) && seen.add(s.url)).slice(0, 8);
    return send(200, { text: text || '(không có nội dung)', marks: st.marks, sources, provider, model });
  } catch (e) {
    const s = e.status;
    const msg = s === 401 || s === 403 ? 'Khóa API không đúng hoặc không có quyền.' : s === 429 ? 'Hết hạn mức hoặc gọi quá nhanh, thử lại sau ít phút.'
      : s === 404 ? `Không có mô hình "${model}". Đổi mô hình trong Cài đặt.` : e.name === 'AbortError' ? 'AI trả lời quá lâu, thử lại.' : 'Lỗi gọi AI: ' + e.message;
    return send(502, { error: msg });
  }
};
module.exports.toolTide = toolTide;
module.exports.toolPlaces = toolPlaces;
module.exports.TOOLS = TOOLS;
