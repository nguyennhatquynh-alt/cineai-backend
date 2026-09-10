from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import requests
import json
import base64

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
    style: str = "Cinematic 3D Fantasy"
    mood: str = "Êm đềm, thơ mộng, chậm"
    shots_count: int = 6
    duration: int = 30

class TTSRequest(BaseModel):
    eleven_labs_key: str
    text: str
    @app.post("/api/generate-movie")
def generate_movie(req: MovieRequest):
    try:
        genai.configure(api_key=req.gemini_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = f"""
        Bạn là một đạo diễn điện ảnh Hollywood và là một nhà biên kịch xuất sắc. 
        Hãy tạo một kịch bản phân cảnh chi tiết cho câu chuyện sau: "{req.story}"
        Tên dự án: {req.title}
        Phong cách hình ảnh: {req.style}
        Tâm trạng/Nhịp điệu: {req.mood}
        Số lượng phân cảnh (shots): {req.shots_count}
        Định dạng khung hình: {req.aspect_ratio}

        Yêu cầu trả về DUY NHẤT một chuỗi JSON chuẩn (không kèm markdown thừa) theo cấu trúc sau:
        {{
          "char": "Mô tả nhân vật chính nhất quán xuất hiện xuyên suốt",
          "shots": [
            {{
              "shot": 1,
              "act": "Hồi 1",
              "time": "00:00 - 00:05",
              "cam": "Góc máy, tiêu cự ống kính",
              "lighting": "Ánh sáng, màu sắc",
              "motion": "Chuyển động máy quay",
              "dialogue": "Lời thoại hoặc lời dẫn truyện bằng tiếng Việt",
              "sfx": "Hiệu ứng âm thanh",
              "img": "Prompt tiếng Anh cực kỳ chi tiết bằng cú pháp cinematic photorealistic, 8k, để tạo ảnh qua Pollinations AI"
            }}
          ]
        }}
        """
        
        response = model.generate_content(prompt)
        raw_text = response.text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
        raw_text = raw_text.strip()
        
        data = json.loads(raw_text)
        
        # Tự động tạo link ảnh minh họa qua Pollinations AI dựa trên prompt của từng shot
        for s in data.get("shots", []):
            img_prompt = s.get("img", "cinematic landscape")
            encoded_prompt = requests.utils.quote(img_prompt + f", {req.style}, highly detailed 8k")
            width = 1024 if req.aspect_ratio == "16:9" else 576
            height = 576 if req.aspect_ratio == "16:9" else 1024
            s["img"] = f"https://pollinations.ai/p/{encoded_prompt}?width={width}&height={height}&nologo=true"

        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        @app.post("/api/generate-tts")
def generate_tts(req: TTSRequest):
    try:
        url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM" # Giọng Rachel mặc định chuẩn mượt
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": req.eleven_labs_key
        }
        payload = {
            "text": req.text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"ElevenLabs Error: {response.text}")
            
        audio_base64 = base64.b64encode(response.content).decode("utf-8")
        return {"status": "success", "audio_base64": audio_base64}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7860)
    
