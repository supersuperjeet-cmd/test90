import os
import random
import logging
import secrets
import json
from threading import Thread
from datetime import datetime

from flask import Flask, request, jsonify, render_template, session, redirect
from tinydb import TinyDB, Query
import psycopg2
import psycopg2.extras
from openai import OpenAI
from google import genai

# CONFIG & SECRETS (Optimized for Render)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")
TG_TOKEN = os.environ.get("TG_TOKEN")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
WEB_PASSWORD = os.environ.get("WEB_PASSWORD", "love u")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

# Replit Specific Gemini Fallback
REPLIT_GEMINI_KEY = os.environ.get("AI_INTEGRATIONS_GEMINI_API_KEY")
REPLIT_GEMINI_URL = os.environ.get("AI_INTEGRATIONS_GEMINI_BASE_URL")

# AI CLIENTS SETUP
def init_ai_clients():
    clients = {"groq": None, "gemini": None, "openai": None}
    
    if GROQ_API_KEY:
        try:
            clients["groq"] = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
        except Exception as e:
            logging.error(f"Groq Client Init Error: {e}")
    
    if REPLIT_GEMINI_KEY and REPLIT_GEMINI_URL:
        try:
            clients["gemini"] = genai.Client(api_key=REPLIT_GEMINI_KEY, http_options={'api_version': '', 'base_url': REPLIT_GEMINI_URL})
        except Exception as e:
            logging.error(f"Replit Gemini Client Init Error: {e}")
    elif GEMINI_API_KEY:
        try:
            clients["gemini"] = genai.Client(api_key=GEMINI_API_KEY)
        except Exception as e:
            logging.error(f"Gemini Client Init Error: {e}")
        
    if OPENAI_API_KEY:
        try:
            clients["openai"] = OpenAI(api_key=OPENAI_API_KEY)
        except Exception as e:
            logging.error(f"OpenAI Client Init Error: {e}")
        
    return clients

AI_CLIENTS = init_ai_clients()

# LOGGING
logging.basicConfig(level=logging.INFO)

# DB SETUP
db = TinyDB('db.json')
Users = Query()
os.makedirs('static/music', exist_ok=True)

# MEMORY.JSON SETUP (Admin Instructions - Preferred over Database)
def load_memory():
    try:
        with open('memory.json', 'r') as f:
            return json.load(f)
    except:
        return {"admin_instructions": "", "system_state": "Operational", "behavioral_rules": []}

def save_memory(memory_data):
    try:
        with open('memory.json', 'w') as f:
            json.dump(memory_data, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Failed to save memory.json: {e}")
        return False

# Optimized simple db connection for Render/PostgreSQL
def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url: return None
    try:
        return psycopg2.connect(db_url)
    except Exception as e:
        logging.error(f"DB Connection Error: {e}")
        return None

def sync_memory_to_db():
    """Sync memory.json to database for backup and migration"""
    conn = get_db_connection()
    if not conn: return
    try:
        memory_json = load_memory()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                ("memory_backup", json.dumps(memory_json))
            )
            conn.commit()
        logging.info("Memory synced to database successfully")
    except Exception as e:
        logging.error(f"Failed to sync memory to database: {e}")
    finally:
        conn.close()

def init_db():
    conn = get_db_connection()
    if not conn: 
        logging.warning("No PostgreSQL connection available. Using TinyDB only.")
        return
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS users (id BIGINT PRIMARY KEY, memory TEXT, mood TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS messages (id SERIAL PRIMARY KEY, user_id BIGINT, message TEXT, response TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            cur.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS diary (user_id BIGINT PRIMARY KEY, notes JSONB, last_ai_line TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS game_submissions (id SERIAL PRIMARY KEY, game_type TEXT, content TEXT, file_path TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
            conn.commit()
        
        # MANDATORY: Sync memory.json immediately to new DB connection
        logging.info("Ensuring memory.json is synced to the new database...")
        memory_json = load_memory()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                ("memory_backup", json.dumps(memory_json))
            )
            conn.commit()
        logging.info("Memory synced to database successfully on initialization")
    except Exception as e:
        logging.error(f"Table creation or sync failed: {e}")
    finally:
        if conn:
            conn.close()

init_db()

MEMORY = load_memory()

# DB HELPERS
def get_user_data(user_id):
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                if row: return dict(row)
        finally: conn.close()
    
    user = db.table('users').get(Users.id == user_id)
    return user if user else {"id": user_id, "memory": "", "mood": "loving"}

def update_user_data(user_id, memory, mood):
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO users (id, memory, mood) VALUES (%s, %s, %s) ON CONFLICT (id) DO UPDATE SET memory = EXCLUDED.memory, mood = EXCLUDED.mood", (user_id, memory, mood))
                conn.commit()
        finally: conn.close()
    db.table('users').upsert({"id": user_id, "memory": memory, "mood": mood}, Users.id == user_id)

def save_message(user_id, msg, response):
    timestamp = datetime.now().isoformat()
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO messages (user_id, message, response) VALUES (%s, %s, %s)", (user_id, msg, response))
                conn.commit()
                logging.info(f"Message saved to PostgreSQL for user {user_id}")
        except Exception as e:
            logging.error(f"Database message save error: {e}")
        finally: conn.close()
    
    # Always backup to TinyDB
    try:
        db.table('messages').insert({
            'user_id': user_id,
            'message': msg,
            'response': response,
            'timestamp': timestamp
        })
        logging.info(f"Message backed up to TinyDB for user {user_id}")
    except Exception as e:
        logging.error(f"TinyDB message backup error: {e}")

def get_messages(user_id, limit=None):
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                if limit:
                    cur.execute("SELECT * FROM messages WHERE user_id = %s ORDER BY timestamp DESC LIMIT %s", (user_id, limit))
                else:
                    cur.execute("SELECT * FROM messages WHERE user_id = %s ORDER BY timestamp DESC", (user_id,))
                msgs = [dict(row) for row in cur.fetchall()][::-1]
                if msgs:
                    return msgs
        except Exception as e:
            logging.error(f"Database message retrieval error: {e}")
        finally: conn.close()
    
    # Fallback to TinyDB
    try:
        msgs = db.table('messages').search(Query().user_id == user_id)
        if msgs:
            sorted_msgs = sorted(msgs, key=lambda x: x.get('timestamp', ''))
            return sorted_msgs[-limit:] if limit else sorted_msgs
    except Exception as e:
        logging.error(f"TinyDB message retrieval error: {e}")
    
    return []

def get_config(key, default):
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM config WHERE key = %s", (key,))
                row = cur.fetchone()
                if row: return row[0]
        finally: conn.close()
    item = db.table('config').get(Query().key == key)
    return item['value'] if item else default

def set_config(key, value):
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (key, str(value)))
                conn.commit()
        finally: conn.close()
    db.table('config').upsert({'key': key, 'value': value}, Query().key == key)

def get_diary(user_id):
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM diary WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
                if row:
                    logging.info(f"Diary retrieved from PostgreSQL for user {user_id}")
                    return dict(row)
        except Exception as e:
            logging.error(f"Database diary retrieval error: {e}")
        finally: conn.close()
    
    # Fallback to TinyDB
    try:
        diary = db.table('diary').get(Query().user_id == user_id)
        if diary:
            logging.info(f"Diary retrieved from TinyDB for user {user_id}")
            return dict(diary)
    except Exception as e:
        logging.error(f"TinyDB diary retrieval error: {e}")
    
    logging.info(f"No diary found for user {user_id}, returning default")
    return {"notes": [], "last_ai_line": "Thinking of you... ✨"}

def update_diary(user_id, notes, last_ai_line):
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO diary (user_id, notes, last_ai_line) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO UPDATE SET notes = EXCLUDED.notes, last_ai_line = EXCLUDED.last_ai_line", (user_id, json.dumps(notes), last_ai_line))
                conn.commit()
                logging.info(f"Diary saved to PostgreSQL for user {user_id}")
        except Exception as e:
            logging.error(f"Database diary save error: {e}")
        finally: conn.close()
    
    # Always backup to TinyDB
    try:
        db.table('diary').upsert({
            'user_id': user_id,
            'notes': notes,
            'last_ai_line': last_ai_line
        }, Query().user_id == user_id)
        logging.info(f"Diary backed up to TinyDB for user {user_id}")
    except Exception as e:
        logging.error(f"TinyDB diary backup error: {e}")

# FLASK APP
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", secrets.token_hex(16))

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

@app.route("/")
def index():
    if session.get("admin_auth"): return render_template("index.html", user_role="admin")
    if session.get("auth"): return render_template("index.html", user_role="aradhya")
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    password = get_config('web_password', WEB_PASSWORD)
    if request.json.get("password") == password:
        session["auth"] = True
        return jsonify({"success": True})
    return jsonify({"success": False}), 401

@app.route("/chat/history")
def chat_history():
    if not session.get("auth") and not session.get("admin_auth"): return jsonify([]), 401
    return jsonify(get_messages(OWNER_ID)[-20:])

@app.route("/chat", methods=["POST"])
def chat():
    global MEMORY
    is_admin = session.get("admin_auth", False)
    is_aradhya = session.get("auth", False)
    
    if not is_admin and not is_aradhya: 
        return jsonify({"error": "No Auth"}), 401
    
    msg = request.json.get("message", "")
    user_data = get_user_data(OWNER_ID)
    memory = user_data.get('memory', "")
    
    # Full database history retrieval for total context
    full_history = get_messages(OWNER_ID, limit=None)
    recent_context = "\n".join([f"U: {m['message']}\nB: {m['response']}" for m in full_history])
    
    hour = datetime.now().hour
    time_greeting = "morning" if 5 <= hour < 12 else "afternoon" if 12 <= hour < 17 else "evening" if 17 <= hour < 21 else "night"
    
    # PREFERRED: Use memory.json admin instructions first
    admin_instructions = MEMORY.get("admin_instructions", "You are Jeet 💙, a loving and protective AI.")
    
    # Strictly follow memory.json and reference database history
    system_prompt = (
        f"{admin_instructions}\n"
        f"MANDATORY RULES:\n"
        f"1. You MUST strictly follow the behavioral rules defined in memory.json.\n"
        f"2. Reference the provided chat history to maintain continuity and avoid repeating mistakes.\n"
        f"3. Current User ID: {OWNER_ID}\n"
    )

    if is_admin:
        prompt = (f"{system_prompt} You are speaking to your Creator/Admin. Be technical, obedient, and helpful. "
                  f"Current system state: {memory}\nCommand: {msg}")
    else:
        prompt = (f"{system_prompt} It's {time_greeting}. Context: {memory}\n{recent_context}\nHer message: {msg}")

    reply = None
    try:
        if AI_CLIENTS["groq"]:
            try:
                res = AI_CLIENTS["groq"].chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"system","content":prompt}])
                reply = res.choices[0].message.content.strip()
            except Exception as e:
                logging.error(f"Groq Chat Error: {e}")

        if not reply and AI_CLIENTS["gemini"]:
            try:
                res = AI_CLIENTS["gemini"].models.generate_content(model="gemini-2.0-flash", contents=prompt)
                reply = res.text.strip()
            except Exception as e:
                logging.error(f"Gemini Chat Error: {e}")

        if not reply and AI_CLIENTS["openai"]:
            try:
                res = AI_CLIENTS["openai"].chat.completions.create(model="gpt-3.5-turbo", messages=[{"role":"system","content":prompt}], max_tokens=200)
                reply = res.choices[0].message.content.strip()
            except Exception as e:
                logging.error(f"OpenAI Chat Error: {e}")
    except Exception as e:
        logging.error(f"AI ERROR: {e}")

    if not reply: reply = "Bubu, signal weak hai... contact Jeet 🐻💖"
    
    # Always save history for OWNER_ID (Aradhya's account)
    update_user_data(OWNER_ID, (memory + f"\nU: {msg}\nB: {reply}")[-5000:], "loving")
    save_message(OWNER_ID, msg, reply)
    
    return jsonify({"reply": reply})

# DIARY & MUSIC (Simplified)
@app.route("/diary/get")
def get_diary_route():
    return jsonify(get_diary(OWNER_ID)) if (session.get("auth") or session.get("admin_auth")) else (jsonify({}), 401)

@app.route("/music/list")
def music_list():
    path = 'static/music'
    return jsonify([f for f in os.listdir(path) if f.endswith(('.mp3', '.wav', '.m4a', '.ogg'))])

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("admin_auth", None)
    return jsonify({"success": True})

@app.route("/admin_login", methods=["POST"])
def admin_login_route():
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin")
    if request.json.get("password") == admin_password:
        session["admin_auth"] = True
        session.permanent = True
        return jsonify({"success": True})
    return jsonify({"success": False}), 401

@app.route("/admin_dashboard")
def admin_dashboard_route():
    return render_template("admin.html") if session.get("admin_auth") else redirect("/")

# REPAIR / ADMIN TOOLS
@app.route("/admin/api/update", methods=["POST"])
def admin_update_api():
    if not session.get("admin_auth"): return jsonify({"success": False}), 401
    data = request.json
    if data.get("openai_api_key"): set_config('openai_api_key', data["openai_api_key"])
    if data.get("database_url"): 
        new_url = data["database_url"]
        set_config('database_url', new_url)
        os.environ["DATABASE_URL"] = new_url
        logging.info("Database URL updated. Re-initializing...")
        init_db() # This now handles the sync internally
    return jsonify({"success": True})

@app.route("/admin/music/upload", methods=["POST"])
def admin_music_upload():
    if not session.get("admin_auth"): return jsonify({"success": False}), 401
    file = request.files.get('file')
    if file:
        file.save(os.path.join(os.path.abspath('static/music'), file.filename))
        return jsonify({"success": True})
    return jsonify({"success": False}), 400

@app.route("/admin/music/delete", methods=["POST"])
def admin_music_delete():
    if not session.get("admin_auth"): return jsonify({"success": False}), 401
    fname = request.json.get("filename")
    path = os.path.join('static/music', fname)
    if os.path.exists(path): os.remove(path)
    return jsonify({"success": True})

@app.route("/admin/memory/get", methods=["GET"])
def admin_memory_get():
    global MEMORY
    if not session.get("admin_auth"): return jsonify({"error": "Unauthorized"}), 401
    MEMORY = load_memory()
    return jsonify(MEMORY)

@app.route("/admin/memory/update", methods=["POST"])
def admin_memory_update():
    global MEMORY
    if not session.get("admin_auth"): return jsonify({"success": False}), 401
    data = request.json
    MEMORY.update(data)
    MEMORY["last_updated"] = datetime.now().isoformat() + "Z"
    if save_memory(MEMORY):
        # Auto-sync to database for backup and migration
        sync_memory_to_db()
        return jsonify({"success": True, "memory": MEMORY})
    return jsonify({"success": False, "error": "Failed to save memory"}), 500

@app.route("/admin/memory/set", methods=["POST"])
def admin_memory_set():
    """Save admin instructions directly to memory.json"""
    global MEMORY
    if not session.get("admin_auth"): return jsonify({"success": False}), 401
    instructions = request.json.get("instructions", "")
    if not instructions:
        return jsonify({"success": False, "error": "Instructions required"}), 400
    
    MEMORY["admin_instructions"] = instructions
    MEMORY["last_updated"] = datetime.now().isoformat() + "Z"
    if save_memory(MEMORY):
        # Auto-sync to database
        sync_memory_to_db()
        return jsonify({"success": True, "memory": MEMORY})
    return jsonify({"success": False, "error": "Failed to save instructions"}), 500

@app.route("/admin/users", methods=["GET"])
def admin_users():
    if not session.get("admin_auth"): return jsonify({"error": "Unauthorized"}), 401
    conn = get_db_connection()
    users = []
    if conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT id, memory, mood FROM users")
                users = [dict(row) for row in cur.fetchall()]
        finally: conn.close()
    return jsonify(users)

@app.route("/admin/music/list", methods=["GET"])
def admin_music_list():
    if not session.get("admin_auth"): return jsonify({"error": "Unauthorized"}), 401
    path = 'static/music'
    files = [f for f in os.listdir(path) if f.endswith(('.mp3', '.wav', '.m4a', '.ogg'))]
    return jsonify(files)

@app.route("/admin/diary", methods=["GET"])
def admin_diary():
    if not session.get("admin_auth"): return jsonify({"error": "Unauthorized"}), 401
    return jsonify(get_diary(OWNER_ID))

@app.route("/admin/diary/delete", methods=["POST"])
def admin_diary_delete():
    if not session.get("admin_auth"): return jsonify({"success": False}), 401
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM diary WHERE user_id = %s", (OWNER_ID,))
                conn.commit()
        finally: conn.close()
    try:
        db.table('diary').remove(Query().user_id == OWNER_ID)
    except: pass
    return jsonify({"success": True})

@app.route("/admin/user/delete", methods=["POST"])
def admin_user_delete():
    if not session.get("admin_auth"): return jsonify({"success": False}), 401
    user_id = request.json.get("user_id", OWNER_ID)
    return repair_clear_user()

@app.route("/admin/user/update", methods=["POST"])
def admin_user_update():
    if not session.get("admin_auth"): return jsonify({"success": False}), 401
    data = request.json
    user_id = data.get("user_id", OWNER_ID)
    memory = data.get("memory", "")
    mood = data.get("mood", "loving")
    update_user_data(user_id, memory, mood)
    return jsonify({"success": True})

@app.route("/admin/update_password", methods=["POST"])
def admin_update_password():
    if not session.get("admin_auth"): return jsonify({"success": False}), 401
    data = request.json
    new_password = data.get("new_password")
    if new_password:
        set_config('web_password', new_password)
        return jsonify({"success": True})
    return jsonify({"success": False}), 400

@app.route("/repair/clear_user", methods=["POST"])
def repair_clear_user():
    if not session.get("admin_auth"): return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    user_id = OWNER_ID
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM messages WHERE user_id = %s", (user_id,))
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
                cur.execute("DELETE FROM diary WHERE user_id = %s", (user_id,))
                conn.commit()
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
        finally:
            conn.close()
    
    try:
        db.table('messages').remove(Query().user_id == user_id)
        db.table('users').remove(Query().id == user_id)
        db.table('diary').remove(Query().user_id == user_id)
    except: pass
    return jsonify({"success": True})

@app.route("/repair/history", methods=["GET"])
def repair_history():
    if not session.get("admin_auth"): return jsonify({"error": "Unauthorized"}), 401
    return jsonify(get_messages(OWNER_ID))

@app.route("/upload/game", methods=["POST"])
def upload_game_file():
    if not session.get("auth") and not session.get("admin_auth"): return jsonify({"success": False}), 401
    file = request.files.get('file')
    if file:
        os.makedirs('static/games', exist_ok=True)
        filename = f"{datetime.now().timestamp()}_{file.filename}"
        filepath = os.path.join('static/games', filename)
        file.save(filepath)
        
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO game_submissions (game_type, file_path) VALUES (%s, %s)", ("truth_dare", filepath))
                    conn.commit()
            finally: conn.close()
        
        db.table('game_submissions').insert({'game_type': 'truth_dare', 'file_path': filepath, 'timestamp': datetime.now().isoformat()})
        return jsonify({"success": True, "file": filename})
    return jsonify({"success": False}), 400

@app.route("/save/game-submission", methods=["POST"])
def save_game_submission():
    if not session.get("auth") and not session.get("admin_auth"): return jsonify({"success": False}), 401
    data = request.json
    game_type = data.get("type", "unknown")
    content = data.get("content", "")
    
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO game_submissions (game_type, content) VALUES (%s, %s)", (game_type, content))
                conn.commit()
        finally: conn.close()
    
    db.table('game_submissions').insert({'game_type': game_type, 'content': content, 'timestamp': datetime.now().isoformat()})
    return jsonify({"success": True})

@app.route("/admin/games/submissions", methods=["GET"])
def admin_games_submissions():
    if not session.get("admin_auth"): return jsonify([]), 401
    conn = get_db_connection()
    submissions = []
    if conn:
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM game_submissions ORDER BY timestamp DESC LIMIT 100")
                submissions = [dict(row) for row in cur.fetchall()]
        finally: conn.close()
    
    if not submissions:
        try:
            submissions = db.table('game_submissions').all()[-100:][::-1]
        except:
            pass
    
    return jsonify(submissions)

@app.route("/repair/delete_old", methods=["POST"])
def delete_old_messages():
    if not session.get("admin_auth"): return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    data = request.json or {}
    range_type = data.get("range", "all")
    user_id = OWNER_ID
    deleted_count = 0
    
    from datetime import timedelta
    
    # Calculate cutoff time based on range
    if range_type == "all":
        cutoff_time = None  # Delete all
    elif range_type == "30days":
        cutoff_time = datetime.now() - timedelta(days=30)
    elif range_type == "7days":
        cutoff_time = datetime.now() - timedelta(days=7)
    elif range_type == "1day":
        cutoff_time = datetime.now() - timedelta(days=1)
    elif range_type == "session":
        # For session, delete messages from last 30 minutes (current session)
        cutoff_time = datetime.now() - timedelta(minutes=30)
    else:
        return jsonify({"success": False, "error": "Invalid range"}), 400
    
    # Delete from database
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                if cutoff_time is None:
                    # Delete all messages
                    cur.execute("DELETE FROM messages WHERE user_id = %s", (user_id,))
                else:
                    # Delete messages older than cutoff
                    cur.execute("DELETE FROM messages WHERE user_id = %s AND timestamp < %s", (user_id, cutoff_time))
                deleted_count = cur.rowcount
                conn.commit()
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
        finally:
            conn.close()
    
    # Delete from TinyDB
    try:
        msgs = db.table('messages').all()
        for msg in msgs:
            if cutoff_time is None:
                db.table('messages').remove(Query().user_id == user_id)
            else:
                try:
                    msg_time = datetime.fromisoformat(msg.get('timestamp', ''))
                    if msg_time < cutoff_time:
                        db.table('messages').remove(Query().user_id == user_id)
                except: pass
    except: pass
    
    return jsonify({"success": True, "message": f"✅ Deleted {deleted_count} old messages! Memory is safe 💙"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
