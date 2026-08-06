import os
import base64
import threading

import telebot
from telebot import types
from groq import Groq
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not BOT_TOKEN or not GROQ_API_KEY:
    raise RuntimeError("BOT_TOKEN va GROQ_API_KEY Render Variables/.env da bo‘lishi kerak")

bot = telebot.TeleBot(BOT_TOKEN)
client = Groq(api_key=GROQ_API_KEY)
app = Flask(__name__)
CORS(app)
WEB_APP_URL = "https://abdulaziznormuminov18-creator.github.io/fitotahlil-app/?v=6"

PROMPTS = {
    "fertilizer": """Siz professional agronom va o‘g‘itlash bo‘yicha mutaxassissiz. Berilgan ma’lumotlar asosida o‘zbek tilida xavfsiz o‘g‘itlash rejasini tuzing. O‘simlik nomi, tuvak diametri va balandligi, tuproq hajmi, o‘simlik yoshi, holati va o‘g‘it turini hisobga oling. Natijada: tuvak hajmi, mos o‘g‘it, bir martalik miqdor, qancha suvga aralashtirish, qo‘llash oralig‘i, keyingi sana va sababni yozing. Mahsulot yorlig‘idagi dozadan oshirmaslikni ayting.""",
    "identify": """O‘simlik rasmini aniqlang. O‘zbek tilida quyidagilarni bering: o‘simlik nomi, lotincha nomi, asosiy xususiyatlari, yorug‘lik talabi, sug‘orish, tuproq va o‘g‘it tavsiyasi. Rasm sifati past bo‘lsa, noaniqlikni ayting.""", 
    "analyze": """O‘simlikning umumiy holatini tahlil qiling: sog‘lomlik, barg va gul holati, o‘sish dinamikasi, suvsizlanish yoki ortiqcha namlik belgilari, sug‘orish va o‘g‘it tavsiyasi, keyingi tekshiruv sanasi. O‘zbek tilida yozing.""",
    "diagnose": """O‘simlikdagi kasallik va zararkunandalarni aniqlang. O‘zbek tilida quyidagilarni bering: kasallik nomi, zararkunanda nomi yoki ‘aniqlanmadi’, dalillar, xavf darajasi, davolash, xavfsizlik va qayta tekshirish. Aniq bo‘lmasa, buni ayting."""
}

def ai_analyze(image_bytes, mode="analyze"):
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    completion = client.chat.completions.create(
        model="qwen/qwen3.6-27b",
        messages=[{"role": "user", "content": [
            {"type": "text", "text": PROMPTS.get(mode, PROMPTS["analyze"])},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}}
        ]}],
        temperature=0.2,
        max_completion_tokens=1200,
        reasoning_effort="none",
        reasoning_format="hidden"
    )
    return completion.choices[0].message.content or "AI javobi bo‘sh qaytdi."

@app.get("/")
def home():
    return jsonify(status="ok", message="FitoTahlil AI API ishlayapti")

@app.get("/health")
def health():
    return jsonify(status="healthy")

@app.post("/api/fertilizer")
def fertilizer_api():
    data = request.get_json(silent=True) or {}
    required = ["plant", "diameter", "height", "soil", "age", "condition"]
    if any(not str(data.get(key, "")).strip() for key in required):
        return jsonify(success=False, error="Barcha maydonlarni to‘ldiring"), 400
    user_text = (
        PROMPTS["fertilizer"] + "\\n\\n"
        f"O‘simlik: {data.get('plant')}\\n"
        f"Tuvak diametri: {data.get('diameter')} sm\\n"
        f"Tuvak balandligi: {data.get('height')} sm\\n"
        f"Tuproq hajmi: {data.get('soil')} litr\\n"
        f"O‘simlik yoshi: {data.get('age')}\\n"
        f"O‘simlik holati: {data.get('condition')}\\n"
        f"O‘g‘it turi: {data.get('fertilizer') or 'AI o‘zi moslasin'}"
    )
    try:
        answer = client.chat.completions.create(
            model="qwen/qwen3.6-27b",
            messages=[{"role": "user", "content": user_text}],
            temperature=0.2,
            max_completion_tokens=800,
            reasoning_effort="none",
            reasoning_format="hidden"
        ).choices[0].message.content
        return jsonify(success=True, result=answer or "Natija bo‘sh qaytdi")
    except Exception as error:
        print("O‘g‘it API xatosi:", repr(error))
        return jsonify(success=False, error="AI hisoblashda xatolik yuz berdi"), 500

@app.post("/api/<mode>")
def api_analysis(mode):
    if mode not in PROMPTS:
        return jsonify(success=False, error="Noto‘g‘ri tahlil turi"), 404
    if "image" not in request.files:
        return jsonify(success=False, error="Rasm topilmadi"), 400
    image = request.files["image"].read()
    if not image:
        return jsonify(success=False, error="Rasm bo‘sh"), 400
    if len(image) > 10 * 1024 * 1024:
        return jsonify(success=False, error="Rasm 10 MB dan kichik bo‘lishi kerak"), 413
    try:
        return jsonify(success=True, mode=mode, result=ai_analyze(image, mode))
    except Exception as error:
        print("API xatosi:", repr(error))
        return jsonify(success=False, error="AI tahlilida xatolik yuz berdi"), 500

@bot.message_handler(commands=["start", "help"])
def start(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "🌿 FitoTahlil AI ilovasini ochish",
        web_app=types.WebAppInfo(url=WEB_APP_URL)
    ))
    bot.send_message(message.chat.id, "Mini App ichida o‘simlikni aniqlash va tahlil qilish uchun tugmani bosing.", reply_markup=markup)

@bot.message_handler(content_types=["photo"])
def telegram_photo(message):
    status = bot.reply_to(message, "⏳ Rasm tahlil qilinmoqda...")
    try:
        info = bot.get_file(message.photo[-1].file_id)
        result = ai_analyze(bot.download_file(info.file_path), "diagnose")
        bot.edit_message_text("📋 AI DIAGNOSTIKA\n\n" + result, message.chat.id, status.message_id)
    except Exception as error:
        print("Telegram xatosi:", repr(error))
        bot.edit_message_text("⚠️ Tahlilni amalga oshirib bo‘lmadi.", message.chat.id, status.message_id)

def run_bot():
    bot.delete_webhook(drop_pending_updates=True)
    bot.infinity_polling(timeout=30, long_polling_timeout=30)

if __name__ == "__main__":
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False)
