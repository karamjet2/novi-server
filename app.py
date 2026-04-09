"""
Novi Cloud Backend v3
Full featured — chat history, user memory, encyclopedia, health tracker, weekly report, seasonal tips, symptoms checker
"""

import os
import json
from datetime import datetime, timedelta
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

# ── In-memory storage (persists while server runs) ───────────────
user_profiles = {}   # user_id -> {name, goals, preferences}
chat_histories = {}  # user_id -> [{role, content, time}]
health_logs    = {}  # user_id -> [{date, water, sleep, exercise, mood}]

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

RESPONSE_LENGTHS = {
    "short": "Keep your answer under 2 sentences. Be very concise.",
    "medium": "Give a medium-length answer — 3-5 sentences with good detail.",
    "long": "Give a detailed answer with examples, tips, and interesting facts. Be thorough.",
}

EMERGENCY_KEYWORDS = [
    "chest pain", "heart attack", "stroke", "can't breathe",
    "cannot breathe", "overdose", "unconscious", "not breathing",
    "severe bleeding", "poisoned",
]

SEASONS = {
    12: "winter", 1: "winter", 2: "winter",
    3: "spring", 4: "spring", 5: "spring",
    6: "summer", 7: "summer", 8: "summer",
    9: "autumn", 10: "autumn", 11: "autumn",
}

def is_emergency(text):
    return any(kw in text.lower() for kw in EMERGENCY_KEYWORDS)

def get_current_season():
    return SEASONS.get(datetime.now().month, "spring")

def get_system_prompt(personality="bestfriend", language="en", response_length="medium", custom_prompt="", user_profile=None):
    p = PERSONALITIES.get(personality, PERSONALITIES["bestfriend"])
    lang = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["en"])
    length = RESPONSE_LENGTHS.get(response_length, RESPONSE_LENGTHS["medium"])
    custom_section = f"\nCUSTOM INSTRUCTIONS FROM USER: {custom_prompt}" if custom_prompt.strip() else ""
    user_section = ""
    if user_profile:
        name = user_profile.get("name", "")
        goals = user_profile.get("goals", "")
        prefs = user_profile.get("preferences", "")
        if name:
            user_section = f"\nUSER INFO: The user's name is {name}."
        if goals:
            user_section += f" Their health goals are: {goals}."
        if prefs:
            user_section += f" Their preferences: {prefs}."

    return f"""
{p['prompt']}
{custom_section}
{user_section}

EXPERTISE: You specialize exclusively in:
- Plants, trees, flowers, herbs, fungi, ecosystems, wildlife, and the natural world
- Human health, nutrition, vitamins, minerals, natural remedies and supplements
- Sleep science, exercise physiology, mental wellness, stress management
- Ayurvedic medicine, Traditional Chinese Medicine, herbal knowledge
- Environmental health, seasonal wellness, nature therapy

ANSWER QUALITY RULES:
1. {length}
2. Include at least one specific interesting fact the person probably doesn't know
3. Mention practical tips they can actually use
4. If unsure: "I'm not 100% certain but..."
5. For medical symptoms, always recommend seeing a real doctor
6. Only answer nature and health questions. For other topics say: "That's outside my expertise! I only know about nature and health 🌿"
7. After your answer, suggest 2 short follow-up questions the user might want to ask. Format them as: FOLLOWUP: question1 | question2

LANGUAGE RULE: {lang}

EMERGENCY RULE: If someone mentions chest pain, difficulty breathing, stroke symptoms, or overdose — immediately say: "This sounds like a medical emergency! Please call emergency services right away!"
""".strip()

# ── Helper ──────────────────────────────────────────────────────
def get_client():
    return Anthropic(api_key=ANTHROPIC_KEY)

def get_el_client():
    return ElevenLabs(api_key=ELEVENLABS_KEY)

# ── Routes ──────────────────────────────────────────────────────

@app.route('/')
def index():
    return jsonify({"status": "Novi server v3 is running! 🌿"})

@app.route('/health')
def health():
    return jsonify({"ok": True, "version": "3.0"})

@app.route('/personalities')
def get_personalities():
    return jsonify({
        "personalities": [
            {"id": k, "name": v["name"], "emoji": v["emoji"]}
            for k, v in PERSONALITIES.items()
        ]
    })

# ── User Profile ─────────────────────────────────────────────────
@app.route('/profile', methods=['GET'])
def get_profile():
    user_id = request.args.get("user_id", "default")
    return jsonify({"profile": user_profiles.get(user_id, {})})

@app.route('/profile', methods=['POST'])
def save_profile():
    data = request.get_json()
    user_id = data.get("user_id", "default")
    user_profiles[user_id] = {
        "name": data.get("name", ""),
        "goals": data.get("goals", ""),
        "preferences": data.get("preferences", ""),
    }
    return jsonify({"ok": True, "profile": user_profiles[user_id]})

# ── Chat ─────────────────────────────────────────────────────────
@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    question        = data.get("question", "")
    personality     = data.get("personality", "bestfriend")
    language        = data.get("language", "en")
    response_length = data.get("response_length", "medium")
    custom_prompt   = data.get("custom_prompt", "")
    user_id         = data.get("user_id", "default")
    save_history    = data.get("save_history", True)

    if not question:
        return jsonify({"error": "No question provided"}), 400

    if is_emergency(question):
        return jsonify({"answer": "This sounds like a medical emergency! Please call emergency services right away!", "followups": []})

    try:
        client = get_client()
        user_profile = user_profiles.get(user_id, {})

        # Get saved history for this user
        history = chat_histories.get(user_id, [])
        messages = []
        for msg in history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": question})

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=get_system_prompt(personality, language, response_length, custom_prompt, user_profile),
            messages=messages
        )
        full_answer = response.content[0].text

        # Extract follow-up questions
        followups = []
        if "FOLLOWUP:" in full_answer:
            parts = full_answer.split("FOLLOWUP:")
            answer = parts[0].strip()
            followup_text = parts[1].strip()
            followups = [q.strip() for q in followup_text.split("|") if q.strip()]
        else:
            answer = full_answer

        # Save to history
        if save_history:
            if user_id not in chat_histories:
                chat_histories[user_id] = []
            now = datetime.now().strftime("%I:%M %p")
            chat_histories[user_id].append({"role": "user", "content": question, "time": now})
            chat_histories[user_id].append({"role": "assistant", "content": answer, "time": now})
            # Keep last 200 messages
            if len(chat_histories[user_id]) > 200:
                chat_histories[user_id] = chat_histories[user_id][-200:]

        return jsonify({"answer": answer, "followups": followups})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Chat History ─────────────────────────────────────────────────
@app.route('/history', methods=['GET'])
def get_history():
    user_id = request.args.get("user_id", "default")
    history = chat_histories.get(user_id, [])
    # Format for app
    messages = []
    for i in range(0, len(history), 2):
        if i < len(history):
            msg = history[i]
            messages.append({
                "role": "user" if msg["role"] == "user" else "novi",
                "text": msg["content"],
                "time": msg.get("time", "")
            })
        if i + 1 < len(history):
            msg = history[i + 1]
            messages.append({
                "role": "novi",
                "text": msg["content"],
                "time": msg.get("time", "")
            })
    return jsonify({"messages": messages})

@app.route('/history/clear', methods=['POST'])
def clear_history():
    data = request.get_json()
    user_id = data.get("user_id", "default")
    chat_histories[user_id] = []
    return jsonify({"ok": True})

@app.route('/history/search', methods=['POST'])
def search_history():
    data = request.get_json()
    user_id = data.get("user_id", "default")
    query = data.get("query", "").lower()
    history = chat_histories.get(user_id, [])
    results = [msg for msg in history if query in msg.get("content", "").lower()]
    return jsonify({"results": results})

# ── Health Tracker ───────────────────────────────────────────────
@app.route('/health-log', methods=['POST'])
def log_health():
    data = request.get_json()
    user_id = data.get("user_id", "default")
    today = datetime.now().strftime("%Y-%m-%d")
    if user_id not in health_logs:
        health_logs[user_id] = []
    # Update or add today's log
    existing = next((l for l in health_logs[user_id] if l["date"] == today), None)
    if existing:
        existing.update({k: v for k, v in data.items() if k not in ["user_id"]})
    else:
        health_logs[user_id].append({
            "date": today,
            "water": data.get("water", 0),
            "sleep": data.get("sleep", 0),
            "exercise": data.get("exercise", 0),
            "mood": data.get("mood", ""),
        })
    return jsonify({"ok": True})

@app.route('/health-log', methods=['GET'])
def get_health_log():
    user_id = request.args.get("user_id", "default")
    logs = health_logs.get(user_id, [])
    # Last 30 days
    return jsonify({"logs": logs[-30:]})

# ── Weekly Report ────────────────────────────────────────────────
@app.route('/weekly-report', methods=['POST'])
def weekly_report():
    data = request.get_json()
    user_id  = data.get("user_id", "default")
    language = data.get("language", "en")
    personality = data.get("personality", "bestfriend")

    logs = health_logs.get(user_id, [])
    history = chat_histories.get(user_id, [])
    profile = user_profiles.get(user_id, {})

    # Last 7 days stats
    week_logs = logs[-7:] if logs else []
    avg_water    = sum(l.get("water", 0) for l in week_logs) / max(len(week_logs), 1)
    avg_sleep    = sum(l.get("sleep", 0) for l in week_logs) / max(len(week_logs), 1)
    avg_exercise = sum(l.get("exercise", 0) for l in week_logs) / max(len(week_logs), 1)
    questions_asked = len([m for m in history[-50:] if m["role"] == "user"])

    try:
        client = get_client()
        lang = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["en"])
        p = PERSONALITIES.get(personality, PERSONALITIES["bestfriend"])
        name = profile.get("name", "friend")

        prompt = f"""
{p['prompt']}
{lang}
Generate a warm, encouraging weekly health summary for {name}.
Their stats this week:
- Average water intake: {avg_water:.1f} glasses/day
- Average sleep: {avg_sleep:.1f} hours/night  
- Exercise sessions: {avg_exercise:.1f} times/week
- Questions asked to Novi: {questions_asked}

Give a 3-4 sentence summary with encouragement and 2 specific tips for next week. Be warm and motivating.
"""
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        return jsonify({"report": response.content[0].text, "stats": {
            "water": round(avg_water, 1),
            "sleep": round(avg_sleep, 1),
            "exercise": round(avg_exercise, 1),
            "questions": questions_asked
        }})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Seasonal Tips ────────────────────────────────────────────────
@app.route('/seasonal-tip', methods=['POST'])
def seasonal_tip():
    data = request.get_json()
    language = data.get("language", "en")
    season = get_current_season()

    try:
        client = get_client()
        lang = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["en"])
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            messages=[{"role": "user", "content": f"Give one specific health or nature tip for {season}. Make it practical and interesting. Under 2 sentences. {lang}"}]
        )
        return jsonify({"tip": response.content[0].text, "season": season})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Symptoms Checker ─────────────────────────────────────────────
@app.route('/symptoms', methods=['POST'])
def check_symptoms():
    data = request.get_json()
    symptoms = data.get("symptoms", "")
    language = data.get("language", "en")

    if not symptoms:
        return jsonify({"error": "No symptoms provided"}), 400

    if is_emergency(symptoms):
        return jsonify({"response": "These symptoms sound serious! Please call emergency services or go to the nearest hospital immediately!", "severity": "emergency"})

    try:
        client = get_client()
        lang = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["en"])
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=f"You are Novi, a knowledgeable health assistant. When someone describes symptoms, provide helpful general information about possible causes and natural remedies, but ALWAYS remind them to see a real doctor for proper diagnosis. Never diagnose. {lang}",
            messages=[{"role": "user", "content": f"I have these symptoms: {symptoms}. What could this be and what natural remedies might help?"}]
        )
        return jsonify({"response": response.content[0].text, "severity": "moderate"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Plant Encyclopedia ───────────────────────────────────────────
@app.route('/encyclopedia', methods=['POST'])
def encyclopedia():
    data = request.get_json()
    query    = data.get("query", "")
    language = data.get("language", "en")
    category = data.get("category", "plant")  # plant, herb, tree, animal

    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        client = get_client()
        lang = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["en"])
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=f"You are Novi, a nature encyclopedia expert. Give detailed, fascinating information about {category}s in a structured way. Include: common name, scientific name, key facts, health benefits if any, interesting trivia, and where it's found. Be engaging and educational. {lang}",
            messages=[{"role": "user", "content": f"Tell me about: {query}"}]
        )
        return jsonify({"entry": response.content[0].text, "query": query, "category": category})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Daily Tip ────────────────────────────────────────────────────
@app.route('/daily-tip', methods=['POST'])
def daily_tip():
    data = request.get_json()
    language    = data.get("language", "en")
    personality = data.get("personality", "bestfriend")

    try:
        client = get_client()
        lang = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["en"])
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            system=f"You are Novi, a nature and health AI. Give ONE short, practical, interesting health or nature tip for today. Make it feel fresh and motivating. Keep it under 2 sentences. {lang}",
            messages=[{"role": "user", "content": "Give me today's health tip"}]
        )
        return jsonify({"tip": response.content[0].text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Nature Fact ──────────────────────────────────────────────────
@app.route('/nature-fact', methods=['POST'])
def nature_fact():
    data = request.get_json()
    language = data.get("language", "en")

    try:
        client = get_client()
        lang = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["en"])
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            system=f"You are Novi, a nature expert. Share ONE fascinating, surprising nature fact that most people don't know. Make it mind-blowing and fun! Keep it under 2 sentences. {lang}",
            messages=[{"role": "user", "content": "Give me an amazing nature fact"}]
        )
        return jsonify({"fact": response.content[0].text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Mood Response ────────────────────────────────────────────────
@app.route('/mood-response', methods=['POST'])
def mood_response():
    data = request.get_json()
    mood        = data.get("mood", "okay")
    language    = data.get("language", "en")
    personality = data.get("personality", "bestfriend")

    try:
        client = get_client()
        lang = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["en"])
        p = PERSONALITIES.get(personality, PERSONALITIES["bestfriend"])
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            system=f"{p['prompt']} You specialize in nature and health. {lang}",
            messages=[{"role": "user", "content": f"I'm feeling {mood} today. Give me a short, caring nature or health tip that matches my mood. Keep it warm and under 3 sentences."}]
        )
        return jsonify({"response": response.content[0].text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Speak ────────────────────────────────────────────────────────
@app.route('/speak', methods=['POST'])
def speak():
    data     = request.get_json()
    text     = data.get("text", "")
    voice_id = data.get("voice_id", "QngvLQR8bsLR5bzoa6Vv")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        el_client = get_el_client()
        audio = el_client.text_to_speech.convert(
            voice_id=voice_id,
            text=text[:500],  # limit to 500 chars to save credits
            model_id="eleven_multilingual_v2",
            voice_settings={
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.5,
                "use_speaker_boost": True,
            }
        )
        audio_data = b"".join(audio)
        return Response(audio_data, mimetype="audio/mpeg")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Voices ───────────────────────────────────────────────────────
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