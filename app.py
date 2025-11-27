import json
import os
import base64
import requests
import io
from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException
from fastapi.responses import HTMLResponse
from PIL import Image
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

app = FastAPI()

# تحميل بيانات الأطباء من JSON
DOCTORS_DATA = {"doctors": []}
try:
    with open("doctors.json", "r", encoding="utf-8") as f:
        DOCTORS_DATA = json.load(f)
    logger.info("تم تحميل بيانات الأطباء من doctors.json")
except FileNotFoundError:
    logger.warning("ملف doctors.json مش موجود، هيشتغل بدون مواعيد الأطباء")

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# دالة البحث عن الدكتور في الـ JSON
def find_doctor_in_db(query: str):
    q = query.lower().strip()
    for doc in DOCTORS_DATA.get("doctors", []):
        if (q in doc.get("name", "").lower() or 
            # أحمد
            q in doc.get("full_name", "").lower() or          # دكتور أحمد محمد
            doc.get("specialty", "").lower() in q or          # أسنان
            q in doc.get("specialty", "").lower()):           # جلدية
            return doc
    return None

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>الدكتور الذكي - عيادة وتين</title>
        <style>
            body { font-family: 'Cairo', sans-serif; background: linear-gradient(135deg, #e3f2fd, #bbdefb); margin:0; padding:20px; }
            .container { max-width:650px; margin:auto; background:white; padding:30px; border-radius:20px; box-shadow:0 15px 40px rgba(0,0,0,0.15); }
            h1 { text-align:center; color:#1976d2; }
            input, button { padding:15px; margin:10px 0; width:100%; border-radius:12px; border:2px solid #ddd; font-size:17px; }
            button { background:#1976d2; color:white; border:none; cursor:pointer; font-weight:bold; }
            button:hover { background:#1565c0; }
            .response { margin-top:25px; padding:20px; border-radius:12px; display:none; font-size:18px; line-height:1.8; }
            .from-db { background:#e8f5e8; border:2px solid #4caf50; }
            .from-ai { background:#fff3e0; border:2px solid #ff9800; }
            .error { background:#ffebee; border:2px solid #f44336; }
        </style>
        <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;700&display=swap" rel="stylesheet">
    </head>
    <body>
        <div class="container">
            <h1>الدكتور الذكي - عيادة وتين</h1>
            <p style="text-align:center;">اسأل عن مواعيد الدكاترة أو ارفع أشعة أو وصف أعراضك</p>
            
            <form id="chatForm" enctype="multipart/form-data">
                <input type="file" name="image" accept="image/*"><br>
                <input type="text" name="query" placeholder="مثلاً: مواعيد دكتور أحمد محمد؟ أو أشعة صدر" required><br>
                <button type="submit">إرسال</button>
            </form>
            
            <div id="response" class="response"></div>
        </div>

        <script>
            document.getElementById('chatForm').onsubmit = async (e) => {
                e.preventDefault();
                const fd = new FormData(e.target);
                const div = document.getElementById('response');
                div.style.display = 'block';
                div.className = 'response';
                div.innerHTML = 'جاري البحث والتحليل...';

                try {
                    const res = await fetch('/upload_and_query', {method:'POST', body:fd});
                    const data = await res.json();
                    if (data.error) {
                        div.className += ' error';
                        div.innerHTML = `<p>خطأ: ${data.error}</p>`;
                    } else if (data.from_db) {
                        div.className += ' from-db';
                        div.innerHTML = data.response;
                    } else {
                        div.className += ' from-ai';
                        div.innerHTML = `<strong>الذكاء الاصطناعي قال (${data.model}):</strong><br>${data.response.replace(/\\n/g, '<br>')}`;
                    }
                } catch (err) {
                    div.className += ' error';
                    div.innerHTML = `<p>مشكلة في الاتصال: ${err.message}</p>`;
                }
            };
        </script>
    </body>
    </html>
    """

@app.post("/upload_and_query")
async def upload_and_query(image: UploadFile = File(None), query: str = Form(...)):
    user_query = query.strip()

    # أولاً: نشوف لو السؤال عن دكتور في الـ JSON
    doctor = find_doctor_in_db(user_query)
    if doctor:
        days = "، ".join(doctor["days"])
        response_text = f"""
        <h3 style="color:#1976d2; margin:0;">{doctor['full_name']} - {doctor['specialty']}</h3>
        <p><strong>أيام الكشف:</strong> {days}</p>
        <p><strong>المواعيد:</strong> من {doctor['from']} إلى {doctor['to']}</p>
        <p><strong>العيادة:</strong> {doctor.get('location', 'عيادة وتين')}</p>
        <p><strong>تليفون الحجز:</strong> {doctor.get('phone', 'غير متاح')}</p>
        <p style="margin-top:15px;"><a href="https://wa.me/2{doctor.get('phone', '').lstrip('0')}" 
           style="background:#25d366;color:white;padding:10px 20px;border-radius:8px;text-decoration:none;">حجز فوري عبر واتساب</a></p>
        """
        return {"response": response_text, "from_db": True}

    # لو مش دكتور → نروح للـ AI (زي الكود الأصلي)
    try:
        # لو في صورة → GPT-4o Vision
        if image and image.filename:
            content = await image.read()
            if len(content) > 12_000_000:
                raise HTTPException(400, "الصورة كبيرة أوي (أكتر من 12 ميجا)")

            base64_image = base64.b64encode(content).decode('utf-8')

            payload = {
                "model": "gpt-4o-mini",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"السؤال: {user_query}\nجاوب بالعربي المصري"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                    ]
                }],
                "max_tokens": 1000
            }
            headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
            r = requests.post(OPENAI_API_URL, json=payload, headers=headers, timeout=90)
            r.raise_for_status()
            answer = r.json()["choices"][0]["message"]["content"].strip()
            return {"response": answer, "model": "GPT-4o-mini (Vision)", "from_db": False}

        # نص بس → Groq Llama 3.3
        else:
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": f"جاوب بالعربي المصري: {user_query}"}],
                "temperature": 0.7,
                "max_tokens": 1024
            }
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
            r = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=40)
            r.raise_for_status()
            answer = r.json()["choices"][0]["message"]["content"].strip()
            return {"response": answer, "model": "Llama-3.3-70B", "from_db": False}

    except Exception as e:
        logger.error(f"AI Error: {e}")
        raise HTTPException(status_code=500, detail="السيرفر زعلان شوية، جرب تاني بعد دقيقة")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
