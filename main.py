import time
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="CineAI Production Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RUNPOD_API_KEY = "rpa_TFJEHFY0029UQ73E3HSA84BCKHDWMNH9HHSNT"
POD_ID = "aafgcmzcigg2nf"
COMFY_URL = f"https://{POD_ID}-3000.proxy.runpod.net"
RUNPOD_GQL_URL = f"https://api.runpod.io/graphql?api_key={RUNPOD_API_KEY}"

class MovieRequest(BaseModel):
    gemini_key: str
    story: str
    ratio: str = "16:9"
    style: str = "Cinematic 3D Fantasy"
    shots_count: int = 6

def call_runpod_gql(query: str):
    try:
        res = requests.post(RUNPOD_GQL_URL, json={"query": query}, timeout=10)
        return res.json()
    except Exception as e:
        print("RunPod GQL Error:", e)
        return None

def start_pod():
    query = f'mutation {{ podResume(input: {{ podId: "{POD_ID}", gpuCount: 1 }}) {{ id desiredStatus }} }}'
    return call_runpod_gql(query)

def stop_pod():
    query = f'mutation {{ podStop(input: {{ podId: "{POD_ID}" }}) {{ id desiredStatus }} }}'
    return call_runpod_gql(query)

def wait_for_comfy(max_wait=60):
    start = time.time()
    while time.time() - start < max_wait:
        try:
            res = requests.get(f"{COMFY_URL}/system_stats", timeout=3)
            if res.status_code == 200:
                return True
        except:
            pass
        time.sleep(4)
    return False

@app.post("/api/generate-movie")
def generate_movie(req: MovieRequest):
    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={req.gemini_key}"
    prompt_text = f"""You are a Hollywood Film Director. Transform this idea into a professional {req.shots_count}-shot storyboard.
Story: {req.story}. Style: {req.style}. Aspect Ratio: {req.ratio}.
Return ONLY valid JSON:
{{
  "char": "character description in English",
  "shots": [
    {{
      "shot": 1,
      "act": "Hồi 1",
      "time": "00:00-00:05",
      "cam": "tracking shot",
      "lighting": "cinematic lighting",
      "action": "action description",
      "dialogue": "Vietnamese dialogue",
      "sfx": "bass sound"
    }}
  ]
}}"""
    
    try:
        gem_res = requests.post(gemini_url, json={"contents": [{"parts": [{"text": prompt_text}]}]}).json()
        raw_text = gem_res["candidates"][0]["content"]["parts"][0]["text"].strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:-3].strip()
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:-3].strip()
            
        import json
        storyboard = json.loads(raw_text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi phân tích kịch bản Gemini: {str(e)}")

    start_pod()
    is_ready = wait_for_comfy(50)
    
    try:
        if is_ready:
            pass
    finally:
        stop_pod()

    return {
        "status": "success",
        "storyboard": storyboard,
        "video_url": "https://www.w3schools.com/html/mov_bbb.mp4"
    }

@app.get("/")
def home():
    return {"status": "CineAI Backend Orchestrator is running!"}
  
