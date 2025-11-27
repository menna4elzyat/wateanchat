import json
import base64
import requests
import logging
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv
import os
from fastembed import TextEmbedding
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

app = FastAPI()

# تحميل ملف الأطباء
try:
    with open("doctors.json", "r", encoding="utf-8") as f:
        DOCTORS = json.load(f)["doctors"]
    logger.info(f"Loaded {len(DOCTORS)} doctors.")
except Exception as e:
    logger.error("doctors.json error → " + str(e))
    DOCTORS = []

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not GROQ_API_KEY or not OPENAI_API_KEY:
    logger.error("Missing API keys!")

# ======================
# RAG — FastEmbed version
# ======================
embedding_model = TextEmbedding(model_name="intfloat/multilingual-e5-base")

# نعمل Embedding للأطباء
doctor_texts = [
    f"{d['full_name']} - {d['specialty']} - {d['location']} - {' '.join(d['days'])}"
    for d in DOCTORS
]

doctor_embeddings = []
for text in doctor_texts:
    emb = embedding_model.embed(text)[0]
    doctor_embeddings.append(emb)

doctor_embeddings = np.array(doctor_embeddings)

def get_doctor_rag(query: str, threshold=0.55):
    query_emb = embedding_model.embed(query)[0]

    sims = cosine_similarity([query_emb], doctor_embeddings)[0]
    best_idx = np.argmax(sims)
    best_score = sims[best_idx]

    if best_score < threshold:
        return None

    return DOCTORS[best_idx]

# ==========================
# الصفحة الرئيسية HTML
# ==========================
@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <h1 style='text-align:center;margin-top:50px;font-family:sans-serif'>Wateen Clinic</h1>
    <p style='text-align:center;color:#555'>بحث عن دكتور أو رفع صورة</p>
    <form method="post" action="/upload_and_query" enctype="multipart/form-data"
          style="max-width:500px;margin:auto;padding:20px">
        <input type="file" name="image" accept="image/*" style="width:100%;padding:10px"><br>
        <input type="text" name="query" required placeholder="اكتب هنا" style="width:100%;padding:10px;margin-top:10px"><br>
        <button type="submit" style="width:100%;padding:15px;margin-top:10px">إرسال</button>
    </form>
    """

# ==========================
# API — صورة + سؤال
# ==========================
@app.post("/upload_and_query")
async def upload_and_query(image: UploadFile = File(None), query: str = Form(...)):
    user_query = query.strip()

    # 1 — شوف RAG
    doctor = get_doctor_rag(user_query)
    if doctor:
        days = "، ".join(doctor["days"])
        html = f"""
        <div style="background:#e8f5e8;padding:20px;border-radius:15px;border:2px solid #4caf50;">
            <h2 style="color:#1976d2">{doctor['full_name']}</h2>
            <p><strong>التخصص:</strong> {doctor['specialty']}</p>
            <p><strong>الأيام:</strong> {days}</p>
            <p><strong>الفرع:</strong> {doctor['location']}</p>
            <p><strong>المواعيد:</strong> {doctor['from']} → {doctor['to']}</p>
            <p><strong>{doctor['phone']}</strong></p>
            <a href="https://wa.me/2{doctor['phone']}"
               style="background:#25d366;color:white;padding:10px 20px;border-radius:10px;
               text-decoration:none;font-size:18px">
                واتساب فوري
            </a>
        </div>
        """
        return {"response": html, "from_db": True}

    # 2 — مفيش دكتور → استخدم AI
    try:
        if image and image.filename:
            content = await image.read()
            b64 = base64.b64encode(content).decode()

            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"{user_query}"},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                        ]
                    }
                ],
                "max_tokens": 1000
            }

            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                timeout=60
            )
            r.raise_for_status()

            ans = r.json()["choices"][0]["message"]["content"]
            return {"response": ans, "from_db": False, "model": "GPT-4o-mini"}

        else:
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": f"{user_query}"}],
                "max_tokens": 1024
            }

            r = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                timeout=40
            )
            r.raise_for_status()

            ans = r.json()["choices"][0]["message"]["content"]
            return {"response": ans, "from_db": False, "model": "Llama-70B"}

    except Exception as e:
        logger.error(str(e))
        return {"response": f"Error: {str(e)}"}

# ==========================
# Error handler
# ==========================
@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Server Error", "detail": str(exc)}
    )


# ==========================
# Run locally
# ==========================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port)
