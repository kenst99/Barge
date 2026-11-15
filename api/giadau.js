// api/giadau.js — Vercel Function: lấy giá dầu DO 0,05S Mức 2 của Petrolimex (giá vùng 1, kèm vùng 2) từ https://giaxanghomnay.com
// để app ước tính chi phí tuyến. Trình duyệt không đọc thẳng trang đó được (CORS) nên app gọi /api/giadau.
// Chỉ tải đúng địa chỉ cố định bên dưới. ?debug=1 trả thêm đoạn chữ quanh dòng giá để kiểm tra khi trang đổi giao diện.
const SOURCES = ['https://giaxanghomnay.com/', 'https://www.giaxanghomnay.com/'];

const toText = html => String(html || '').replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/gi, ' ')
  .replace(/\s+/g, ' ').replace(/<\/(td|th)>/gi, ' | ').replace(/<\/tr>/gi, ' ¶ ').replace(/<[^>]+>/g, ' ')
  .replace(/&nbsp;/gi, ' ').replace(/[ \t]+/g, ' ');
const num = c => { const m = String(c).match(/^\s*(\d{1,3}(?:[.,]\d{3})+)\s*$/); return m ? Number(m[1].replace(/[.,]/g, '')) : null; };

// Bảng Petrolimex trên giaxanghomnay.com (11/2026):
//   Xăng/dầu | Tăng giảm | Tăng giảm kỳ trước* | Giá vùng 1 | Giá vùng 2
//   DO 0,05S Mức 2 | 0 | -1,870 | 26,820 | 27,350
// Lấy dòng "DO 0,05S Mức 2" trong khối "giá theo Petrolimex"; cột lấy theo tiêu đề "Giá vùng 1 / 2".
function parse(html) {
  const text = toText(html);
  const i0 = text.search(/gi[áa] theo Petrolimex/i);
  const i1 = i0 >= 0 ? text.slice(i0 + 20).search(/gi[áa] theo (PVOIL|PV ?Oil|Mipec)/i) : -1;
  const block = i0 >= 0 ? text.slice(i0, i1 >= 0 ? i0 + 20 + i1 : undefined) : text;
  const rows = block.split('¶').map(r => r.split('|').map(c => c.trim()));
  const head = rows.find(r => r.some(c => /v[ùu]ng\s*1/i.test(c)));
  const c1 = head ? head.findIndex(c => /v[ùu]ng\s*1/i.test(c)) : -1, c2 = head ? head.findIndex(c => /v[ùu]ng\s*2/i.test(c)) : -1;
  const pick = re => rows.find(r => re.test(r[0]));
  const row = pick(/\bDO\s*0[,.]05\s*S\b.*M[ứu]c\s*2/i) || pick(/\bDO\s*0[,.]05\s*S\b/i);
  if (!row) return null;
  let v1 = c1 > 0 ? num(row[c1]) : null, v2 = c2 > 0 ? num(row[c2]) : null;
  if (v1 == null) {                                      // không đọc được tiêu đề: 2 số giá cuối dòng = vùng 1, vùng 2
    const ps = row.slice(1).map(num).filter(v => v && v >= 8000 && v <= 60000);
    v1 = ps.length >= 2 ? ps[ps.length - 2] : ps[0]; v2 = ps.length >= 2 ? ps[ps.length - 1] : null;
  }
  if (!v1 || v1 < 8000 || v1 > 60000) return null;
  const up = (block.match(/c[ậa]p nh[ậa]t\s*(\d{4}-\d{2}-\d{2}[ \d:]*)/i) || [])[1];
  return { name: row[0].replace(/\s+/g, ' '), price: v1, v1, v2, brand: i0 >= 0 ? 'Petrolimex' : '', updated: up ? up.trim() : '', _row: row.join(' | ') };
}

module.exports = async (req, res) => {
  const debug = req.query && req.query.debug;
  res.setHeader('Cache-Control', debug ? 'no-store' : 's-maxage=1800, stale-while-revalidate=21600');
  let last = '';
  for (const url of SOURCES) {
    try {
      const ctl = new AbortController(), tm = setTimeout(() => ctl.abort(), 9000);
      const r = await fetch(url, { signal: ctl.signal, headers: { 'User-Agent': 'Mozilla/5.0 (compatible; salan-barge/1.0)', 'Accept-Language': 'vi' } });
      clearTimeout(tm);
      if (!r.ok) { last = 'HTTP ' + r.status; continue; }
      const html = await r.text(), hit = parse(html);
      if (hit) {
        const out = { ok: true, price: hit.price, v1: hit.v1, v2: hit.v2, name: `${hit.name} · ${hit.brand || 'giaxanghomnay'} vùng 1`, updated: hit.updated, src: url, at: Date.now() };
        if (debug) out.debug = hit._row;
        return res.status(200).json(out);
      }
      last = 'không tìm thấy dòng DO 0,05S Mức 2';
      if (debug) return res.status(502).json({ ok: false, error: last, debug: toText(html).slice(0, 4000) });
    } catch (e) { last = e.name === 'AbortError' ? 'quá thời gian chờ' : String(e.message || e); }
  }
  res.status(502).json({ ok: false, error: 'Chưa lấy được giá dầu từ giaxanghomnay.com (' + last + '). Nhập tay giá dầu trong app.' });
};
module.exports.parse = parse;
