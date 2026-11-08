// api/ocr.js — Vercel Function: đọc ảnh báo cáo chuyến viết tay của tài công (OCR bằng AI có thị giác).
// App gửi: POST /api/ocr {provider, model?, image:{data:<base64 không có tiền tố>, type:'image/jpeg'}, known:{stations:[], routes:[], barges:[]}}
// Trả về:  {trips:[{date, barge, route, cargo, total_written, items:[{name, known_station, amount, kind, unsure}], notes, warnings}], provider, model}
// Khóa API giống api/ai.js: header x-ai-key, hoặc biến môi trường GEMINI_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY (+ AI_PASS nếu có).
// Mỗi lần gửi một ảnh (ảnh đã được app thu nhỏ còn ~1800 px) để không vượt giới hạn 4,5 MB của Vercel.

const DEFAULT_MODEL = { gemini: 'gemini-3.8-flash', claude: 'claude-opus-5-5', openai: 'gpt-5.5' };
const ENV_KEY = { gemini: 'GEMINI_API_KEY', claude: 'ANTHROPIC_API_KEY', openai: 'OPENAI_API_KEY' };

const ITEM = {
  type: 'object',
  properties: {
    name: { type: 'string', description: 'Tên khoản chi đúng như chữ trong sổ (sửa lỗi chính tả rõ ràng)' },
    known_station: { type: 'string', description: 'Tên trạm trong danh sách trạm đã biết nếu chắc chắn là cùng một trạm, không thì rỗng' },
    amount: { type: 'integer', description: 'Số tiền đầy đủ bằng đồng (VD 500.000 → 500000; cột ghi tắt 500 khi tổng là 10.500.000 → 500000)' },
    kind: { type: 'string', enum: ['station', 'other'], description: 'station = trạm, cảng vụ, biên phòng, thanh tra, đội…; other = bồi dưỡng, tài công, vét, phạt, dầu, xe, đò…' },
    unsure: { type: 'boolean', description: 'true nếu chữ hoặc số đọc không chắc' },
  },
  required: ['name', 'known_station', 'amount', 'kind', 'unsure'],
  additionalProperties: false,
};
const SCHEMA = {
  type: 'object',
  properties: {
    trips: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          date: { type: 'string', description: 'Ngày nhận hàng / ngày chi, dạng YYYY-MM-DD; năm 2 chữ số 26 → 2026; không có thì rỗng' },
          barge: { type: 'string', description: 'Số hiệu tàu, VD ST-06128; không có thì rỗng' },
          route: { type: 'string', description: 'Tuyến chở hàng dạng "Hàng Nơi nhận → Nơi giao", VD "Đá Vũng Tàu → Vĩnh Thạnh"' },
          cargo: { type: 'string', description: 'Hàng, khối lượng (VD "Gạch, 485 kiện", "Đá 1x2, 996 tấn")' },
          total_written: { type: 'integer', description: 'Tổng tiền ghi trong sổ bằng đồng, 0 nếu không có' },
          items: { type: 'array', items: ITEM },
          notes: { type: 'string', description: 'Giờ chạy, bơm dầu (lít), tiền ứng / chuyển khoản, thiếu lại… gọn trong vài dòng' },
          warnings: { type: 'string', description: 'Chỗ khó đọc, tổng không khớp, trang bị cắt… rỗng nếu không có' },
        },
        required: ['date', 'barge', 'route', 'cargo', 'total_written', 'items', 'notes', 'warnings'],
        additionalProperties: false,
      },
    },
  },
  required: ['trips'],
  additionalProperties: false,
};

function prompt(known) {
  const k = known && typeof known === 'object' ? known : {};
  const list = (a, n) => (Array.isArray(a) ? a : []).map(x => String(x).slice(0, 80)).slice(0, n);
  return [
    'Đây là ảnh một trang sổ tay viết tay (tiếng Việt) của tài công sà lan, ghi các khoản chi khi chạy một chuyến chở hàng: tiền "qua trạm" (trạm CSGT đường thủy, cảng vụ, biên phòng, thanh tra, đội…), bồi dưỡng cập/cẩu, tài công, vét, phạt…',
    'Đọc kỹ từng dòng và trả về JSON đúng lược đồ. Quy tắc:',
    '- Mỗi dòng có số tiền là một mục trong items, giữ thứ tự từ trên xuống. Không đưa dòng tổng, dòng "ứng", dòng chuyển khoản, dòng trừ vào items.',
    '- Số tiền đổi ra đồng đầy đủ. Sổ hay ghi tắt nghìn đồng (500 = 500.000); dựa vào dòng tổng để biết. Dấu chấm là phân cách nghìn.',
    '- Cộng lại các mục và so với tổng ghi trong sổ; nếu lệch, ghi vào warnings và đánh dấu unsure cho dòng nghi ngờ.',
    '- kind = station cho trạm, cảng vụ, biên phòng, thanh tra, đội, "363", "Cục", "Phòng", "Tàu" (trạm), "Kinh Nước Mặn"…; kind = other cho bồi dưỡng, tài công, vét đá, phạt, đò, xe, dầu, phí cảng, bến cảng…',
    '- known_station: chỉ điền khi chắc chắn mục này là một trạm trong danh sách dưới đây (chép đúng tên trong danh sách); không chắc thì để rỗng.',
    '- Một trang có thể có hơn một chuyến (nhiều tiêu đề tuyến) → nhiều phần tử trong trips. Trang chỉ có giờ chạy, không có tiền, vẫn trả một chuyến với items rỗng.',
    '- Không bịa: chữ nào không đọc được thì ghi gần đúng nhất và đánh unsure = true.',
    '',
    'Trạm đã biết: ' + (list(k.stations, 160).join(' | ') || '(chưa có)'),
    'Tuyến đã có trong nhật ký: ' + (list(k.routes, 40).join(' | ') || '(chưa có)'),
    'Số hiệu tàu: ' + (list(k.barges, 10).join(', ') || 'ST-06128, ST-06413, ST-06369'),
  ].join('\n');
}

async function getJSON(url, opt, ms) {
  const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms || 110000);
  try {
    const r = await fetch(url, Object.assign({ signal: ctl.signal }, opt));
    const txt = await r.text(); let j = null;
    try { j = JSON.parse(txt); } catch (e) { /* để trống */ }
    if (!r.ok) { const e = new Error((j && j.error && (j.error.message || j.error)) || txt.slice(0, 300) || ('HTTP ' + r.status)); e.status = r.status; throw e; }
    return j;
  } finally { clearTimeout(t); }
}
function parseJSON(s) {
  s = String(s || '').trim().replace(/^```(?:json)?\s*/i, '').replace(/```\s*$/, '');
  try { return JSON.parse(s); } catch (e) { const m = s.match(/\{[\s\S]*\}/); if (m) return JSON.parse(m[0]); throw new Error('AI không trả về JSON hợp lệ'); }
}

async function ocrClaude(key, model, img, text) {
  // Claude: ảnh base64 + structured outputs (output_config.format) để chắc chắn JSON đúng lược đồ.
  // Bật dự phòng phía máy chủ (fallbacks "default") khi bộ lọc an toàn từ chối.
  const j = await getJSON('https://api.anthropic.com/v1/messages', { method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-api-key': key, 'anthropic-version': '2023-06-01', 'anthropic-beta': 'server-side-fallback-2026-07-01' },
    body: JSON.stringify({ model, max_tokens: 16000, fallbacks: 'default',
      output_config: { effort: 'medium', format: { type: 'json_schema', schema: SCHEMA } },
      messages: [{ role: 'user', content: [
        { type: 'image', source: { type: 'base64', media_type: img.type, data: img.data } },
        { type: 'text', text } ] }] }) });
  if (j.stop_reason === 'refusal') throw new Error('Claude từ chối đọc ảnh này');
  if (j.stop_reason === 'max_tokens') throw new Error('Ảnh quá nhiều chữ, AI trả lời bị cắt – chụp từng trang');
  return parseJSON((j.content || []).filter(b => b.type === 'text').map(b => b.text).join(''));
}
async function ocrGemini(key, model, img, text) {
  const j = await getJSON(`https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`, { method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-goog-api-key': key },
    body: JSON.stringify({
      contents: [{ role: 'user', parts: [{ inline_data: { mime_type: img.type, data: img.data } },
        { text: text + '\n\nLược đồ JSON phải theo:\n' + JSON.stringify(SCHEMA) }] }],
      generationConfig: { responseMimeType: 'application/json', thinkingConfig: { thinkingLevel: 'medium' } } }) });
  const c = j.candidates && j.candidates[0];
  if (!c || !c.content) throw new Error('Gemini không đọc được ảnh');
  return parseJSON((c.content.parts || []).filter(p => p.text && !p.thought).map(p => p.text).join(''));
}
async function ocrOpenAI(key, model, img, text) {
  const j = await getJSON('https://api.openai.com/v1/responses', { method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + key },
    body: JSON.stringify({ model, reasoning: { effort: 'medium' },
      input: [{ role: 'user', content: [{ type: 'input_text', text }, { type: 'input_image', image_url: `data:${img.type};base64,${img.data}` }] }],
      text: { format: { type: 'json_schema', name: 'bao_cao_chuyen', schema: SCHEMA, strict: true } } }) });
  let out = '';
  (j.output || []).forEach(o => { if (o.type === 'message') (o.content || []).forEach(c => { if (c.type === 'output_text') out += c.text; if (c.type === 'refusal') throw new Error('GPT từ chối: ' + c.refusal); }); });
  return parseJSON(out);
}

// làm sạch kết quả AI trước khi trả về app
function clean(o) {
  const s = (v, n) => String(v == null ? '' : v).slice(0, n || 200).trim();
  const int = v => { const x = typeof v === 'number' ? Math.round(v) : Number(String(v).replace(/\D/g, '')); return isFinite(x) && x > 0 ? x : 0; };
  const trips = (o && Array.isArray(o.trips) ? o.trips : []).slice(0, 6).map(t => ({
    date: /^\d{4}-\d{2}-\d{2}$/.test(s(t.date)) ? s(t.date) : '',
    barge: s(t.barge, 20), route: s(t.route, 120), cargo: s(t.cargo, 120), total_written: int(t.total_written),
    items: (Array.isArray(t.items) ? t.items : []).slice(0, 60).map(i => ({ name: s(i.name, 80), known_station: s(i.known_station, 80),
      amount: int(i.amount), kind: i.kind === 'station' ? 'station' : 'other', unsure: !!i.unsure })).filter(i => i.name || i.amount),
    notes: s(t.notes, 1200), warnings: s(t.warnings, 600),
  }));
  return { trips };
}

module.exports = async (req, res) => {
  res.setHeader('Cache-Control', 'no-store');
  const send = (code, obj) => res.status(code).json(obj);
  if (req.method !== 'POST') return send(405, { error: 'Chỉ nhận POST' });
  let b = req.body;
  if (typeof b === 'string') { try { b = JSON.parse(b); } catch (e) { b = null; } }
  if (!b || typeof b !== 'object') return send(400, { error: 'Dữ liệu gửi lên không hợp lệ' });
  const provider = DEFAULT_MODEL[b.provider] ? b.provider : 'gemini';
  const model = (typeof b.model === 'string' && /^[\w.\-:/]{2,80}$/.test(b.model)) ? b.model : DEFAULT_MODEL[provider];
  const img = b.image || {};
  const type = /^image\/(jpeg|png|webp)$/.test(img.type) ? img.type : 'image/jpeg';
  const data = typeof img.data === 'string' ? img.data.replace(/^data:[^,]+,/, '') : '';
  if (!data || data.length < 1000) return send(400, { error: 'Thiếu ảnh' });
  if (data.length > 4200000) return send(413, { error: 'Ảnh quá lớn – chụp lại gần hơn hoặc chọn ảnh nhỏ hơn' });

  let key = String(req.headers['x-ai-key'] || '').trim();
  if (!key) {
    if (process.env.AI_PASS && req.headers['x-app-pass'] !== process.env.AI_PASS) return send(401, { error: 'Sai hoặc thiếu mật khẩu trợ lý AI (cài đặt trong bảng Trợ lý AI).' });
    key = process.env[ENV_KEY[provider]] || '';
  }
  if (!key) return send(400, { error: `Chưa có khóa API ${provider}. Nhập khóa trong ⚙️ của Trợ lý AI, hoặc đặt biến ${ENV_KEY[provider]} trên Vercel.` });

  try {
    const run = provider === 'claude' ? ocrClaude : provider === 'openai' ? ocrOpenAI : ocrGemini;
    const out = clean(await run(key, model, { type, data }, prompt(b.known)));
    return send(200, Object.assign(out, { provider, model }));
  } catch (e) {
    const st = e.status;
    const msg = st === 401 || st === 403 ? 'Khóa API không đúng hoặc không có quyền.' : st === 429 ? 'Hết hạn mức hoặc gọi quá nhanh, thử lại sau ít phút.'
      : st === 404 ? `Không có mô hình "${model}". Đổi mô hình trong ⚙️ Trợ lý AI.` : e.name === 'AbortError' ? 'AI đọc ảnh quá lâu, thử lại.' : 'Lỗi đọc ảnh: ' + e.message;
    return send(502, { error: msg });
  }
};
module.exports.SCHEMA = SCHEMA;
module.exports.clean = clean;
module.exports.prompt = prompt;
