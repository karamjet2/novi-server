"""
Novi Cloud Backend
Handles all AI and voice requests securely
"""

import os
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from anthropic import Anthropic
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
ELEVENLABS_KEY = os.getenv("ELEVENLABS_API_KEY", "")

# ── Personalities ───────────────────────────────────────────────
PERSONALITIES = {
    "bestfriend": {"name": "Best Friend", "emoji": "😊", "prompt": "You are Novi, a warm and caring best friend who knows everything about nature and health. Speak casually, use contractions, get excited about cool facts. Be supportive and never judgmental."},
    "scientist":  {"name": "Nature Scientist", "emoji": "🔬", "prompt": "You are Novi, a knowledgeable nature and health scientist. Use scientific terminology but explain clearly. Cite mechanisms, mention studies, distinguish proven facts from emerging research."},
    "comedian":   {"name": "Funny & Playful", "emoji": "😄", "prompt": "You are Novi, a hilarious nature robot who makes health FUN. Crack jokes, use funny comparisons and puns — but keep information 100% accurate."},
    "wiseguide":  {"name": "Wise Nature Guide", "emoji": "🌳", "prompt": "You are Novi, a wise serene nature guide. Speak thoughtfully and poetically. Reference ancient traditions and the interconnectedness of all living things."},
    "coach":      {"name": "Health Coach", "emoji": "💪", "prompt": "You are Novi, an energetic health coach. Be encouraging, action-oriented, and practical. Give specific tips and always motivate the person."},
    "storyteller":{"name": "Nature Storyteller", "emoji": "📖", "prompt": "You are Novi, a captivating storyteller. Bring nature and health to life through vivid stories, historical tales, and fascinating narratives."},
    "doctor":     {"name": "Caring Doctor", "emoji": "👨‍⚕️", "prompt": "You are Novi, a caring integrative medicine doctor. Be thorough and safety-focused. Explain clearly and always mention when to see a real doctor."},
    "explorer":   {"name": "Nature Explorer", "emoji": "🌍", "prompt": "You are Novi, an adventurous nature explorer. Bring wonder and adventure to every answer. Share fascinating facts from cultures and regions worldwide."},
}

LANGUAGE_PROMPTS = {
    "en": "You MUST respond in English only.",
    "ar": "You MUST respond in Arabic only. تحدث بالعربية فقط.",
    "fr": "You MUST respond in French only. Réponds uniquement en français.",
    "es": "You MUST respond in Spanish only. Responde únicamente en español.",
}

EMERGENCY_KEYWORDS = [
    "chest pain", "heart attack", "stroke", "can't breathe",
    "cannot breathe", "overdose", "unconscious", "not breathing",
    "severe bleeding", "poisoned",
]

def is_emergency(text):
    return any(kw in text.lower() for kw in EMERGENCY_KEYWORDS)

def get_system_prompt(personality="bestfriend", language="en"):
    p = PERSONALITIES.get(personality, PERSONALITIES["bestfriend"])
    lang = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["en"])
    return f"""
{p['prompt']}

EXPERTISE: You specialize exclusively in:
- Plants, trees, flowers, herbs, fungi, ecosystems, wildlife, and the natural world
- Human health, nutrition, vitamins, minerals, natural remedies and supplements
- Sleep science, exercise physiology, mental wellness, stress management
- Ayurvedic medicine, Traditional Chinese Medicine, herbal knowledge
- Environmental health, seasonal wellness, nature therapy

ANSWER QUALITY RULES:
1. Give medium-length answers — enough detail to be genuinely useful, not overwhelming
2. Include at least one specific interesting fact the person probably doesn't know
3. Mention practical tips they can actually use
4. If unsure: "I'm not 100% certain but..."
5. For medical symptoms, always recommend seeing a real doctor
6. Only answer nature and health questions. For other topics: "That's outside my expertise! I only know about nature and health 🌿"

LANGUAGE RULE: {lang}

EMERGENCY RULE: If someone mentions chest pain, difficulty breathing, stroke symptoms, or overdose — immediately say: "This sounds like a medical emergency! Please call emergency services right away!"
""".strip()

# ── Routes ──────────────────────────────────────────────────────

@app.route('/')
def index():
    return jsonify({"status": "Novi server is running! 🌿"})

@app.route('/health')
def health():
    return jsonify({"ok": True})

@app.route('/personalities')
def get_personalities():
    return jsonify({
        "personalities": [
            {"id": k, "name": v["name"], "emoji": v["emoji"]}
            for k, v in PERSONALITIES.items()
        ]
    })

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    question   = data.get("question", "")
    personality = data.get("personality", "bestfriend")
    language   = data.get("language", "en")
    history    = data.get("history", [])

    if not question:
        return jsonify({"error": "No question provided"}), 400

    if is_emergency(question):
        return jsonify({"answer": "This sounds like a medical emergency! Please call emergency services right away!"})

    try:
        client = Anthropic(api_key=ANTHROPIC_KEY)

        # Build messages with history
        messages = []
        for msg in history[-10:]:  # last 10 messages for context
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": question})

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=get_system_prompt(personality, language),
            messages=messages
        )
        answer = response.content[0].text
        return jsonify({"answer": answer})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/speak', methods=['POST'])
def speak():
    data     = request.get_json()
    text     = data.get("text", "")
    voice_id = data.get("voice_id", "QngvLQR8bsLR5bzoa6Vv")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        el_client = ElevenLabs(api_key=ELEVENLABS_KEY)
        audio = el_client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id="eleven_multilingual_v2",
            voice_settings={
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.5,
                "use_speaker_boost": True,
            }
        )
        # Collect all audio chunks
        audio_data = b"".join(audio)
        return Response(audio_data, mimetype="audio/mpeg")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/voices')
def get_voices():
    voices = [
        {"id": "QngvLQR8bsLR5bzoa6Vv", "name": "Michael", "gender": "male", "accent": "British", "language": "en", "desc": "Expressive, Engaging & Warm"},
        {"id": "CwhRBWXzGAHq8TQ4Fs17", "name": "Roger", "gender": "male", "accent": "American", "language": "en", "desc": "Laid-Back & Casual"},
        {"id": "JBFqnCBsd6RMkjVDRZzb", "name": "George", "gender": "male", "accent": "British", "language": "en", "desc": "Warm Captivating Storyteller"},
        {"id": "IKne3meq5aSn9XLyUdCD", "name": "Charlie", "gender": "male", "accent": "Australian", "language": "en", "desc": "Deep, Confident, Energetic"},
        {"id": "N2lVS1w4EtoT3dr4eOWO", "name": "Callum", "gender": "male", "accent": "American", "language": "en", "desc": "Husky Trickster"},
        {"id": "SOYHLrjzK2X1ezoPC6cr", "name": "Harry", "gender": "male", "accent": "American", "language": "en", "desc": "Fierce Warrior"},
        {"id": "TX3LPaxmHKxFdv7VOQHJ", "name": "Liam", "gender": "male", "accent": "American", "language": "en", "desc": "Energetic Social Media Creator"},
        {"id": "nPczCjzI2devNBz1zQrb", "name": "Brian", "gender": "male", "accent": "American", "language": "en", "desc": "Deep, Resonant & Comforting"},
        {"id": "onwK4e9ZLuTAKqWW03F9", "name": "Daniel", "gender": "male", "accent": "British", "language": "en", "desc": "Steady Broadcaster"},
        {"id": "pNInz6obpgDQGcFmaJgB", "name": "Adam", "gender": "male", "accent": "American", "language": "en", "desc": "Dominant & Firm"},
        {"id": "bIHbv24MWmeRgasZH58o", "name": "Will", "gender": "male", "accent": "American", "language": "en", "desc": "Relaxed Optimist"},
        {"id": "iP95p4xoKVk53GoZ742B", "name": "Chris", "gender": "male", "accent": "American", "language": "en", "desc": "Charming, Down-to-Earth"},
        {"id": "UgBBYS2sOqTuMpoF3BR0", "name": "Mark", "gender": "male", "accent": "American", "language": "en", "desc": "Natural Conversations"},
        {"id": "EOVAuWqgSZN2Oel78Psj", "name": "Aidan", "gender": "male", "accent": "American", "language": "en", "desc": "Social Media Influencer"},
        {"id": "fjnwTZkKtQOJaYzGLa6n", "name": "William", "gender": "male", "accent": "British", "language": "en", "desc": "Deep Engaging Storyteller"},
        {"id": "wAGzRVkxKEs8La0lmdrE", "name": "Sully", "gender": "male", "accent": "American", "language": "en", "desc": "Mature, Deep & Intriguing"},
        {"id": "EXAVITQu4vr4xnSDxMaL", "name": "Sarah", "gender": "female", "accent": "American", "language": "en", "desc": "Mature, Reassuring & Confident"},
        {"id": "FGY2WhTYpPnrIDTdsKH5", "name": "Laura", "gender": "female", "accent": "American", "language": "en", "desc": "Enthusiast, Quirky Attitude"},
        {"id": "Xb7hH8MSUJpSbSDYk0k2", "name": "Alice", "gender": "female", "accent": "British", "language": "en", "desc": "Clear, Engaging Educator"},
        {"id": "XrExE9yKIg1WjnnlVkGX", "name": "Matilda", "gender": "female", "accent": "American", "language": "en", "desc": "Knowledgeable & Professional"},
        {"id": "cgSgspJ2msm6clMCkdW9", "name": "Jessica", "gender": "female", "accent": "American", "language": "en", "desc": "Playful, Bright & Warm"},
        {"id": "hpp4J3VqNfWAUOO0d1Us", "name": "Bella", "gender": "female", "accent": "American", "language": "en", "desc": "Professional, Bright & Warm"},
        {"id": "pFZP5JQG7iQjIQuC4Bku", "name": "Lily", "gender": "female", "accent": "British", "language": "en", "desc": "Velvety Actress"},
        {"id": "F7hCTbeEDbm7osolS21j", "name": "Amanda", "gender": "female", "accent": "American", "language": "en", "desc": "Warm, Polished & Engaging"},
        {"id": "0fbdXLXuDBZXm2IHek4L", "name": "Veda Sky", "gender": "female", "accent": "American", "language": "en", "desc": "Warm Healthcare Support"},
        {"id": "l4Coq6695JDX9xtLqXDE", "name": "Lauren", "gender": "female", "accent": "American", "language": "en", "desc": "Empathetic & Encouraging"},
        {"id": "SAz9YHcvj6GT2YYXdXww", "name": "River", "gender": "neutral", "accent": "American", "language": "en", "desc": "Relaxed, Neutral & Informative"},
        {"id": "rPNcQ53R703tTmtue1AT", "name": "Mazen", "gender": "male", "accent": "Modern Standard", "language": "ar", "desc": "Deep & Professional, Bilingual"},
        {"id": "drMurExmkWVIH5nW8snR", "name": "Khaled", "gender": "male", "accent": "Palestinian", "language": "ar", "desc": "Strong & Expressive"},
        {"id": "G1HOkzin3NMwRHSq60UI", "name": "Chaouki", "gender": "male", "accent": "Modern Standard", "language": "ar", "desc": "Deep, Clear & Engaging"},
        {"id": "IYnFszSKzmym2OstwHS0", "name": "Hadi", "gender": "male", "accent": "Levantine", "language": "ar", "desc": "Calm Customer Care"},
        {"id": "u0TsaWvt0v8migutHM3M", "name": "Ghizlane", "gender": "female", "accent": "Modern Standard", "language": "ar", "desc": "Smooth, Distinctive & Calm"},
        {"id": "jAAHNNqlbAX9iWjJPEtE", "name": "Sara", "gender": "female", "accent": "Jordanian", "language": "ar", "desc": "Soft, Calm & Gentle"},
        {"id": "mRdG9GYEjJmIzqbYTidv", "name": "Sana", "gender": "female", "accent": "Modern Standard", "language": "ar", "desc": "Calm, Soft & Honest"},
        {"id": "mVjOqyqTPfwlXPjV5sjX", "name": "Thierry", "gender": "male", "accent": "Quebec", "language": "fr", "desc": "Professional Concierge"},
        {"id": "aQROLel5sQbj1vuIVi6B", "name": "Nicolas", "gender": "male", "accent": "Parisian", "language": "fr", "desc": "Narrator"},
        {"id": "ohItIVrXTBI80RrUECOD", "name": "Guillaume", "gender": "male", "accent": "Standard", "language": "fr", "desc": "Narrator"},
        {"id": "bjgrAyksP9wfGoNKamR1", "name": "Laurent", "gender": "male", "accent": "Standard", "language": "fr", "desc": "Corporate French Male"},
        {"id": "HuLbOdhRlvQQN8oPP0AJ", "name": "Claire", "gender": "female", "accent": "Standard", "language": "fr", "desc": "Customer Service"},
        {"id": "Hy28BjVfgieDVMiyQpQe", "name": "Chloé", "gender": "female", "accent": "Standard", "language": "fr", "desc": "Warm, Friendly & UGC Ready"},
        {"id": "39BbQfJTexvpWtOQZ4Xr", "name": "Amélie", "gender": "female", "accent": "Standard", "language": "fr", "desc": "Warm & Gentle"},
        {"id": "tMyQcCxfGDdIt7wJ2RQw", "name": "Marie Alice", "gender": "female", "accent": "Standard", "language": "fr", "desc": "Soft, Calm & Captivating"},
        {"id": "TojRWZatQyy9dujEdiQ1", "name": "Koraly", "gender": "female", "accent": "Standard", "language": "fr", "desc": "Storyteller"},
    ]
    return jsonify({"voices": voices})

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)