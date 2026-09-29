// api/gmap.js — Vercel Function: mở link Google Maps rút gọn (maps.app.goo.gl…) và trả về tọa độ.
// Trình duyệt không tự theo được link rút gọn (bị chặn CORS) nên app gọi: /api/gmap?u=<link>
// Chỉ đi theo các tên miền của Google để không bị lợi dụng làm proxy.
const ALLOW = /^(maps\.app\.goo\.gl|goo\.gl|g\.co|consent\.google\.[a-z.]+|(www\.|maps\.)?google\.[a-z.]+)$/i;

function extract(v) {
  v = String(v || '');
  try { v = decodeURIComponent(v.replace(/\+/g, ' ')); } catch (e) {}
  const ok = (a, b) => isFinite(a) && isFinite(b) && Math.abs(a) <= 90 && Math.abs(b) <= 180 && !(a === 0 && b === 0);
  const pats = [
    /!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/,
    /[?&](?:q|query|ll|sll|destination|daddr|center)=(?:loc:)?\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)/,
    /\/(?:place|search|dir)\/(?:[^/@]*\/)?(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)/,
    /@(-?\d+\.\d+),\s*(-?\d+\.\d+)/,
  ];
  for (const re of pats) { const m = v.match(re); if (m && ok(+m[1], +m[2])) return [+m[1], +m[2]]; }
  return null;
}
function extractBody(html) {
  // ảnh bản đồ tĩnh: center=lat%2Clon ; trạng thái khởi tạo: [[[zoom,lon,lat]
  let m = html.match(/center=(-?\d+\.\d+)(?:%2C|,)(-?\d+\.\d+)/);
  if (m) return [+m[1], +m[2]];
  m = html.match(/APP_INITIALIZATION_STATE=\[\[\[[\d.]+,(-?\d+\.\d+),(-?\d+\.\d+)\]/);
  if (m) return [+m[2], +m[1]];
  return null;
}

module.exports = async (req, res) => {
  let url = String((req.query && req.query.u) || '').trim();
  const send = (code, obj) => {
    res.setHeader('Cache-Control', code === 200 ? 'public, max-age=86400' : 'no-store');
    res.status(code).json(obj);
  };
  if (!url) return send(400, { error: 'thiếu tham số u' });
  try {
    for (let hop = 0; hop < 8; hop++) {
      const u = new URL(url);
      if (!/^https?:$/.test(u.protocol) || !ALLOW.test(u.hostname)) return send(400, { error: 'chỉ nhận link Google Maps' });
      const ll = extract(url);
      if (ll) return send(200, { lat: ll[0], lon: ll[1], url });
      const r = await fetch(url, {
        redirect: 'manual',
        headers: { 'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36', 'Accept-Language': 'vi,en;q=0.8' },
      });
      const loc = r.headers.get('location');
      if (r.status >= 300 && r.status < 400 && loc) { url = new URL(loc, url).href; continue; }
      const body = (await r.text()).slice(0, 800000);
      const ll2 = extractBody(body);
      return ll2 ? send(200, { lat: ll2[0], lon: ll2[1], url }) : send(404, { error: 'không thấy tọa độ', url });
    }
    return send(404, { error: 'quá nhiều chuyển hướng' });
  } catch (e) {
    return send(502, { error: 'không mở được link' });
  }
};
module.exports.extract = extract;
module.exports.extractBody = extractBody;
