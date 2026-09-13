import os
import random
import requests
import hashlib
import secrets
import json
import html
from datetime import datetime
from fastapi import FastAPI, Request, Form, Response, Cookie, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

app = FastAPI(title="CineAI Studio Pro 3.0 - Production Backend", version="14.9")

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://djkxwtkhmjpehgqvhkee.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

def get_supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def load_users():
    if not SUPABASE_KEY:
        return {}
    try:
        url = f"{SUPABASE_URL}/rest/v1/cineai_store?id=eq.1&select=payload"
        response = requests.get(url, headers=get_supabase_headers(), timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0 and data[0].get("payload"):
                return data[0].get("payload", {})
    except Exception as e:
        print("Lỗi tải từ Supabase:", e)
    return {}

def save_users():
    if not SUPABASE_KEY:
        return
    try:
        url = f"{SUPABASE_URL}/rest/v1/cineai_store"
        payload = {"id": 1, "payload": USERS_DB}
        headers = get_supabase_headers()
        headers["Prefer"] = "resolution=merge-duplicates"
        requests.post(url, json=payload, headers=headers, timeout=10)
    except Exception as e:
        print("Lỗi lưu Supabase:", e)

USERS_DB = load_users()
ACTIVE_SESSIONS = {}

GEMINI_KEYS_RAW = os.getenv("GEMINI_API_KEYS", "")
GEMINI_KEYS = [k.strip() for k in GEMINI_KEYS_RAW.split(",") if k.strip()]

def call_gemini_direct(prompt_text):
    if not GEMINI_KEYS:
        return None, "Chưa cấu hình GEMINI_API_KEYS trong biến môi trường!"
    
    selected_key = random.choice(GEMINI_KEYS)
    models_to_try = ['gemini-1.5-flash', 'gemini-pro']
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={selected_key}"
        headers = {"Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt_text}]}]}
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                text_result = data["candidates"][0]["content"]["parts"][0]["text"]
                return text_result, model_name
        except Exception:
            pass
    return None, "Lỗi gọi Gemini API"

@app.post("/api/cineai/chat")
async def chat_with_director(data: dict):
    user_message = data.get("message", "")
    if not user_message:
        return JSONResponse({"reply": "Vui lòng nhập nội dung trao đổi!"})
    
    prompt = (
        "Bạn là Đạo diễn ảo chuyên nghiệp của hệ thống Cine AI Studio Pro 3.0. "
        "Hãy phản hồi trực tiếp, tư vấn và cùng người dùng thảo luận kịch bản phim ngắn "
        "tại Tầng 7 & 8 một cách gần gũi, chuyên nghiệp và chi tiết.\n\n"
        f"Yêu cầu từ người dùng: {user_message}"
    )
    
    reply_text, _ = call_gemini_direct(prompt)
    if not reply_text:
        reply_text = "⚠️ Chưa cấu hình hoặc lỗi kết nối GEMINI_API_KEYS trên Render."
        
    return JSONResponse({"reply": reply_text})

def hash_password(password: str, salt: str = None):
    if not salt:
        salt = secrets.token_hex(16)
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return pwd_hash, salt
    
