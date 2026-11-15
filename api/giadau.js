// api/giadau.js — Vercel Function: lấy giá dầu DO 0,05S của Petrolimex, MỨC 2 (vùng 2), từ https://giaxanghomnay.com
// để app ước tính chi phí tuyến. Trình duyệt không đọc thẳng trang đó được (CORS) nên app gọi /api/giadau.
// Chỉ tải đúng địa chỉ cố định bên dưới. ?debug=1 trả thêm đoạn chữ quanh dòng giá để kiểm tra khi trang đổi giao diện.
const SOURCES = ['https://giaxanghomnay.com/', 'https://www.giaxanghomnay.com/'];

const toText = html => String(html || '').replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/gi, ' ')
  .replace(/<\/(td|th)>/gi, ' | ').replace(/<\/tr>/gi, ' \n ').replace(/<[^>]+>/g, ' ')
  .replace(/&nbsp;/gi, ' ').replace(/&#273;|&#x111;/gi, 'đ').replace(/[ \t]+/g, ' ');
const PRICE = /\d{2}[.,]\d{3}(?![\d.,]*\d{3})/g;          // 18.560 / 18,560 (không lấy số dài hơn)

// Bảng Petrolimex: "Dầu DO 0,05S-II | 18.560 | 18.930" → mức 1 = 18.560, mức 2 = 18.930.
// Trang có nhiều hãng (Petrolimex, PVOIL…): ưu tiên dòng DO 0,05S nằm trong khối có chữ Petrolimex.
function parse(html) {
  const text = toText(html);
  const rows = [];
  const re = /D[ầa]u\s*DO\s*0[,.]05\s*S(?:\s*-\s*[IV]+)?|DO\s*0[,.]05\s*S(?:\s*-\s*[IV]+)?/gi;
  let m;
  while ((m = re.exec(text))) {
    const tail = text.slice(m.index + m[0].length, m.index + m[0].length + 120).split('\n')[0];
    const nums = (tail.match(PRICE) || []).map(x => Number(x.replace(/[.,]/g, ''))).filter(v => v >= 8000 && v <= 60000);
    if (!nums.length) continue;
    const before = text.slice(Math.max(0, m.index - 3000), m.index);
    const brands = [...before.matchAll(/Petrolimex|PVOIL|PV\s*Oil|Mipec|Saigon\s*Petro|Comeco/gi)];
    const brand = brands.length ? brands[brands.length - 1][0] : '';
    rows.push({ name: m[0].replace(/\s+/g, ' ').trim(), m1: nums[0], m2: nums[1] || null, brand, at: m.index });
  }
  if (!rows.length) return null;
  const r = rows.find(x => /petrolimex/i.test(x.brand) && x.m2) || rows.find(x => x.m2) || rows[0];
  return { name: r.name, price: r.m2 || r.m1, m1: r.m1, m2: r.m2, level: r.m2 ? 2 : 1, brand: r.brand || 'Petrolimex', _at: r.at, _text: text };
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
        const out = { ok: true, price: hit.price, level: hit.level, m1: hit.m1, m2: hit.m2, name: `${hit.name} (${hit.brand}, mức ${hit.level})`, src: url, at: Date.now() };
        if (debug) out.debug = hit._text.slice(Math.max(0, hit._at - 400), hit._at + 300);
        return res.status(200).json(out);
      }
      last = 'không tìm thấy dòng dầu DO 0,05S';
      if (debug) return res.status(502).json({ ok: false, error: last, debug: toText(html).slice(0, 4000) });
    } catch (e) { last = e.name === 'AbortError' ? 'quá thời gian chờ' : String(e.message || e); }
  }
  res.status(502).json({ ok: false, error: 'Chưa lấy được giá dầu từ giaxanghomnay.com (' + last + '). Nhập tay giá dầu trong app.' });
};
module.exports.parse = parse;
