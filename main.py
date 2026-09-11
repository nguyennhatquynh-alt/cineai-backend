import os
import time
import json
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MovieRequest(BaseModel):
    gemini_key: str
    title: str
    story: str
    aspect_ratio: str = "16:9"
    style: str = "Cinematic 3D Epic Biography"
    mood: str = "Êm đềm, hoài niệm, sâu lắng"
    shots_count: int = 6
    duration: int = 30

@app.get("/")
def home():
    return {"status": "CineAI Backend Master Epic is running smoothly with 11 Locks!"}

@app.post("/api/generate-movie")
def generate_movie(req: MovieRequest):
    try:
        # Cấu hình API Key cho Gemini
        api_key = req.gemini_key or os.environ.get("GEMINI_API_KEY", "AIzaSyAXkRSS1n_dREtWtSFJ9ga7xKKIeMMQZa8")
        genai.configure(api_key=api_key)

        prompt = f"""
        Bạn là một Đạo diễn điện ảnh và Biên kịch trưởng xuất sắc. Hãy phân rã câu chuyện sau thành một kịch bản phim dài tuân thủ tuyệt đối '11 Chốt Khóa Đạo Diễn' (Khóa nhân vật, địa điểm, phục trang, màu sắc, âm thanh, giọng nói và 5 khóa cấu trúc kịch bản).
        
        Tên dự án: {req.title}
        Nội dung cốt truyện: {req.story}
        Phong cách mỹ thuật: {req.style}
        Tâm trạng/Gam màu: {req.mood}
        Số lượng phân cảnh (Shots): {req.shots_count}
        Thời lượng: {req.duration} giây
        Tỷ lệ khung hình: {req.aspect_ratio}

        Hãy trả về kết quả DUY NHẤT dưới định dạng JSON chuẩn (không kèm markdown rườm rà) với cấu trúc như sau:
        {{
          "char": "Mô tả DNA nhân vật và khóa giọng nói xuyên suốt",
          "shots": [
            {{
              "shot": 1,
              "act": "HỒI 1: KHỞI ĐẦU",
              "time": "00:00 - 00:05",
              "cam": "Wide cinematic tracking shot",
              "lighting": "Golden hour warm tones, soft volumetric light",
              "motion": "Slow gentle pan right",
              "dialogue": "Câu thoại tiếng Việt có chiều sâu cảm xúc",
              "sfx": "Tiếng gió nhẹ, âm thanh môi trường hoài niệm",
              "img": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=800"
            }}
          ]
        }}
        """

        response = None
        last_error = None

        # --- CƠ CHẾ CHỌN TRƯỢT TỰ ĐỘNG & TĂNG TIMEOUT ---
        models_to_try = ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-pro']
        
        for model_name in models_to_try:
            try:
                print(f"Đang thử kết nối với model: {model_name}...")
                model = genai.GenerativeModel(model_name)
                
                # Tăng giới hạn timeout lên 120 giây
                response = model.generate_content(
                    prompt,
                    request_options={"timeout": 120.0}
                )
                if response and response.text:
                    break 
            except Exception as e:
                last_error = str(e)
                print(f"Model {model_name} thất bại: {last_error}. Đang chuyển trượt (fallback)...")
                time.sleep(1)

        if not response or not response.text:
            raise HTTPException(status_code=500, detail=f"Tất cả các mô hình Gemini đều phản hồi chậm hoặc lỗi Timeout. Chi tiết: {last_error}")

        # Xử lý chuỗi JSON trả về từ AI an toàn chống lỗi cú pháp
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

        try:
            data_json = json.loads(raw_text)
        except json.JSONDecodeError as jde:
            print(f"Lỗi cú pháp JSON thuần, đang tự động làm sạch: {jde}")
            cleaned_text = re.sub(r',\s*([\]}])', r'\1', raw_text)
            try:
                data_json = json.loads(cleaned_text)
            except Exception as e2:
                print(f"Không thể parse JSON, dùng dữ liệu dự phòng: {e2}")
                data_json = {
                    "char": "Cinematic character arc default",
                    "shots": [
                        {
                            "shot": 1,
                            "act": "HỒI 1: KHỞI ĐẦU",
                            "time": "00:00 - 00:05",
                            "cam": "Wide cinematic tracking shot",
                            "lighting": "Golden hour warm tones",
                            "motion": "Slow gentle pan",
                            "dialogue": req.story[:100],
                            "sfx": "Tiếng gió thiên nhiên",
                            "img": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=800"
                        }
                    ]
                }

        return {
            "success": True,
            "data": data_json
        }

    except Exception as e:
        print(f"Lỗi Backend nghiêm trọng: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý hệ thống Backend: {str(e)}")
        
