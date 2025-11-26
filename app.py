from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import base64
import requests
import io
from PIL import Image
from dotenv import load_dotenv
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)  # أصلحت هنا (كان __main__ غلط)

load_dotenv()

app = FastAPI()

# APIs
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = "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"

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_API_KEY = "sk-...YOUR_OPENAI_KEY_HERE..."  # حطي هنا الـ OpenAI Key بتاعك (من https://platform.openai.com/api-keys)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    html_content = """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AI Medical Chatbot</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); margin: 0; padding: 20px; color: #333; }
            .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 15px; padding: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.1); }
            h1 { text-align: center; color: #1976d2; margin-bottom: 30px; font-size: 2.5em; }
            form { display: flex; flex-direction: column; gap: 15px; }
            input[type="file"], input[type="text"] { padding: 12px; border: 2px solid #ddd; border-radius: 8px; font-size: 16px; }
            input[type="text"] { height: 50px; }
            input[type="submit"] { background: #1976d2; color: white; padding: 15px; border: none; border-radius: 8px; font-size: 18px; cursor: pointer; transition: background 0.3s; }
            input[type="submit"]:hover { background: #1565c0; }
            .response { margin-top: 20px; padding: 15px; background: #f5f5f5; border-radius: 8px; display: none; }
            .error { background: #ffebee; color: #c62828; border: 1px solid #ef5350; }
            .success { background: #e8f5e8; color: #2e7d32; border: 1px solid #4caf50; }
            label { font-weight: bold; color: #555; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 AI Medical Chatbot</h1>
            <p style="text-align: center; color: #666;">ارفع صورة طبية أو اكتب سؤالك الطبي، وهساعدك فورًا!</p>
            <form id="chatForm" enctype="multipart/form-data" method="post" action="/upload_and_query">
                <label for="image">صورة (اختياري):</label>
                <input type="file" id="image" name="image" accept="image/*">
                
                <label for="query">سؤالك (مطلوب):</label>
                <input type="text" id="query" name="query" placeholder="مثال: إيه اللي في الصورة دي؟ أو وصف أعراضك..." required>
                
                <input type="submit" value="إرسال السؤال">
            </form>
            <div id="response" class="response"></div>
        </div>
        <script>
            document.getElementById('chatForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                const formData = new FormData(this);
                const respDiv = document.getElementById('response');
                respDiv.className = 'response'; // Reset class
                respDiv.style.display = 'block';
                respDiv.innerHTML = '<p>جاري التحليل... انتظري شوية</p>';
                
                try {
                    const response = await fetch('/upload_and_query', { method: 'POST', body: formData });
                    const data = await response.json();
                    if (data.error || data.detail) {
                        respDiv.className += ' error';
                        respDiv.innerHTML = `<p>❌ خطأ: ${data.error || data.detail}</p>`;
                    } else {
                        respDiv.className += ' success';
                        respDiv.innerHTML = `<p>✅ الإجابة (${data.model}):</p><p>${data.response}</p>`;
                    }
                } catch (err) {
                    respDiv.className += ' error';
                    respDiv.innerHTML = `<p>❌ مشكلة في الاتصال: ${err.message}</p>`;
                }
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html_content)

@app.post("/upload_and_query")
async def upload_and_query(
    image: UploadFile = File(None),  # اختياري
    query: str = Form(...)           # إجباري
):
    if not query.strip():
        raise HTTPException(status_code=400, detail="السؤال مطلوب!")

    try:
        # لو في صورة → استخدم OpenAI Vision
        if image and image.filename:
            image_content = await image.read()
            if not image_content:
                raise HTTPException(status_code=400, detail="الملف فاضي")

            encoded_image = base64.b64encode(image_content).decode("utf-8")

            # التحقق من الصورة
            try:
                img = Image.open(io.BytesIO(image_content))
                img.verify()
            except Exception as e:
                logger.error(f"صيغة الصورة غلط: {str(e)}")
                raise HTTPException(status_code=400, detail="الصورة مش صالحة، جربي صورة تانية")

            # OpenAI Vision request
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": query},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"}}
                    ]
                }
            ]

            try:
                response = requests.post(
                    OPENAI_API_URL,
                    json={
                        "model": "gpt-4o-mini",  # أفضل موديل Vision رخيص
                        "messages": messages,
                        "max_tokens": 1000,
                        "temperature": 0.7
                    },
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    timeout=60
                )
                if response.status_code == 200:
                    answer = response.json()["choices"][0]["message"]["content"].strip()
                    return {"response": answer, "model": "GPT-4o-mini (Vision)"}
                else:
                    error_msg = response.json().get("error", {}).get("message", "مشكلة في السيرفر")
                    raise HTTPException(status_code=500, detail=f"خطأ من OpenAI: {error_msg}")
            except Exception as e:
                logger.error(f"خطأ في OpenAI: {str(e)}")
                raise HTTPException(status_code=500, detail=f"مشكلة في تحليل الصورة: {str(e)}")

        # لو مفيش صورة → استخدم Groq للنص (الموديل الجديد)
        else:
            try:
                response = requests.post(
                    GROQ_API_URL,
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                    json={
                        "model": "llama-3.3-70b-versatile",  # البديل الرسمي والأقوى (بدل llama3-70b-8192)
                        "messages": [{"role": "user", "content": query}],
                        "temperature": 0.7,
                        "max_tokens": 1024
                    },
                    timeout=30
                )
                if response.status_code == 200:
                    answer = response.json()["choices"][0]["message"]["content"].strip()
                    return {"response": answer, "model": "Llama-3.3-70B (Text)"}
                else:
                    error_msg = response.json().get("error", {}).get("message", "مشكلة في السيرفر")
                    raise HTTPException(status_code=500, detail=f"خطأ من Groq: {error_msg}")
            except Exception as e:
                logger.error(f"خطأ في Groq: {str(e)}")
                raise HTTPException(status_code=500, detail=f"مشكلة في الاتصال: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"خطأ غير متوقع: {str(e)}")
        raise HTTPException(status_code=500, detail="حصل خطأ داخلي، جربي تاني")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)