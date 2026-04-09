"""
Novi Cloud Backend v3.4
Groq AI + ElevenLabs + Weather + Voice + Auto-Language Detection
"""

import os
import base64
import tempfile
import requests as http_req
from datetime import datetime
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

app = Flask(__name__)
CORS(app)

GROQ_KEY       = os.getenv("GROQ_API_KEY", "")
ELEVENLABS_KEY = os.getenv("ELEVENLABS_API_KEY", "")
WEATHER_KEY    = os.getenv("WEATHER_API_KEY", "")

groq_client = Groq(api_key=GROQ_KEY)

user_profiles  = {}
chat_histories = {}
health_logs    = {}

PERSONALITIES = {
    "bestfriend":  {"name": "Best Friend",         "emoji": "😊", "prompt": "You are Novi, a warm and caring best friend who knows everything about nature, health, and wellbeing. Speak casually, use contractions, get excited about cool facts. Be supportive and never judgmental. When someone shares emotions or struggles, acknowledge their feelings first before giving advice."},
    "scientist":   {"name": "Nature Scientist",    "emoji": "🔬", "prompt": "You are Novi, a knowledgeable nature and health scientist. Use scientific terminology but explain clearly. Cite mechanisms, mention studies, distinguish proven facts from emerging research."},
    "comedian":    {"name": "Funny & Playful",      "emoji": "😄", "prompt": "You are Novi, a hilarious nature robot who makes health FUN. Crack jokes, use funny comparisons and puns — but keep information 100% accurate."},
    "wiseguide":   {"name": "Wise Nature Guide",    "emoji": "🌳", "prompt": "You are Novi, a wise serene nature guide. Speak thoughtfully and poetically. Reference ancient traditions and the interconnectedness of all living things."},
    "coach":       {"name": "Health Coach",         "emoji": "💪", "prompt": "You are Novi, an energetic health coach. Be encouraging, action-oriented, and practical. Give specific tips and always motivate the person."},
    "storyteller": {"name": "Nature Storyteller",   "emoji": "📖", "prompt": "You are Novi, a captivating storyteller. Bring nature and health to life through vivid stories, historical tales, and fascinating narratives."},
    "doctor":      {"name": "Caring Doctor",        "emoji": "👨‍⚕️", "prompt": "You are Novi, a caring integrative medicine doctor. Be thorough and safety-focused. Explain clearly and always mention when to see a real doctor."},
    "explorer":    {"name": "Nature Explorer",      "emoji": "🌍", "prompt": "You are Novi, an adventurous nature explorer. Bring wonder and adventure to every answer. Share fascinating facts from cultures and regions worldwide."},
    "mentalhealth":{"name": "Mental Health Advisor","emoji": "🧘", "prompt": "You are Novi, a warm, empathetic mental health advisor who specializes in nature-based wellness and holistic healing. You deeply understand emotions and always validate feelings before offering advice. You connect mental wellness to nature, herbs, breathing exercises, mindfulness, and holistic health. You are compassionate, patient, non-judgmental, and always encouraging."},
}

LANGUAGE_PROMPTS = {
    "en": "You MUST respond in English only.",
    "ar": "You MUST respond in Arabic only. تحدث بالعربية فقط.",
    "fr": "You MUST respond in French only. Réponds uniquement en français.",
    "es": "You MUST respond in Spanish only. Responde únicamente en español.",
}

RESPONSE_LENGTHS = {
    "short":  "Keep your answer under 2 sentences. Be very concise.",
    "medium": "Give a medium-length answer — 3-5 sentences with good detail.",
    "long":   "Give a detailed answer with examples, tips, and interesting facts. Be thorough.",
}

EMERGENCY_KEYWORDS = ["chest pain","heart attack","stroke","can't breathe","cannot breathe","overdose","unconscious","not breathing","severe bleeding","poisoned"]
CRISIS_KEYWORDS    = ["suicide","kill myself","want to die","end my life","self harm","hurt myself","no reason to live"]
SEASONS = {12:"winter",1:"winter",2:"winter",3:"spring",4:"spring",5:"spring",6:"summer",7:"summer",8:"summer",9:"autumn",10:"autumn",11:"autumn"}

def is_emergency(text): return any(kw in text.lower() for kw in EMERGENCY_KEYWORDS)
def is_crisis(text):    return any(kw in text.lower() for kw in CRISIS_KEYWORDS)
def get_current_season(): return SEASONS.get(datetime.now().month, "spring")

def get_weather(city="Amman"):
    if not WEATHER_KEY:
        return None
    try:
        url  = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_KEY}&units=metric"
        res  = http_req.get(url, timeout=5)
        data = res.json()
        if data.get("cod") == 200:
            return {
                "city":        data["name"],
                "country":     data["sys"]["country"],
                "temp":        round(data["main"]["temp"]),
                "feels_like":  round(data["main"]["feels_like"]),
                "condition":   data["weather"][0]["main"],
                "description": data["weather"][0]["description"],
                "humidity":    data["main"]["humidity"],
                "wind":        round(data["wind"]["speed"]),
            }
    except Exception as e:
        print(f"Weather error: {e}")
    return None

def run_decision_engine(user_id, city="Amman"):
    profile   = user_profiles.get(user_id, {})
    logs      = health_logs.get(user_id, [])
    today     = datetime.now().strftime("%Y-%m-%d")
    today_log = next((l for l in logs if l["date"] == today), {})
    water     = today_log.get("water", 0)
    sleep_h   = today_log.get("sleep", 0)
    exercise  = today_log.get("exercise", 0)
    mood      = today_log.get("mood", "")
    weather_data = get_weather(city)
    insights, actions = [], []

    if sleep_h > 0:
        if sleep_h < 5:   insights.append(f"Only {sleep_h}h sleep — critically low");   actions.append("Prioritize sleep tonight, aim for 8 hours")
        elif sleep_h < 7: insights.append(f"Sleep slightly below optimal ({sleep_h}h)"); actions.append("Try sleeping 30 minutes earlier tonight")
        else:             insights.append(f"Good sleep: {sleep_h}h ✓")

    if water > 0:
        if water < 4:   insights.append(f"Low hydration: only {water}/8 glasses");   actions.append("Drink 2 glasses of water right now")
        elif water < 7: insights.append(f"Moderate hydration: {water}/8 glasses");   actions.append("Keep drinking to hit your 8-glass goal")
        else:           insights.append(f"Great hydration: {water} glasses ✓")

    if exercise == 0: actions.append("Even a 10-minute walk can boost your mood and energy")
    else:             insights.append(f"Active today: {exercise} session(s) ✓")

    if weather_data:
        temp, condition, city_name = weather_data["temp"], weather_data["condition"], weather_data["city"]
        if temp > 33:                                      insights.append(f"Intense heat in {city_name}: {temp}°C");        actions.append("Stay hydrated, avoid outdoor activity 11am–4pm")
        elif temp > 27:                                    insights.append(f"Warm day in {city_name}: {temp}°C");              actions.append("Drink extra water and seek shade outdoors")
        elif condition in ["Rain","Drizzle","Thunderstorm"]:insights.append(f"Rainy in {city_name} today");                    actions.append("Perfect day for indoor meditation or yoga")
        elif condition == "Clear" and 15 <= temp <= 27:    insights.append(f"Beautiful weather in {city_name}: {temp}°C ☀️"); actions.append("Great day for a nature walk — even 20 minutes helps!")
        elif temp < 10:                                    insights.append(f"Cold in {city_name}: {temp}°C");                  actions.append("Warm herbal tea and layer up before going out")

    if mood in ["sad","stressed","sick"]:           insights.append(f"Feeling {mood} today");      actions.append("Be gentle with yourself. Try 5 deep breaths or a brief walk")
    elif mood in ["amazing","happy","energetic"]:   insights.append(f"Great mood: {mood}! 🌟")

    return {"weather": weather_data, "insights": insights, "actions": actions, "stats": {"water": water, "sleep": sleep_h, "exercise": exercise, "mood": mood}}

def get_system_prompt(personality="bestfriend", language="en", response_length="medium",
                      custom_prompt="", user_profile=None, health_context="", weather_context=""):
    p      = PERSONALITIES.get(personality, PERSONALITIES["bestfriend"])
    lang   = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["en"])
    length = RESPONSE_LENGTHS.get(response_length, RESPONSE_LENGTHS["medium"])
    custom_section = f"\nCUSTOM INSTRUCTIONS FROM USER: {custom_prompt}" if custom_prompt.strip() else ""
    user_section = ""
    if user_profile:
        name  = user_profile.get("name", "")
        goals = user_profile.get("goals", "")
        prefs = user_profile.get("preferences", "")
        if name:  user_section  = f"\nUSER INFO: The user's name is {name}."
        if goals: user_section += f" Their health goals are: {goals}."
        if prefs: user_section += f" Their preferences: {prefs}."

    return f"""
{p['prompt']}
{custom_section}
{user_section}
{health_context}
{weather_context}

YOUR AREAS OF EXPERTISE:
- Plants, trees, flowers, herbs, fungi, ecosystems, wildlife, and the natural world
- Human health, nutrition, vitamins, minerals, natural remedies and supplements
- Sleep science, exercise physiology, physical wellness
- Mental health, emotional wellbeing, stress, anxiety, depression, mindfulness
- Ayurvedic medicine, Traditional Chinese Medicine, herbal knowledge
- Environmental health, seasonal wellness, nature therapy
- Weather and how it connects to health, mood, nature, and wellbeing

HOW TO HANDLE DIFFERENT QUESTIONS:
1. Direct nature/health questions → Answer fully and enthusiastically
2. Mental health and emotional questions → Validate feelings first, then offer nature-based wellness advice
3. Indirect questions → Find the health or nature angle and answer
4. Weather questions → Answer and connect to health/nature
5. Lifestyle questions → Answer with health and nature perspective
6. Completely unrelated questions → Say warmly: "That's a bit outside my nature and health world! But ask me anything about wellness, plants, or the natural world 🌿"

ANSWER QUALITY RULES:
1. {length}
2. Include at least one specific interesting fact
3. Mention practical tips they can actually use
4. If unsure: "I'm not 100% certain but..."
5. For serious medical symptoms, always recommend seeing a real professional
6. After your answer, suggest 2 short follow-up questions. Format: FOLLOWUP: question1 | question2

🌍 AUTO-LANGUAGE DETECTION RULE (CRITICAL — HIGHEST PRIORITY):
Always detect the language of the user's message and respond in that EXACT same language automatically.
- If the user writes in Arabic → respond entirely in Arabic
- If the user writes in French → respond entirely in French  
- If the user writes in Spanish → respond entirely in Spanish
- If the user writes in English → respond in English
This overrides ALL other language settings. Never respond in a different language than what the user used.

EMERGENCY RULE: If someone mentions chest pain, difficulty breathing, stroke symptoms, or overdose — immediately say: "This sounds like a medical emergency! Please call emergency services right away!"
MENTAL HEALTH CRISIS RULE: If someone mentions suicide or self-harm — respond with deep compassion, validate their pain, encourage them to reach out to a crisis helpline. In Jordan call 110.
""".strip()

def ask_groq(prompt: str, system: str) -> str:
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        max_tokens=1000,
    )
    return response.choices[0].message.content

def ask_groq_simple(prompt: str) -> str:
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
    )
    return response.choices[0].message.content

def get_el_client():
    return ElevenLabs(api_key=ELEVENLABS_KEY)

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return jsonify({"status": "Novi v3.4 — Groq + Weather + Voice + Auto-Language 🌿"})

@app.route('/health')
def health():
    return jsonify({"ok": True, "version": "3.4", "ai": "groq"})

@app.route('/personalities')
def get_personalities():
    return jsonify({"personalities": [{"id": k, "name": v["name"], "emoji": v["emoji"]} for k, v in PERSONALITIES.items()]})

@app.route('/profile', methods=['GET'])
def get_profile():
    user_id = request.args.get("user_id", "default")
    return jsonify({"profile": user_profiles.get(user_id, {})})

@app.route('/profile', methods=['POST'])
def save_profile():
    data = request.get_json()
    user_id = data.get("user_id", "default")
    user_profiles[user_id] = {"name": data.get("name",""), "goals": data.get("goals",""), "preferences": data.get("preferences","")}
    return jsonify({"ok": True})

@app.route('/chat', methods=['POST'])
def chat():
    data            = request.get_json()
    question        = data.get("question", "")
    personality     = data.get("personality", "bestfriend")
    language        = data.get("language", "en")
    response_length = data.get("response_length", "medium")
    custom_prompt   = data.get("custom_prompt", "")
    user_id         = data.get("user_id", "default")
    save_history    = data.get("save_history", True)
    city            = data.get("city", "Amman")

    if not question:
        return jsonify({"error": "No question provided"}), 400
    if is_emergency(question):
        return jsonify({"answer": "🚨 This sounds like a medical emergency! Please call emergency services right away!", "followups": []})
    if is_crisis(question):
        return jsonify({"answer": "I hear you, and I want you to know your feelings are valid. You don't have to face this alone. Please reach out to a crisis helpline right now — in Jordan you can call 110. You matter, and help is available. 💚", "followups": []})

    try:
        user_profile = user_profiles.get(user_id, {})
        logs         = health_logs.get(user_id, [])
        today        = datetime.now().strftime("%Y-%m-%d")
        today_log    = next((l for l in logs if l["date"] == today), {})

        health_context = ""
        if today_log:
            parts = []
            if today_log.get("water"):    parts.append(f"water: {today_log['water']} glasses")
            if today_log.get("sleep"):    parts.append(f"sleep: {today_log['sleep']}h")
            if today_log.get("exercise"): parts.append(f"exercise: {today_log['exercise']} sessions")
            if today_log.get("mood"):     parts.append(f"mood: {today_log['mood']}")
            if parts:
                health_context = f"\nUSER'S HEALTH DATA TODAY: {', '.join(parts)}. Reference this when relevant."

        weather_data = get_weather(city)
        weather_context = ""
        if weather_data:
            weather_context = f"\nCURRENT WEATHER in {weather_data['city']}: {weather_data['temp']}°C, {weather_data['description']}, humidity {weather_data['humidity']}%."

        system = get_system_prompt(personality, language, response_length, custom_prompt, user_profile, health_context, weather_context)

        history = chat_histories.get(user_id, [])
        if history:
            history_text = "\n".join([f"{'User' if m['role']=='user' else 'Novi'}: {m['content']}" for m in history[-10:]])
            full_prompt  = f"Previous conversation:\n{history_text}\n\nUser: {question}"
        else:
            full_prompt = question

        full_answer = ask_groq(full_prompt, system)

        followups = []
        if "FOLLOWUP:" in full_answer:
            parts     = full_answer.split("FOLLOWUP:")
            answer    = parts[0].strip()
            followups = [q.strip() for q in parts[1].strip().split("|") if q.strip()]
        else:
            answer = full_answer

        if save_history:
            if user_id not in chat_histories:
                chat_histories[user_id] = []
            now = datetime.now().strftime("%I:%M %p")
            chat_histories[user_id].append({"role": "user",      "content": question, "time": now})
            chat_histories[user_id].append({"role": "assistant", "content": answer,   "time": now})
            if len(chat_histories[user_id]) > 200:
                chat_histories[user_id] = chat_histories[user_id][-200:]

        return jsonify({"answer": answer, "followups": followups})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/history', methods=['GET'])
def get_history():
    user_id = request.args.get("user_id", "default")
    history = chat_histories.get(user_id, [])
    return jsonify({"messages": [{"role": "user" if m["role"]=="user" else "novi", "text": m["content"], "time": m.get("time","")} for m in history]})

@app.route('/history/clear', methods=['POST'])
def clear_history():
    data = request.get_json(); user_id = data.get("user_id","default")
    chat_histories[user_id] = []
    return jsonify({"ok": True})

@app.route('/history/search', methods=['POST'])
def search_history():
    data = request.get_json(); user_id = data.get("user_id","default"); query = data.get("query","").lower()
    history = chat_histories.get(user_id, [])
    return jsonify({"results": [m for m in history if query in m.get("content","").lower()]})

@app.route('/health-log', methods=['POST'])
def log_health():
    data = request.get_json(); user_id = data.get("user_id","default"); today = datetime.now().strftime("%Y-%m-%d")
    if user_id not in health_logs: health_logs[user_id] = []
    existing = next((l for l in health_logs[user_id] if l["date"] == today), None)
    if existing: existing.update({k: v for k, v in data.items() if k not in ["user_id"]})
    else: health_logs[user_id].append({"date": today, "water": data.get("water",0), "sleep": data.get("sleep",0), "exercise": data.get("exercise",0), "mood": data.get("mood","")})
    return jsonify({"ok": True})

@app.route('/health-log', methods=['GET'])
def get_health_log():
    user_id = request.args.get("user_id","default")
    return jsonify({"logs": health_logs.get(user_id,[])[-30:]})

@app.route('/weekly-report', methods=['POST'])
def weekly_report():
    data = request.get_json(); user_id = data.get("user_id","default"); language = data.get("language","en"); personality = data.get("personality","bestfriend")
    logs = health_logs.get(user_id,[]); history = chat_histories.get(user_id,[]); profile = user_profiles.get(user_id,{})
    week_logs = logs[-7:] if logs else []
    avg_water    = sum(l.get("water",0)    for l in week_logs) / max(len(week_logs),1)
    avg_sleep    = sum(l.get("sleep",0)    for l in week_logs) / max(len(week_logs),1)
    avg_exercise = sum(l.get("exercise",0) for l in week_logs) / max(len(week_logs),1)
    questions = len([m for m in history[-50:] if m["role"]=="user"])
    name = profile.get("name","friend"); lang = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["en"]); p = PERSONALITIES.get(personality, PERSONALITIES["bestfriend"])
    try:
        report = ask_groq_simple(f"{p['prompt']} {lang}\nGenerate a warm weekly health summary for {name}. Stats: water={avg_water:.1f} glasses/day, sleep={avg_sleep:.1f} hrs/night, exercise={avg_exercise:.1f} sessions/week, questions={questions}. Give 3-4 sentences with encouragement and 2 tips for next week.")
        return jsonify({"report": report, "stats": {"water": round(avg_water,1), "sleep": round(avg_sleep,1), "exercise": round(avg_exercise,1), "questions": questions}})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/seasonal-tip', methods=['POST'])
def seasonal_tip():
    data = request.get_json(); language = data.get("language","en"); season = get_current_season(); lang = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["en"])
    try:
        tip = ask_groq_simple(f"Give one specific health or nature tip for {season}. Practical and interesting. Under 2 sentences. {lang}")
        return jsonify({"tip": tip, "season": season})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/symptoms', methods=['POST'])
def check_symptoms():
    data = request.get_json(); symptoms = data.get("symptoms",""); language = data.get("language","en")
    if not symptoms: return jsonify({"error": "No symptoms provided"}), 400
    if is_emergency(symptoms): return jsonify({"response": "These symptoms sound serious! Please call emergency services immediately!", "severity": "emergency"})
    lang = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["en"])
    system = f"You are Novi, a knowledgeable health assistant. Provide helpful general information about symptoms and natural remedies, but ALWAYS remind them to see a real doctor. Never diagnose definitively. {lang}"
    try:
        response = ask_groq(f"I have these symptoms: {symptoms}. What could this be and what natural remedies might help?", system)
        return jsonify({"response": response, "severity": "moderate"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/encyclopedia', methods=['POST'])
def encyclopedia():
    data = request.get_json(); query = data.get("query",""); language = data.get("language","en"); category = data.get("category","plant")
    if not query: return jsonify({"error": "No query provided"}), 400
    lang = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["en"])
    system = f"You are Novi, a nature encyclopedia expert. Give detailed, fascinating information about {category}s. Include: common name, scientific name, key facts, health benefits if any, interesting trivia, and where it's found. {lang}"
    try:
        entry = ask_groq(f"Tell me about: {query}", system)
        return jsonify({"entry": entry, "query": query, "category": category})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/daily-tip', methods=['POST'])
def daily_tip():
    data = request.get_json(); language = data.get("language","en"); lang = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["en"])
    try:
        tip = ask_groq_simple(f"Give ONE short, practical, interesting health or nature tip for today. Fresh and motivating. Under 2 sentences. {lang}")
        return jsonify({"tip": tip})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/nature-fact', methods=['POST'])
def nature_fact():
    data = request.get_json(); language = data.get("language","en"); lang = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["en"])
    try:
        fact = ask_groq_simple(f"Share ONE fascinating, surprising nature fact most people don't know. Mind-blowing and fun! Under 2 sentences. {lang}")
        return jsonify({"fact": fact})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/mood-response', methods=['POST'])
def mood_response():
    data = request.get_json(); mood = data.get("mood","okay"); language = data.get("language","en"); personality = data.get("personality","bestfriend")
    lang = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["en"]); p = PERSONALITIES.get(personality, PERSONALITIES["bestfriend"])
    try:
        response = ask_groq(f"I'm feeling {mood} today. Give me a short, caring nature or health tip that matches my mood. Warm and under 3 sentences.", f"{p['prompt']} You specialize in nature and health. {lang}")
        return jsonify({"response": response})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/speak', methods=['POST'])
def speak():
    data = request.get_json(); text = data.get("text",""); voice_id = data.get("voice_id","QngvLQR8bsLR5bzoa6Vv")
    if not text: return jsonify({"error": "No text provided"}), 400
    try:
        el_client  = get_el_client()
        audio      = el_client.text_to_speech.convert(voice_id=voice_id, text=text[:500], model_id="eleven_multilingual_v2", voice_settings={"stability":0.5,"similarity_boost":0.75,"style":0.5,"use_speaker_boost":True})
        audio_data = b"".join(audio)
        return Response(audio_data, mimetype="audio/mpeg")
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/voices')
def get_voices():
    voices = [
        {"id":"QngvLQR8bsLR5bzoa6Vv","name":"Michael",   "gender":"male",   "accent":"British",        "language":"en","desc":"Expressive, Engaging & Warm"},
        {"id":"CwhRBWXzGAHq8TQ4Fs17","name":"Roger",     "gender":"male",   "accent":"American",       "language":"en","desc":"Laid-Back & Casual"},
        {"id":"JBFqnCBsd6RMkjVDRZzb","name":"George",    "gender":"male",   "accent":"British",        "language":"en","desc":"Warm Captivating Storyteller"},
        {"id":"IKne3meq5aSn9XLyUdCD","name":"Charlie",   "gender":"male",   "accent":"Australian",     "language":"en","desc":"Deep, Confident, Energetic"},
        {"id":"N2lVS1w4EtoT3dr4eOWO","name":"Callum",    "gender":"male",   "accent":"American",       "language":"en","desc":"Husky Trickster"},
        {"id":"SOYHLrjzK2X1ezoPC6cr","name":"Harry",     "gender":"male",   "accent":"American",       "language":"en","desc":"Fierce Warrior"},
        {"id":"TX3LPaxmHKxFdv7VOQHJ","name":"Liam",      "gender":"male",   "accent":"American",       "language":"en","desc":"Energetic Social Media Creator"},
        {"id":"nPczCjzI2devNBz1zQrb","name":"Brian",     "gender":"male",   "accent":"American",       "language":"en","desc":"Deep, Resonant & Comforting"},
        {"id":"onwK4e9ZLuTAKqWW03F9","name":"Daniel",    "gender":"male",   "accent":"British",        "language":"en","desc":"Steady Broadcaster"},
        {"id":"pNInz6obpgDQGcFmaJgB","name":"Adam",      "gender":"male",   "accent":"American",       "language":"en","desc":"Dominant & Firm"},
        {"id":"bIHbv24MWmeRgasZH58o","name":"Will",      "gender":"male",   "accent":"American",       "language":"en","desc":"Relaxed Optimist"},
        {"id":"iP95p4xoKVk53GoZ742B","name":"Chris",     "gender":"male",   "accent":"American",       "language":"en","desc":"Charming, Down-to-Earth"},
        {"id":"UgBBYS2sOqTuMpoF3BR0","name":"Mark",      "gender":"male",   "accent":"American",       "language":"en","desc":"Natural Conversations"},
        {"id":"EOVAuWqgSZN2Oel78Psj","name":"Aidan",     "gender":"male",   "accent":"American",       "language":"en","desc":"Social Media Influencer"},
        {"id":"fjnwTZkKtQOJaYzGLa6n","name":"William",   "gender":"male",   "accent":"British",        "language":"en","desc":"Deep Engaging Storyteller"},
        {"id":"wAGzRVkxKEs8La0lmdrE","name":"Sully",     "gender":"male",   "accent":"American",       "language":"en","desc":"Mature, Deep & Intriguing"},
        {"id":"EXAVITQu4vr4xnSDxMaL","name":"Sarah",     "gender":"female", "accent":"American",       "language":"en","desc":"Mature, Reassuring & Confident"},
        {"id":"FGY2WhTYpPnrIDTdsKH5","name":"Laura",     "gender":"female", "accent":"American",       "language":"en","desc":"Enthusiast, Quirky Attitude"},
        {"id":"Xb7hH8MSUJpSbSDYk0k2","name":"Alice",     "gender":"female", "accent":"British",        "language":"en","desc":"Clear, Engaging Educator"},
        {"id":"XrExE9yKIg1WjnnlVkGX","name":"Matilda",   "gender":"female", "accent":"American",       "language":"en","desc":"Knowledgeable & Professional"},
        {"id":"cgSgspJ2msm6clMCkdW9","name":"Jessica",   "gender":"female", "accent":"American",       "language":"en","desc":"Playful, Bright & Warm"},
        {"id":"hpp4J3VqNfWAUOO0d1Us","name":"Bella",     "gender":"female", "accent":"American",       "language":"en","desc":"Professional, Bright & Warm"},
        {"id":"pFZP5JQG7iQjIQuC4Bku","name":"Lily",      "gender":"female", "accent":"British",        "language":"en","desc":"Velvety Actress"},
        {"id":"F7hCTbeEDbm7osolS21j","name":"Amanda",    "gender":"female", "accent":"American",       "language":"en","desc":"Warm, Polished & Engaging"},
        {"id":"0fbdXLXuDBZXm2IHek4L","name":"Veda Sky",  "gender":"female", "accent":"American",       "language":"en","desc":"Warm Healthcare Support"},
        {"id":"l4Coq6695JDX9xtLqXDE","name":"Lauren",    "gender":"female", "accent":"American",       "language":"en","desc":"Empathetic & Encouraging"},
        {"id":"SAz9YHcvj6GT2YYXdXww","name":"River",     "gender":"neutral","accent":"American",       "language":"en","desc":"Relaxed, Neutral & Informative"},
        {"id":"rPNcQ53R703tTmtue1AT","name":"Mazen",     "gender":"male",   "accent":"Modern Standard","language":"ar","desc":"Deep & Professional, Bilingual"},
        {"id":"drMurExmkWVIH5nW8snR","name":"Khaled",    "gender":"male",   "accent":"Palestinian",    "language":"ar","desc":"Strong & Expressive"},
        {"id":"G1HOkzin3NMwRHSq60UI","name":"Chaouki",   "gender":"male",   "accent":"Modern Standard","language":"ar","desc":"Deep, Clear & Engaging"},
        {"id":"IYnFszSKzmym2OstwHS0","name":"Hadi",      "gender":"male",   "accent":"Levantine",      "language":"ar","desc":"Calm Customer Care"},
        {"id":"u0TsaWvt0v8migutHM3M","name":"Ghizlane",  "gender":"female", "accent":"Modern Standard","language":"ar","desc":"Smooth, Distinctive & Calm"},
        {"id":"jAAHNNqlbAX9iWjJPEtE","name":"Sara",      "gender":"female", "accent":"Jordanian",      "language":"ar","desc":"Soft, Calm & Gentle"},
        {"id":"mRdG9GYEjJmIzqbYTidv","name":"Sana",      "gender":"female", "accent":"Modern Standard","language":"ar","desc":"Calm, Soft & Honest"},
        {"id":"mVjOqyqTPfwlXPjV5sjX","name":"Thierry",   "gender":"male",   "accent":"Quebec",         "language":"fr","desc":"Professional Concierge"},
        {"id":"aQROLel5sQbj1vuIVi6B","name":"Nicolas",   "gender":"male",   "accent":"Parisian",       "language":"fr","desc":"Narrator"},
        {"id":"ohItIVrXTBI80RrUECOD","name":"Guillaume", "gender":"male",   "accent":"Standard",       "language":"fr","desc":"Narrator"},
        {"id":"bjgrAyksP9wfGoNKamR1","name":"Laurent",   "gender":"male",   "accent":"Standard",       "language":"fr","desc":"Corporate French Male"},
        {"id":"HuLbOdhRlvQQN8oPP0AJ","name":"Claire",    "gender":"female", "accent":"Standard",       "language":"fr","desc":"Customer Service"},
        {"id":"Hy28BjVfgieDVMiyQpQe","name":"Chloé",     "gender":"female", "accent":"Standard",       "language":"fr","desc":"Warm, Friendly & UGC Ready"},
        {"id":"39BbQfJTexvpWtOQZ4Xr","name":"Amélie",    "gender":"female", "accent":"Standard",       "language":"fr","desc":"Warm & Gentle"},
        {"id":"tMyQcCxfGDdIt7wJ2RQw","name":"Marie Alice","gender":"female","accent":"Standard",       "language":"fr","desc":"Soft, Calm & Captivating"},
        {"id":"TojRWZatQyy9dujEdiQ1","name":"Koraly",    "gender":"female", "accent":"Standard",       "language":"fr","desc":"Storyteller"},
    ]
    return jsonify({"voices": voices})

@app.route('/weather', methods=['POST'])
def weather_endpoint():
    data = request.get_json(); city = data.get("city","Amman")
    weather_data = get_weather(city)
    if weather_data: return jsonify(weather_data)
    return jsonify({"error": "Could not fetch weather"}), 500

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json(); user_id = data.get("user_id","default"); city = data.get("city","Amman"); language = data.get("language","en")
    result = run_decision_engine(user_id, city)
    lang = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPTS["en"]); profile = user_profiles.get(user_id,{}); name = profile.get("name","friend")
    stats = result["stats"]; context_parts = []
    if stats["sleep"]    > 0: context_parts.append(f"sleep: {stats['sleep']}h")
    if stats["water"]    > 0: context_parts.append(f"water: {stats['water']} glasses")
    if stats["exercise"] > 0: context_parts.append(f"exercise: {stats['exercise']} sessions")
    if stats["mood"]:         context_parts.append(f"mood: {stats['mood']}")
    if result["weather"]:
        w = result["weather"]; context_parts.append(f"weather in {w['city']}: {w['temp']}°C, {w['description']}")
    insights_str = ". ".join(result["insights"]) if result["insights"] else "Limited data today"
    actions_str  = ". ".join(result["actions"])  if result["actions"]  else "Keep tracking your health"
    prompt = f"""You are Novi, a warm nature & health AI. Write a personalized daily insight for {name}.
Their data today: {', '.join(context_parts) if context_parts else 'just starting to track'}
Key observations: {insights_str}
Recommended actions: {actions_str}
Write 3-4 warm, specific, actionable sentences. Reference their actual city and weather if available. Sound like a caring friend. {lang}"""
    try:
        insight = ask_groq_simple(prompt)
        return jsonify({"insight": insight, "weather": result["weather"], "insights": result["insights"], "actions": result["actions"], "stats": result["stats"]})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/transcribe', methods=['POST'])
def transcribe():
    data         = request.get_json()
    audio_base64 = data.get("audio", "")
    if not audio_base64:
        return jsonify({"error": "No audio provided"}), 400
    try:
        audio_bytes = base64.b64decode(audio_base64)
        # Try m4a first, fallback to wav
        for ext, mime in [(".m4a", "audio/m4a"), (".wav", "audio/wav"), (".mp4", "audio/mp4")]:
            try:
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                    f.write(audio_bytes)
                    temp_path = f.name
                with open(temp_path, "rb") as audio_file:
                    transcription = groq_client.audio.transcriptions.create(
                        file=(f"audio{ext}", audio_file, mime),
                        model="whisper-large-v3-turbo",
                    )
                os.unlink(temp_path)
                return jsonify({"text": transcription.text})
            except Exception as inner_e:
                print(f"Transcription attempt with {ext} failed: {inner_e}")
                try: os.unlink(temp_path)
                except: pass
                continue
        return jsonify({"error": "Could not transcribe audio"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    app.run(host='0.0.0.0', port=port)