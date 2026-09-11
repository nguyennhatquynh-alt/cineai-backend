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
    return {"status": "CineAI Secure Dynamic Backend is running!"}

@app.post("/api/generate-movie")
def generate_movie(req: MovieRequest):
    try:
        # Nhận khóa API cá nhân mới nhất do người dùng nhập trực tiếp từ giao diện
        api_key = req.gemini_key.strip()
        if not api_key:
            raise HTTPException(status_code=400, detail="Vui lòng nhập Gemini API Key của bạn ở phần cài đặt hoặc khung giao diện.")

        genai.configure(api_key=api_key)

        prompt = f"""
        Bạn là một Đạo diễn điện ảnh và Biên kịch trưởng xuất sắc. Hãy phân rã câu chuyện sau thành một kịch bản phim dài tuân thủ tuyệt đối '11 Chốt Khóa Đạo Diễn'.
        
        Tên dự án: {req.title}
        Nội dung cốt truyện: {req.story}
        Phong cách mỹ thuật: {req.style}
        Tâm trạng/Gam màu: {req.mood}
        Số lượng phân cảnh (Shots): {req.shots_count}
        Thời lượng: {req.duration} giây
        Tỷ lệ khung hình: {req.aspect_ratio}

        Hãy trả về kết quả DUY NHẤT dưới định dạng JSON chuẩn (không kèm markdown) với cấu trúc:
        {{
          "char": "Mô tả DNA nhân vật",
          "shots": [
            {{
              "shot": 1,
              "act": "HỒI 1: KHỞI ĐẦU",
              "time": "00:00 - 00:05",
              "cam": "Wide cinematic tracking shot",
              "lighting": "Golden hour warm tones",
              "motion": "Slow pan",
              "dialogue": "Câu thoại tiếng Việt sâu lắng",
              "sfx": "Tiếng gió thiên nhiên",
              "img": "https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=800"
            }}
          ]
        }}
        """

        response = None
        last_error = None
        models_matrix = ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-pro', 'gemini-2.5-flash']
        
        for model_name in models_matrix:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(prompt, request_options={"timeout": 120.0})
                if response and response.text:
                    break 
            except Exception as e:
                last_error = str(e)
                time.sleep(1)

        if not response or not response.text:
            raise HTTPException(status_code=500, detail=f"Lỗi kết nối AI: {last_error}")

        raw_text = response.text.strip()
        if raw_text.startswith("```json"): raw_text = raw_text[7:]
        if raw_text.endswith("```"): raw_text = raw_text[:-3]
        raw_text = raw_text.strip()

        try:
            data_json = json.loads(raw_text)
        except json.JSONDecodeError:
            cleaned_text = re.sub(r',\s*([\]}])', r'\1', raw_text)
            data_json = json.loads(cleaned_text)

        return {"success": True, "data": data_json}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
