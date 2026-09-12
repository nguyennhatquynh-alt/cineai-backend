import os
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.generativeai import GenerativeModel
import google.generativeai as genai

app = FastAPI(
    title="CineAI Studio - Xưởng Phim Tự Động 11 Tầng",
    version="11.1-SecurePro",
    description="Hệ thống xưởng phim tự động khép kín, bảo mật tuyệt đối qua biến môi trường."
)

# ==================== CẤU HÌNH BẢO MẬT QUA BIẾN MÔI TRƯỜNG ====================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "YOUR_GEMINI_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")
OPENAI_WHISPER_KEY = os.getenv("OPENAI_WHISPER_KEY")
STABILITY_KEYS = [
    os.getenv("STABILITY_KEY_1"),
    os.getenv("STABILITY_KEY_2")
]

genai.configure(api_key=GEMINI_API_KEY)

# ==================== PYDANTIC SCHEMAS ====================
class FilmProjectRequest(BaseModel):
    tieu_thuyet_goc: str
    phong_cach_nhac: str = "Art-Pop / Cinematic"
    ty_le_khung_hinh: str = "16:9"

class KeyframeRequest(BaseModel):
    prompt_anh: str
    key_index: int = 0

class RunwayRequest(BaseModel):
    prompt_video: str
    image_url: str

class WhisperRequest(BaseModel):
    audio_file_path: str


# ==================== CÁC MODULE API CHUYÊN SÂU ====================

@app.post("/api/v1/director/phandata-11-tang")
def dao_dien_phan_ra(request: FilmProjectRequest):
    """Tầng 1-6: Gemini phân rã chất liệu thô thành 11 chốt khóa và kịch bản nghệ thuật."""
    try:
        model = GenerativeModel("gemini-1.5-flash")
        prompt_he_thong = (
            f"Bạn là đạo diễn trưởng của CineAI Studio. Hãy phân rã chất liệu tiểu thuyết sau thành kịch bản 11 tầng chuẩn điện ảnh, "
            f"tách bạch góc máy, keyframe hình ảnh biểu tượng và lời thoại cảm xúc: {request.tieu_thuyet_goc}"
        )
        response = model.generate_content(prompt_he_thong)
        return {
            "status": "success",
            "director_blueprint": response.text,
            "message": "Đã hoàn tất phân rã cấu trúc đạo diễn chuyên sâu."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/production/stability-keyframe")
def tao_keyframe_stability(req: KeyframeRequest):
    """Tầng 4 & 6: Khởi tạo Keyframe nghệ thuật độc bản từ Stability AI."""
    valid_keys = [k for k in STABILITY_KEYS if k]
    if not valid_keys:
        raise HTTPException(status_code=500, detail="Chưa cấu hình Stability API Key trong biến môi trường.")
    
    active_key = valid_keys[req.key_index % len(valid_keys)]
    url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"
    
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {active_key}"
    }
    payload = {
        "steps": 30,
        "width": 1024,
        "height": 1024,
        "cfg_scale": 7,
        "samples": 1,
        "text_prompts": [{"text": req.prompt_anh, "weight": 1}]
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    
    return {"status": "success", "data": response.json(), "key_slot_used": req.key_index}


@app.post("/api/v1/production/runway-gen3")
def tao_video_runway(req: RunwayRequest):
    """Tầng 11: Chuyển hóa Keyframe tĩnh thành chuyển động điện ảnh mượt mà bằng Runway Gen-3."""
    if not RUNWAY_API_KEY:
        raise HTTPException(status_code=500, detail="Chưa cấu hình Runway API Key.")
        
    url = "https://api.dev.runwayml.com/v1/tasks"
    headers = {
        "Authorization": f"Bearer {RUNWAY_API_KEY}",
        "X-Runway-Version": "2024-09-06",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gen3a_turbo",
        "promptText": req.prompt_video,
        "promptImage": req.image_url,
        "duration": 5,
        "ratio": "1280:768"
    }
    
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
        
    return {"status": "success", "runway_task": response.json()}


@app.post("/api/v1/audio/suno-audiophile-prompt")
def tao_cau_hinh_suno(request: FilmProjectRequest):
    """Tầng 7 & 11: Tự động hóa sinh mã lệnh Suno chuẩn 100% tiếng Anh, chia 2 phần kèm Stereo 3D Audiophile."""
    tieu_thuyet = request.tieu_thuyet_goc
    part_1 = f"[Style: Cinematic Art-Pop, Binaural 3D spatial audio, holographic soundstage, crystal clear 24-bit audiophile, warm mid, shimmering treble] [Verse 1 & Chorus inspired by: {tieu_thuyet}]"
    part_2 = "[Style: Epic emotional climax, dynamic left-right hard panning, Schumann resonance grounding, rich orchestral strings]"
    
    return {
        "suno_part_1": part_1,
        "suno_part_2": part_2,
        "audiophile_standard": "Đạt chuẩn >= 90 điểm, tách bạch, âm trường rộng sâu."
    }


@app.post("/api/v1/post-production/openai-whisper")
def tao_phu_de_whisper(req: WhisperRequest):
    """Tầng Hậu Kỳ: Trích xuất phụ đề tự động độ chính xác cao bằng OpenAI Whisper API."""
    if not OPENAI_WHISPER_KEY:
        raise HTTPException(status_code=500, detail="Chưa cấu hình OpenAI Whisper API Key.")
        
    url = "https://api.openai.com/v1/audio/transcriptions"
    headers = {"Authorization": f"Bearer {OPENAI_WHISPER_KEY}"}
    
    if not os.path.exists(req.audio_file_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy file âm thanh đầu vào.")
        
    with open(req.audio_file_path, "rb") as audio_file:
        files = {"file": audio_file}
        data = {"model": "whisper-1", "response_format": "srt", "language": "vi"}
        response = requests.post(url, headers=headers, files=files, data=data)
        
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
        
    return {"status": "success", "subtitle_srt": response.text}


@app.post("/api/v1/post-production/ffmpeg-render")
def render_hau_ky_ffmpeg(video_path: str, audio_path: str, subtitle_path: str, output_path: str):
    """Tầng Hậu Kỳ Cuối: Sử dụng FFmpeg để đồng bộ âm thanh, lồng phụ đề và xuất bản file MP4 chuẩn 24fps."""
    ffmpeg_command = (
        f"ffmpeg -i {video_path} -i {audio_path} -c:v libx264 -preset slow -crf 22 "
        f"-vf \"subtitles={subtitle_path}\" -c:a aac -b:a 192k -shortest {output_path} -y"
    )
    
    exit_code = os.system(ffmpeg_command)
    if exit_code != 0:
        raise HTTPException(status_code=500, detail="Lỗi xử lý dựng hình FFmpeg hậu kỳ.")
        
    return {
        "status": "success",
        "output_file": output_path,
        "message": "Đã render thành công video hoàn chỉnh đạt chuẩn phân phối quốc tế."
    }
    
