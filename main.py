import os
import json
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="CineAI Pro Optimized Backend with TTS")

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
    voice_id: str = "21m00Tcm4TlvDq8ikWAM" # Giọng mẫu chuẩn mặc định của ElevenLabs (Rachel)

@app.get("/")
def home():
    return {"status": "ok", "message": "CineAI Pro Backend with TTS is live!"}

@app.post("/api/generate-movie")
def generate_movie(req: MovieRequest):
    try:
        prompt = f"""You are a Hollywood Film Director and Master DP.
Transform the raw idea into a professional {req.shots_count}-shot 3-Act Cinematic Storyboard ({req.duration}s).
Title: "{req.title}". Aspect Ratio: {req.aspect_ratio}. Style: "{req.style}". Mood: "{req.mood}". Story: "{req.story}".

STRICT DIRECTIVE: Return ONLY a valid raw JSON object starting with {{ and ending with }}, without any conversational preamble, intro text, or markdown code blocks:
{{
  "char": "detailed character look and texture in English",
  "shots": [
    {{
      "shot": 1,
      "act": "Hồi 1",
      "time": "00:00-00:05",
      "cam": "dynamic tracking shot",
      "lighting": "35mm anamorphic cinematic lighting",
      "action": "cinematic action prompt under 25 words",
      "motion": "fast aerodynamic blur motion",
      "dialogue": "Vietnamese dialogue",
      "sfx": "sub-bass impact sound"
    }}
  ]
}}"""

        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={req.gemini_key}"
        payload = {
            "contents": [{ "parts": [{ "text": prompt }] }]
        }
        
        resp = requests.post(gemini_url, json=payload, timeout=60)
        resp_data = resp.json()
        
        if "error" in resp_data:
            raise HTTPException(status_code=400, detail=resp_data["error"].get("message", "Gemini API Error"))
            
        raw_text = resp_data["candidates"][0]["content"]["parts"][0]["text"].strip()
        
        clean_text = raw_text.replace("```json", "").replace("```", "").strip()
        first_brace = clean_text.find('{')
        last_brace = clean_text.rfind('}')
        if first_brace != -1 and last_brace != -1:
            clean_text = clean_text[first_brace:last_brace+1]
            
        parsed_json = json.loads(clean_text)
        
        width = 1024 if req.aspect_ratio == "16:9" else 576
        height = 576 if req.aspect_ratio == "16:9" else 1024
        
        for i, s in enumerate(parsed_json.get("shots", [])):
            scene_prompt = f"{req.style}, {parsed_json.get('char', '')}, {s.get('action', '')}, {s.get('cam', '')}, {s.get('lighting', '')}"
            encoded_prompt = requests.utils.quote(scene_prompt)
            s["img"] = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true&seed={1000 + i}"

        return {
            "success": True,
            "data": parsed_json
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generate-tts")
def generate_tts(req: TTSRequest):
    try:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{req.voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": req.eleven_labs_key
        }
        data = {
            "text": req.text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }
        
        response = requests.post(url, json=data, headers=headers, timeout=30)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="ElevenLabs API Error: " + response.text)
            
        # Trả về dạng stream hoặc base64 để frontend phát âm thanh
        import base64
        audio_base64 = base64.b64encode(response.content).decode("utf-8")
        return {"success": True, "audio_base64": audio_base64}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
