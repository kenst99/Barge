# Barge

## Trợ lý AI (tab 🤖 AI trên bản đồ)

Hàm máy chủ `api/ai.js` gọi Gemini, Claude hoặc GPT. AI dùng các công cụ: tìm cây xăng / chỗ sửa tàu / cảng thật trên OpenStreetMap (dọc tuyến hoặc quanh một điểm), tìm tọa độ địa danh, thời tiết và sóng (Open-Meteo), con nước, tìm web (giá dầu, giá cát), ghim kết quả lên bản đồ.

Khóa API — đặt trong Vercel → Project → Settings → Environment Variables (đặt bao nhiêu hãng cũng được), rồi triển khai lại:

| Biến | Hãng |
|---|---|
| `GEMINI_API_KEY` | Google Gemini (aistudio.google.com/apikey) |
| `ANTHROPIC_API_KEY` | Anthropic Claude (console.anthropic.com) |
| `OPENAI_API_KEY` | OpenAI GPT (platform.openai.com) |
| `AI_PASS` (tùy chọn) | Mật khẩu để người lạ không dùng được khóa của máy chủ; nhập cùng mật khẩu trong ⚙️ của tab AI |

Không muốn đặt trên Vercel thì mỗi máy tự nhập khóa trong ⚙️ của tab AI (lưu trên máy đó, không nằm trong file Xuất dữ liệu).
