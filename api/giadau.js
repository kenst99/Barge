// api/giadau.js — Vercel Function: lấy giá dầu DO (diesel) hôm nay từ trang giaxanghomnay để app ước tính chi phí tuyến.
// Trình duyệt không đọc thẳng trang đó được (CORS) nên app gọi /api/giadau. Chỉ tải đúng các địa chỉ cố định bên dưới.
const SOURCES = ['https://giaxanghomnay.com/', 'https://www.giaxanghomnay.com/', 'https://giaxanghomnay.vn/'];

// Tìm dòng dầu diesel trong HTML: "DO 0,05S", "Dầu DO 0,001S-V", "Diesel"… rồi lấy số tiền đầu tiên sau nó (đ/lít)
function parse(html) {
  const text = String(html || '').replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ').replace(/&nbsp;/gi, ' ').replace(/\s+/g, ' ');
  const out = [];
  const re = /(D[ầa]u\s+)?(DO\s*0[,.]0?\d+\s*S(?:\s*-\s*[IV]+)?|Diesel(?:\s+0[,.]0?\d+\s*S)?(?:\s*-\s*[IV]+)?|D[ầa]u\s+diesel)/gi;
  let m;
  while ((m = re.exec(text))) {
    const tail = text.slice(m.index + m[0].length, m.index + m[0].length + 160);
    const nums = tail.match(/\d{2}[.,]\d{3}(?!\d)/g);       // 18.560 / 18,560
    if (!nums) continue;
    const price = Number(nums[0].replace(/[.,]/g, ''));
    if (price >= 8000 && price <= 60000) out.push({ name: m[0].replace(/\s+/g, ' ').trim(), price });
  }
  if (!out.length) return null;
  // ưu tiên DO 0,05S (loại sà lan hay dùng), không có thì lấy dòng diesel đầu tiên
  return out.find(o => /0[,.]05/.test(o.name)) || out[0];
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 's-maxage=1800, stale-while-revalidate=21600');
  let last = '';
  for (const url of SOURCES) {
    try {
      const ctl = new AbortController(), tm = setTimeout(() => ctl.abort(), 8000);
      const r = await fetch(url, { signal: ctl.signal, headers: { 'User-Agent': 'Mozilla/5.0 (compatible; salan-barge/1.0)', 'Accept-Language': 'vi' } });
      clearTimeout(tm);
      if (!r.ok) { last = 'HTTP ' + r.status; continue; }
      const hit = parse(await r.text());
      if (hit) return res.status(200).json({ ok: true, price: hit.price, name: hit.name, src: url, at: Date.now() });
      last = 'không tìm thấy dòng giá dầu DO';
    } catch (e) { last = e.name === 'AbortError' ? 'quá thời gian chờ' : String(e.message || e); }
  }
  res.status(502).json({ ok: false, error: 'Chưa lấy được giá dầu từ giaxanghomnay (' + last + '). Nhập tay giá dầu trong app.' });
};
module.exports.parse = parse;
