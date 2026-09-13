# ==========================================
# CINE AI STUDIO PRO 3.0 - MAIN.PY (PHẦN 1/2)
# ==========================================
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
import google.generativeai as genai
import os

app = FastAPI(title="Cine AI Studio Pro 3.0", version="14.8")

# Cấu hình API Key Gemini cho Đạo diễn ảo (Lấy từ biến môi trường trên Render)
# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Giao diện chính của Cine AI Studio Pro 3.0 tích hợp Tầng 7 & 8"""
    return """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Cine AI Studio Pro 3.0 - Không gian Sáng tạo Độc lập</title>
    <style>
        body { background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; }
        .cine-container { max-width: 1000px; margin: 0 auto; background: #1e1e1e; padding: 30px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }
        h1, h3 { color: #ffffff; border-bottom: 2px solid #333; padding-bottom: 10px; }
        .studio-section { margin-bottom: 25px; background: #252525; padding: 20px; border-radius: 8px; border: 1px solid #333; }
        label { display: block; margin-bottom: 8px; font-weight: 600; color: #b0bec5; }
        textarea { width: 100%; padding: 12px; background: #1a1a1a; color: #ffffff; border: 1px solid #444; border-radius: 6px; font-family: monospace; font-size: 14px; box-sizing: border-box; resize: vertical; }
        button { background: #007bff; color: white; border: none; padding: 12px 24px; border-radius: 6px; cursor: pointer; font-weight: bold; font-size: 14px; transition: background 0.2s; }
        button:hover { background: #0056b3; }
        .btn-save { background: #28a745; margin-left: 10px; }
        .btn-save:hover { background: #218838; }
        .status-bar { margin-top: 10px; font-style: italic; color: #ffc107; display: block; }
    </style>
</head>
<body>
    <div class="cine-container">
        <h1>🎬 CINE AI STUDIO PRO 3.0</h1>
        <p>Hệ thống Đạo diễn ảo & 16 Tầng Điện ảnh chuyên nghiệp (Độc lập & Bảo mật)</p>
        
        <!-- Khung Tầng 7 & 8: Tương tác thời gian thực & Chỉnh sửa thủ công -->
        <div class="studio-section">
            <h3>Tầng 7 & 8: Ý Tưởng Thô & Biên Kịch Ảo (Streaming & Manual Edit)</h3>
            
            <div style="margin-bottom: 15px;">
                <label>Tầng 7 - Nhập ý tưởng sơ khai hoặc cảm xúc thô:</label>
                <textarea id="rawIdeaInput" rows="3" placeholder="Ví dụ: Một chuyến tàu định mệnh xuyên không gian vào nửa đêm..."></textarea>
            </div>
            
            <button onclick="generateScriptStream()">⚡ Kích hoạt Đạo diễn Ảo (Stream)</button>
            <span id="streamStatus" class="status-bar"></span>
            
            <div style="margin-top: 20px;">
                <label>Tầng 8 - Kịch bản điện ảnh (Tự động stream & Cho phép chỉnh sửa thủ công trực tiếp):</label>
                <textarea id="editableScriptOutput" rows="14" placeholder="Kết quả kịch bản thô từ Đạo diễn ảo sẽ hiển thị tại đây theo thời gian thực... Bạn có thể tự do gọt giũa, sửa thoại bất cứ lúc nào."></textarea>
            </div>
            
            <div style="margin-top: 15px;">
                <button onclick="saveProjectChanges()" class="btn-save">💾 Lưu / Cập Nhật Dự Án (Supabase)</button>
            </div>
        </div>
    </div>

    <script>
    async function generateScriptStream() {
        const promptText = document.getElementById('rawIdeaInput').value.trim();
        const outputArea = document.getElementById('editableScriptOutput');
        const statusLabel = document.getElementById('streamStatus');
        
        if (!promptText) {
            alert("Vui lòng nhập ý tưởng thô ở Tầng 7 trước khi kích hoạt Đạo diễn ảo!");
            return;
        }
        
        outputArea.value = "";
        statusLabel.innerText = "Đạo diễn ảo đang kết nối và chấp bút...";
        
        try {
            const response = await fetch('/api/cineai/stream-script', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: promptText })
            });
            
            if (!response.ok) {
                throw new Error("Lỗi kết nối tới máy chủ Đạo diễn ảo.");
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            statusLabel.innerText = "Đang truyền tải luồng kịch bản (Streaming)...";
            
            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value, { stream: true });
                outputArea.value += chunk;
                outputArea.scrollTop = outputArea.scrollHeight;
            }
            
            statusLabel.innerText = "✅ Hoàn tất quá trình biên kịch thời gian thực!";
            
        } catch (error) {
            statusLabel.innerText = "❌ Xảy ra lỗi kết nối!";
            outputArea.value += "\\n\\n[Lỗi hệ thống: " + error.message + "]";
        }
    }

    function saveProjectChanges() {
        const finalContent = document.getElementById('editableScriptOutput').value.trim();
        if (!finalContent) {
            alert("Nội dung kịch bản đang trống, không thể thực hiện lưu dự án!");
            return;
        }
        alert("✅ Đã ghi nhận và sẵn sàng lưu đè phiên bản kịch bản tối ưu nhất lên cơ sở dữ liệu Supabase của dự án!");
    }
    </script>
</body>
</html>
    """
    # ==========================================
# CINE AI STUDIO PRO 3.0 - MAIN.PY (PHẦN 2/2)
# ==========================================

@app.post("/api/cineai/stream-script")
async def stream_script(data: dict):
    """Endpoint xử lý Tầng 7 & 8 trả về Streaming Response từ Gemini API"""
    user_prompt = data.get("prompt", "")
    if not user_prompt:
        raise HTTPException(status_code=400, detail="Prompt ý tưởng thô không được để trống")
    
    system_instruction = (
        "Bạn là Đạo diễn ảo chuyên nghiệp của hệ thống Cine AI Studio Pro 3.0. "
        "Hãy tiếp nhận ý tưởng thô từ Tầng 7 và chuyển hóa thành kịch bản phim ngắn "
        "chuẩn điện ảnh chi tiết, phân đoạn rõ ràng, thoại tự nhiên tại Tầng 8."
    )
    
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            system_instruction=system_instruction
        )
        
        response = model.generate_content(user_prompt, stream=True)
        
        def generate():
            for chunk in response:
                if chunk.text:
                    yield chunk.text
                    
        return StreamingResponse(generate(), media_type="text/plain")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
