from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from flask_wtf import CSRFProtect
import csv
import os
import json
import time

from flask_wtf.csrf import CSRFError

import shutil
from datetime import datetime, timedelta
from difflib import get_close_matches

load_dotenv()

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-secret-key")

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)

app.config["SESSION_TYPE"] = "filesystem"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=24)
csrf = CSRFProtect(app)

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    return jsonify({
        "success": False,
        "error": "CSRF token missing or invalid"
    }), 400


MAX_CONTENT_LENGTH = 16 * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

os.makedirs("data", exist_ok=True)
os.makedirs("static/images", exist_ok=True)

CONFIG_FILE = "admin_config.json"


def load_admin_config():
    """Config file se username/password load karega"""
    if not os.path.exists(CONFIG_FILE):
        default_data = {
            "username": "Admin",
            "password": "pbkdf2:sha256:600000$3IVU6XTMQtys6mbu$4e1228a029f69eeeffeb2295e5f905fdf76dc10ff3afc54ca295a1e3f0523ff7",
            "secret_code": "MasterKey2024",
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(default_data, f)
        return default_data
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except:
        return {
            "username": "Admin",
            "password": "pbkdf2:sha256:600000$3IVU6XTMQtys6mbu$4e1228a029f69eeeffeb2295e5f905fdf76dc10ff3afc54ca295a1e3f0523ff7",
            "secret_code": "MasterKey2024",
        }


def save_admin_config(data):
    """Naya password file me save karega"""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f)
        return True
    except:
        return False


def log_admin_activity(action, status):
    log_file = "data/admin_activity_logs.csv"
    file_exists = os.path.exists(log_file)

    with open(log_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow(["timestamp", "ip_address", "action", "status"])

        writer.writerow(
            [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                request.remote_addr,
                action,
                status,
            ]
        )


DATA_FILE = os.path.join("data", "college_data.json")
SYLLABUS_DB = os.path.join("data", "syllabus_metadata.json")
GALLERY_DB = os.path.join("data", "gallery_metadata.json")


def load_college_data():
    """JSON file se college info load karega"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {}


def create_backup(filepath):
    """Create backup to prevent data corruption"""
    try:
        if os.path.exists(filepath):
            backup_path = filepath + ".bak"
            shutil.copy2(filepath, backup_path)
    except Exception as e:
        print(f"Backup failed: {e}")


def save_college_data(data):
    """Save admin's new data to JSON"""
    create_backup(DATA_FILE)

    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        print(f"Save Error: {e}")
        return False


def load_syllabus_db():
    """Load syllabus metadata safely"""
    if os.path.exists(SYLLABUS_DB):
        try:
            with open(SYLLABUS_DB, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            return []
    return []


def load_gallery_db():
    if os.path.exists(GALLERY_DB):
        try:
            with open(GALLERY_DB, "r") as f:
                return json.load(f)
        except:
            return []
    return []


def save_gallery_db(data):
    create_backup(GALLERY_DB)
    try:
        with open(GALLERY_DB, "w") as f:
            json.dump(data, f, indent=4)
        return True
    except:
        return False


def save_syllabus_db(data):
    """Save new syllabus data"""
    create_backup(SYLLABUS_DB)
    try:
        with open(SYLLABUS_DB, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        print(f"Syllabus Save Error: {e}")
        return False


college_info = load_college_data()


@app.route("/admin/get-data")
def admin_get_data():
    """Admin dashboard data API"""
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify(load_college_data())


@app.route("/admin/save-data", methods=["POST"])
def admin_save_data():
    """Save admin dashboard data"""
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401

    new_data = request.json
    if save_college_data(new_data):
        global college_info
        college_info = new_data
        return jsonify({"success": True, "message": "Data updated successfully!"})

    return jsonify({"success": False, "message": "Failed to save data."}), 500


def log_data(filename, data_list, headers=None):
    """Log data to CSV file"""
    try:
        os.makedirs("data", exist_ok=True)

        path = os.path.join("data", filename)
        exists = os.path.isfile(path)
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not exists and headers:
                writer.writerow(headers)
            writer.writerow(data_list)
    except Exception as e:
        print(f"Logging error: {e}")


def find_course_by_keyword(keyword):
    k = keyword.lower().strip()
    if "ug_courses" in college_info:
        for cat in ["ug_courses", "pg_courses", "diploma_courses"]:
            if cat in college_info:
                for name, info in college_info[cat].items():
                    if k == name.lower():
                        return cat, name, info
        for cat in ["ug_courses", "pg_courses", "diploma_courses"]:
            if cat in college_info:
                for name, info in college_info[cat].items():
                    if k in name.lower() or name.lower() in k:
                        return cat, name, info
    return None, None, None


def correct_spelling(query):
    common_keywords = [
        "courses",
        "fees",
        "admission",
        "facilities",
        "hostel",
        "library",
        "sports",
        "transport",
        "incubation",
        "contact",
        "address",
        "phone",
        "bca",
        "bba",
        "bcom",
        "ba",
        "bsc",
        "msc",
        "mcom",
        "dca",
        "pgdca",
        "biotech",
        "chemistry",
        "english",
        "computer",
        "science",
        "commerce",
        "lab",
        "laboratory",
        "bus",
        "wifi",
        "internet",
        "reading",
        "room",
        "scholarship",
        "placement",
    ]

    words = query.lower().split()
    corrected = []
    suggestions = []

    for word in words:
        matches = get_close_matches(word, common_keywords, n=1, cutoff=0.7)
        if matches and matches[0] != word:
            corrected.append(matches[0])
            suggestions.append((word, matches[0]))
        else:
            corrected.append(word)

    if suggestions:
        suggestion_text = ", ".join([f"'{s[0]}' → '{s[1]}'" for s in suggestions])
        return " ".join(corrected), f"🤔 Did you mean: {suggestion_text}?"

    return query, None


def get_response(user_input):
    try:
        query = (user_input or "").lower().strip()
        current_lang = session.get("language", "Hinglish")

        corrected_query, suggestion = correct_spelling(query)
        if suggestion:
            query = corrected_query

        course_keywords = {
            "bca": "BCA",
            "bba": "BBA",
            "b.com": "B.Com",
            "bcom": "B.Com",
            "bsc biotech": "BSc Biotech",
            "biotech": "BSc Biotech",
            "biotechnology": "BSc Biotech",
            "bsc cs": "BSc CS",
            "bsc computer": "BSc CS",
            "computer science": "BSc CS",
            "bsc maths": "BSc Maths/Bio",
            "bsc bio": "BSc Maths/Bio",
            "bachelor of arts": "BA",
            "msc biotech": "MSc Biotech",
            "msc cs": "MSc CS",
            "msc computer": "MSc CS",
            "msc chemistry": "MSc Chemistry",
            "m.com": "M.Com",
            "mcom": "M.Com",
            "m.lib": "M.Lib. (ISc)",
            "mlib": "M.Lib. (ISc)",
            "library science": "M.Lib. (ISc)",
            "m.a": "M.A. (English)",
            "ma english": "M.A. (English)",
            "dca": "DCA",
            "pgdca": "PGDCA",
        }

        tokens = set([w.strip(".,!?()[]/") for w in query.split() if w.strip()])

        if any(
            w in tokens
            for w in ["hi", "hii", "hiii", "hello", "hey", "namaste", "namaskar"]
        ):
            if current_lang == "Hindi":
                return "🙏 नमस्ते! साई कॉलेज में आपका स्वागत है। मैं आपकी मदद कर सकता हूं!"
            elif current_lang == "English":
                return "👋 Hello! Welcome to Sai College. How can I help you?"
            else:
                return "👋 Hello! Sai College me aapka swagat hai. Kaise madad karu?"

        if any(w in tokens for w in ["thank", "thanks", "dhanyawad", "shukriya"]):
            return "😊 Aapka swagat hai! Kuch aur poochh sakte ho."

        if any(w in query for w in ["principal", "head", "pracharya"]):
            return (
                f"👩🏫 **Principal:** {college_info['principal']['name']}\n"
                f"🎓 Qualification: {college_info['principal']['education']}\n"
                "💡 College ke academic head hain."
            )

        if any(w in query for w in ["director", "chairman", "owner"]):
            return (
                f"👨💼 **Director:** {college_info['director']['name']}\n"
                f"🎓 Qualification: {college_info['director']['role']}\n"
                f"💬 Message: {college_info['director']['message']}"
            )

        if any(
            w in query for w in ["syllabus", "curriculum", "subject", "pdf", "pattern"]
        ):
            return (
                "📄 **Syllabus & PDF Repository**\n\n"
                "Humne sabhi courses aur semesters ke syllabus ek jagah upload kar diye hain.\n\n"
                "Neeche click karke download karein:\n"
                "👇👇👇\n"
                "<a href='/syllabus' target='_blank' style='display:inline-block; margin-top:10px; padding:10px 15px; background:#e67e22; color:white; border-radius:5px; text-decoration:none; font-weight:bold;'>📂 Open Syllabus Page</a>"
            )

        if any(
            word in query
            for word in ["transport", "bus", "vehicle", "gadi", "van", "aana jaana"]
        ):
            return f"🚌 **TRANSPORT FACILITY:**\n\n{college_info['facilities']['transport']}"

        if any(word in query for word in ["hostel", "accommodation", "stay", "rehne"]):
            return f"🏠 **HOSTEL FACILITY:**\n\n{college_info['facilities']['hostel']}"

        if any(
            word in query
            for word in ["lab", "laboratory", "computer", "internet", "wifi"]
        ):
            return f"🔬 **LAB FACILITIES:**\n\n{college_info['facilities']['labs']}"

        if any(
            word in query
            for word in [
                "library",
                "book",
                "books",
                "pustakalaya",
                "e-library",
                "reading",
            ]
        ):
            return (
                f"📚 **LIBRARY FACILITY:**\n\n{college_info['facilities']['library']}"
            )

        if any(
            word in query
            for word in ["sports", "sport", "games", "khel", "cricket", "football"]
        ):
            return (
                f"⚽ **SPORTS FACILITIES:**\n\n{college_info['facilities']['sports']}"
            )

        if any(word in query for word in ["incubation", "kalakriti", "entrepreneur"]):
            return f"🏭 **INCUBATION CENTRE:**\n\n{college_info['facilities']['incubation']}"

        facilities_keywords = ["facilities", "facility", "suvidha", "infrastructure"]
        if any(keyword in query for keyword in facilities_keywords) and "all" in query:
            return (
                "🏫 **Sai College Facilities:**\n\n"
                f"🔬 LABS\n{college_info['facilities']['labs']}\n\n"
                f"📚 LIBRARY\n{college_info['facilities']['library']}\n\n"
                f"🏠 HOSTEL\n{college_info['facilities']['hostel']}\n\n"
                f"🏃♂️ SPORTS\n{college_info['facilities']['sports']}\n\n"
                f"🚌 TRANSPORT\n{college_info['facilities']['transport']}"
            )
        elif any(keyword in query for keyword in facilities_keywords):
            return (
                "🏫 **Facilities Available:**\n\n"
                "🔬 Labs & Internet\n📚 Library & Reading Room\n🏠 Hostel\n🏃♂️ Sports\n🏭 Incubation Centre\n🚌 Bus Service\n\n"
                "💡 Details ke liye type karein: 'Bus', 'Library' ya 'Sports'."
            )

        if any(
            w in query
            for w in [
                "contact",
                "phone",
                "number",
                "mobile",
                "call",
                "email",
                "website",
                "address",
                "sampark",
                "location",
            ]
        ):
            return (
                f"📞 Contact: {college_info['phone']}\n\n"
                f"📧 Email: {college_info['email']}\n\n"
                f"🌐 Website: {college_info['website']}\n\n"
                f"📍 Address: {college_info['address']}\n\n"
                f"🗺️ Google Map: {college_info['map_link']}\n\n"
                f"🚉 Railway Station: Bhilai Nagar (200m)"
            )

        if any(
            w in query
            for w in ["about", "recognition", "accreditation", "naac", "baare", "bare"]
        ):
            img_html = '<img src="/static/images/main_gate.jpg" style="width:100%; border-radius:10px; margin-bottom:10px; border: 2px solid #fff; box-shadow: 0 4px 6px rgba(0,0,0,0.1);" alt="Sai College Main Gate"><br>'

            return (
                img_html + f"🎓 **{college_info['name']}**\n\n"
                f"📍 {college_info['address']}\n\n"
                f"⭐ {college_info['accreditation']}\n\n"
                f"👨💼 Director: {college_info['director']['name']}\n"
                f"👩🏫 Principal: {college_info['principal']['name']}\n\n"
                f"🌐 {college_info['website']}"
            )

        if "msc" in query and "biotech" in query:
            cat, name, info = find_course_by_keyword("MSc Biotech")
            if info:
                return (
                    f"🎯 {name}\n\n"
                    f"⏱️ Duration: {info['duration']}\n"
                    f"💰 Fees: {info['fee']}\n\n"
                    f"📖 {info['desc']}\n\n"
                    f"📞 Admission: {college_info['phone']}"
                )

        if "pg" in query and "dca" in query:
            cat, name, info = find_course_by_keyword("PGDCA")
            if info:
                return (
                    f"🎯 {name}\n\n"
                    f"⏱️ Duration: {info['duration']}\n"
                    f"💰 Fees: {info['fee']}\n\n"
                    f"📖 {info['desc']}\n\n"
                    f"📞 Admission: {college_info['phone']}"
                )

        if (
            query == "ba"
            or "bachelor of arts" in query
            or (query.startswith("ba ") or query.endswith(" ba"))
        ):
            cat, name, info = find_course_by_keyword("BA")
            if info:
                return (
                    f"🎯 {name}\n\n"
                    f"⏱️ Duration: {info['duration']}\n"
                    f"💰 Fees: {info['fee']}\n\n"
                    f"📖 {info['desc']}\n\n"
                    f"📞 Admission: {college_info['phone']}"
                )

        for keyword, course_name in course_keywords.items():
            if keyword in query and "incubation" not in query:
                cat, name, info = find_course_by_keyword(course_name)
                if info:
                    return (
                        f"🎯 {name}\n\n"
                        f"⏱️ Duration: {info['duration']}\n"
                        f"💰 Fees: {info['fee']}\n\n"
                        f"📖 {info['desc']}\n\n"
                        f"📞 Admission: {college_info['phone']}"
                    )

        if any(word in query for word in ["hostel", "accommodation", "stay", "rehne"]):
            return f"🏠 **HOSTEL FACILITY:**\n\n{college_info['facilities']['hostel']}"

        if any(
            word in tokens for word in ["transport", "bus", "vehicle", "gadi", "van"]
        ):
            return f"🚌 **TRANSPORT FACILITY:**\n\n{college_info['facilities']['transport']}"

        if any(word in query for word in ["lab", "laboratory", "computer"]):
            return f"🔬 **LAB FACILITIES:**\n\n{college_info['facilities']['labs']}"

        if "fee" in query or "fees" in query or "cost" in query or "kitna" in query:
            for keyword, course_name in course_keywords.items():
                if keyword in query:
                    cat, name, info = find_course_by_keyword(course_name)
                    if info:
                        return f"💰 {name}: {info['fee']} ({info['duration']})"

                if "fee" in query or "fees" in query:
                    if any(word in query for word in ["ug", "undergraduate"]):
                        text = "💰 UG Course Fees:\n\n"
                        for code, info in college_info["ug_courses"].items():
                            text += f"🎓 {code}: {info['fee']} ({info['duration']})\n"
                        return text

                    if any(word in query for word in ["pg", "postgraduate"]):
                        text = "💰 PG Course Fees:\n\n"
                        for code, info in college_info["pg_courses"].items():
                            text += f"🎓 {code}: {info['fee']} ({info['duration']})\n"
                        return text

                    if "diploma" in query:
                        text = "💰 Diploma Course Fees:\n\n"
                        for code, info in college_info["diploma_courses"].items():
                            text += f"🎓 {code}: {info['fee']} ({info['duration']})\n"
                        return text

            return "Fee category select karo!"

        if (
            any(word in query for word in ["ug", "undergraduate"])
            and "fee" not in query
        ):
            text = "🏛️ **Available Undergraduate Courses:**\n\n(Ye rahe humare sabhi UG courses)\n\n"
            for code, info in college_info["ug_courses"].items():
                text += f"🎓 **{code}**\n⏱️ Duration: {info['duration']}\n💰 Fee: {info['fee']}\n\n"
            text += "💡 Kisi bhi course ka naam type karein full details ke liye."
            return text

        if any(word in query for word in ["pg", "postgraduate"]) and "fee" not in query:
            text = "🏛️ **Available Postgraduate Courses:**\n\n(Ye rahe humare sabhi PG courses)\n\n"
            for code, info in college_info["pg_courses"].items():
                text += f"🎓 **{code}**\n⏱️ Duration: {info['duration']}\n💰 Fee: {info['fee']}\n\n"
            text += "💡 Kisi bhi course ka naam type karein full details ke liye."
            return text

        if "diploma" in query and "fee" not in query:
            text = "🏛️ **Available Diploma Courses:**\n\n(Computer & IT Diploma Courses)\n\n"
            for code, info in college_info["diploma_courses"].items():
                text += f"🎓 **{code}**\n⏱️ Duration: {info['duration']}\n💰 Fee: {info['fee']}\n\n"
            text += "💡 Kisi bhi course ka naam type karein full details ke liye."
            return text

        if "course" in query or "courses" in query:
            if not any(word in query for word in ["ug", "pg", "diploma"]):
                return "Category select karo!"

        if any(
            phrase in query
            for phrase in ["last date", "deadline", "admission kab tak", "kab tak"]
        ):
            return (
                "📅 ADMISSION LAST DATE:\n\n"
                "🗓️ Last Date: 30th June 2026\n\n"
                "⚠️ Apply soon - Limited seats!\n\n"
                f"📝 Online Form: {college_info['website']}\n"
                f"📞 Helpline: {college_info['phone']}\n\n"
                "💡 Visit college campus for offline admission too!"
            )

        if any(
            w in query
            for w in ["admission", "apply", "eligibility", "documents", "pravesh"]
        ):
            return (
                "📋 ADMISSION PROCESS:\n\n"
                "✅ ELIGIBILITY:\n"
                "• UG Courses: 10+2 pass\n"
                "• PG Courses: Graduation pass\n\n"
                "📝 PROCESS:\n"
                "1️⃣ Visit college campus\n"
                "2️⃣ Fill admission form\n"
                "3️⃣ Submit required documents\n"
                "4️⃣ Pay course fees\n\n"
                "📄 REQUIRED DOCUMENTS:\n"
                "• 10th/12th Marksheet\n"
                "• Transfer Certificate (TC)\n"
                "• Character Certificate\n"
                "• Caste Certificate (if applicable)\n"
                "• Aadhaar Card\n"
                "• Passport size photos (4-5)\n\n"
                f"📞 Contact: {college_info['phone']}\n"
                f"🌐 Website: {college_info['website']}\n\n"
                "💡 Fees instalment facility available!"
            )

        if any(
            phrase in query
            for phrase in [
                "semester",
                "yearly",
                "exam system",
                "semester system",
                "kitne semester",
                "annual",
            ]
        ):
            return (
                "📖 SEMESTER SYSTEM:\n\n"
                "✅ SEMESTER-BASED COURSES:\n"
                "🎓 UG: BCA, BBA, B.Com, BSc (Biotech/CS/Maths/Bio), BA\n"
                "🎓 PG: MSc (Biotech/CS/Chemistry), M.Com, M.A. (English)\n\n"
                "📅 PATTERN:\n"
                "• 2 Semesters per year\n"
                "• UG: Total 6 semesters (3 years)\n"
                "• PG: Total 4 semesters (2 years)\n\n"
                "📝 EXAM TYPES:\n"
                "• Mid-semester exams (internal)\n"
                "• End-semester exams (external)\n\n"
                f"📞 {college_info['phone']}"
            )

        if any(
            word in query
            for word in [
                "attendance",
                "hazri",
                "present",
                "absent",
                "75 percent",
                "attendance policy",
            ]
        ):
            return (
                "📊 Attendance Policy:\n\n"
                "✅ Minimum Required: 75%\n"
                "⚠️ If below 75%:\n"
                "- Cannot sit in exam\n"
                "- Can apply for condonation\n\n"
                "🏥 Medical Leave:\n"
                "- Medical certificate required\n\n"
                "💡 Attend classes regularly!\n\n"
                f"📞 {college_info['phone']}"
            )

        if any(
            phrase in query
            for phrase in [
                "exam pattern",
                "paper pattern",
                "marks distribution",
                "theory practical",
                "exam kaisa",
            ]
        ):
            return (
                "📝 Exam Pattern:\n\n"
                "📚 Theory Papers:\n"
                "- Internal: 30 marks\n"
                "- External: 70 marks\n"
                "- Total: 100 marks\n\n"
                "💻 Practical Papers:\n"
                "- Internal: 20 marks\n"
                "- External: 30 marks\n"
                "- Total: 50 marks\n\n"
                "📅 Exams:\n"
                "- Mid-semester exam\n"
                "- End-semester exam\n\n"
                f"📞 {college_info['phone']}"
            )

        if any(
            w in query
            for w in [
                "scholarship",
                "chhatravriti",
                "concession",
                "financial",
                "milti",
                "milta",
                "chahiye",
            ]
        ):
            return (
                "💰 SCHOLARSHIP FACILITIES:\n\n"
                "✅ GOVERNMENT SCHOLARSHIPS:\n"
                "🎓 SC/ST Scholarship\n"
                "🎓 OBC Scholarship\n"
                "🎓 EWS (Economically Weaker Section)\n\n"
                "✅ MERIT-BASED:\n"
                "🏆 75%+ marks: Fee concession\n"
                "🏆 Rank holders: Special scholarship\n\n"
                "✅ SPORTS QUOTA:\n"
                "🏃♂️ State-level players: Fee concession\n"
                "🏃♂️ National-level players: Higher concession\n\n"
                "📋 REQUIRED DOCUMENTS:\n"
                "• Caste Certificate (for SC/ST/OBC)\n"
                "• Income Certificate (for EWS)\n"
                "• Previous year marksheet\n\n"
                f"📞 Details: {college_info['phone']}"
            )

        if any(word in query for word in ["placement", "job", "career", "companies"]):
            return (
                "💼 PLACEMENT CELL:\n\n"
                "🏢 TOP COMPANIES:\n"
                "• TCS\n"
                "• Wipro\n"
                "• ICICI Bank\n"
                "• HDFC Bank\n"
                "• Mahindra Finance\n"
                "• Bajaj Finance\n\n"
                "💰 PACKAGE RANGE:\n"
                "• Average: 3-4 LPA\n"
                "• Highest: 6 LPA\n\n"
                "📚 TRAINING PROVIDED:\n"
                "• Interview Skills\n"
                "• Group Discussion\n"
                "• Personality Development\n"
                "• Resume Building\n"
                "• Aptitude Training\n\n"
                "🎯 INTERNSHIP OPPORTUNITIES:\n"
                "• Summer internships\n"
                "• Live projects\n"
                "• Industry exposure\n\n"
                f"📞 {college_info['phone']}"
            )

        if "photo" in query or "gallery" in query or "image" in query:
            return "📸 Gallery opening... Please wait!"

        log_data(
            "unknown_queries.csv",
            [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_input, "pending"],
            headers=["timestamp", "query", "status"],
        )

        if suggestion:
            return (
                suggestion
                + "\n\n❓ You can ask: Courses, Fees, Facilities, Admission, Contact"
            )

        return (
            "😊 Sorry, I didn't understand your question.\n\n"
            "You can ask these questions:\n\n"
            "📍 What is the college address?\n"
            "📞 What is the contact number?\n"
            "💰 How much is BCA fees?\n"
            "📚 What courses are available?\n"
            "🚌 Is there bus facility?\n"
            "⚽ What sports facilities are there?\n"
            "📊 What is attendance policy?\n"
            "📅 When is admission last date?\n\n"
            "Or ask your question in simple words again! 🙏"
        )
    except Exception as e:
        print(f"Error in get_response: {e}")
        return "⚠️ Internal Error. Please try again."


@app.route("/")
def home():
    return render_template("index.html", college_info=college_info)


@csrf.exempt
@app.route("/chat", methods=["POST"])
def chat():
    try:
        user_message = request.json.get("message", "")
        response = get_response(user_message)
        log_data(
            "chat_logs.csv",
            [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                user_message,
                response[:100],
                request.headers.get("User-Agent", "Unknown"),
            ],
            headers=["timestamp", "user_message", "bot_response", "user_agent"],
        )
        return jsonify({"response": response})
    except Exception as e:
        print(f"⚠️ Chat error: {e}")
        return jsonify({"response": "Something went wrong, please try again."}), 500


@app.route("/set-language", methods=["POST"])
def set_language():
    try:
        data = request.json
        language = data.get("language", "Hinglish")
        session["language"] = language

        if language == "Hindi":
            welcome_msg = "🙏 नमस्ते! साई कॉलेज में स्वागत है। मैं आपकी मदद कर सकता हूं।"
        elif language == "English":
            welcome_msg = "👋 Hello! Welcome to Sai College. How can I help you?"
        else:
            welcome_msg = "🙏 Namaste! Sai College me swagat hai. Kaise madad karu?"

        return jsonify({"success": True, "message": welcome_msg})
    except Exception as e:
        print(f"⚠️ Language error: {e}")
        return jsonify(
            {"success": True, "message": "👋 Namaste! Sai College me swagat hai."}
        )


@app.route("/feedback", methods=["POST"])
def feedback():
    data = request.get_json()

    if not data:
        return jsonify({"error": "No JSON received"}), 400

    feedback_type = data.get("type")
    message = data.get("message")
    rating = data.get("rating")

    if not feedback_type or not message or not rating:
        return jsonify({"error": "Missing fields"}), 400

    feedback_type = data.get("type")
    message = data.get("message")
    rating = data.get("rating")

    # validation
    if not feedback_type or not message or not rating:
        return jsonify({"error": "Missing fields"}), 400

    # DEBUG print (important)
    print(feedback_type, message, rating)

    # TODO: database insert here

    feedback_file = "data/feedback.json"

    feedback_entry = {
        "id": int(time.time() * 1000),  # UNIQUE ID
        "date": datetime.now().strftime("%d %b %Y %I:%M %p"),
        "type": feedback_type,
        "message": message,
        "rating": rating,
        "status": "new",
    }

    if not os.path.exists(feedback_file):
        # ensure file exists
        with open(feedback_file, "w") as f:
            json.dump([], f)

    # read existing feedback
    with open(feedback_file, "r") as f:
        feedback_list = json.load(f)

    # add new feedback at top
    feedback_list.insert(0, feedback_entry)

    # save back to file
    with open(feedback_file, "w") as f:
        json.dump(feedback_list, f, indent=2)

    return jsonify({"success": True}), 200


def admin_required():
    if not session.get("admin"):
        return False
    return True


@app.route("/admin")
def adminloginpage():
    if not session.get("admin"):
        print("✅ Already logged in - redirecting to dashboard")
        return render_template("admin.html")

    return render_template("admin.html")


@app.route("/admin/get-college-data", methods=["GET"])
def get_college_data():
    try:
        if not session.get("admin"):
            return jsonify({"success": False, "message": "Unauthorized"}), 401

        filepath = os.path.join("data", "college_data.json")

        if not os.path.exists(filepath):
            return jsonify({"success": False, "message": "File not found"}), 404

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        return jsonify({"success": True, "data": data})

    except Exception as e:
        print("get_college_data error:", e)
        return jsonify({"success": False, "error": str(e)}), 500


@csrf.exempt
@app.route("/adminlogin", methods=["POST", "OPTIONS"])
def adminlogin():
    if request.method == "OPTIONS":
        return jsonify({"success": True}), 200

    try:
        log_admin_activity("TEST", "MANUAL")
        data = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()

        current_config = load_admin_config()

        print(f"🔐 Login attempt: '{username}'")

        # Success login
        if username == current_config.get("username") and check_password_hash(
            current_config.get("password", ""), password
        ):
            session.clear()
            session["admin"] = True
            session["login_attempts"] = 0
            session.modified = True
            log_admin_activity("LOGIN", "SUCCESS")
            print("✅ Login successful")
            return jsonify({"success": True, "redirect": "/admin"}), 200

        # Invalid login
        if request.method == "POST":
            session["login_attempts"] = session.get("login_attempts", 0) + 1

        if session["login_attempts"] >= 5:
            log_admin_activity("LOGIN", "BLOCKED")
            return (
                jsonify(
                    {"success": False, "message": "Too many attempts. Try again later."}
                ),
                403,
            )

        log_admin_activity("LOGIN", "FAILED")
        print("❌ Invalid credentials")
        return jsonify({"success": False, "message": "Invalid credentials"}), 200

    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        return jsonify({"success": False, "message": "Server error"}), 500

    # This was missing - added it


@app.route("/admincheck-session")
def check_session():
    return jsonify({"loggedin": bool(session.get("admin"))})


@app.route("/admin/reset-password", methods=["POST"])
def reset_password():
    try:
        data = request.get_json()
        secret_code = data.get("secret_code", "").strip()
        new_password = data.get("new_password", "").strip()

        current_config = load_admin_config()

        # Check karo ki Master Code sahi hai ya nahi
        if secret_code == current_config.get("secret_code", "MasterKey2024"):
            # Password update karo
            current_config["password"] = new_password
            if save_admin_config(current_config):
                return jsonify(
                    {"success": True, "message": "Password updated successfully!"}
                )
            else:
                return jsonify({"success": False, "message": "Failed to save file."})
        else:
            return jsonify({"success": False, "message": "Invalid Secret Code!"})

    except Exception as e:
        print(f"Reset Error: {e}")
        return jsonify({"success": False, "message": "Server Error"}), 500


@app.route("/admin/dashboard")
def admin_dashboard():
    """Admin dashboard with session check"""
    print(f"🔍 Session check: {session.get('admin')}")  # Debug print
    if not session.get("admin"):
        print("❌ Unauthorized access")  # Debug print
        return (
            render_template(
                "error.html",
                error_code=401,
                error_message="Please login first",
                college_info=college_info,
            ),
            401,
        )
    print("✅ Dashboard access granted")  # Debug print
    return render_template("admin.html", college_info=college_info)


@app.route("/adminfeedback")
def admin_feedback():
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        path = os.path.join("data", "feedback.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                feedback_list = json.load(f)
            return jsonify({"feedback": feedback_list})
        else:
            return jsonify({"feedback": []})
    except Exception as e:
        print("Admin feedback load error:", e)
        return jsonify({"error": "Error loading feedback"}), 500


@app.route("/adminunknown-queries")  # Correct URL
def admin_queries():
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401

    try:
        path = os.path.join("data", "unknown_queries.csv")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return jsonify({"queries": list(csv.DictReader(f))[::-1]})
        return jsonify({"queries": []})
    except Exception as e:
        return jsonify({"error": "Error loading queries"}), 500


@app.route("/adminlogout")
def admin_logout():
    session.clear()
    return redirect("/")


# Public APIs
@app.route("/api/college-info")
def api_college_info():
    return jsonify(
        {
            "name": college_info["name"],
            "address": college_info["address"],
            "phone": college_info["phone"],
            "email": college_info["email"],
            "website": college_info["website"],
            "map_link": college_info["map_link"],
        }
    )


@app.route("/api/courses")
def api_courses():
    return jsonify(
        {
            "undergraduate": college_info["ug_courses"],
            "postgraduate": college_info["pg_courses"],
            "diploma": college_info["diploma_courses"],
        }
    )


@app.route("/api/facilities")
def api_facilities():
    return jsonify(college_info["facilities"])


# Error Handlers
@app.errorhandler(404)
def not_found_error(error):
    return (
        render_template(
            "error.html",
            error_code=404,
            error_message="Page not found",
            college_info=college_info,
        ),
        404,
    )


@app.errorhandler(500)
def internal_error(error):
    import traceback

    print("--- 500 Error ---")
    traceback.print_exc()
    return (
        render_template(
            "error.html",
            error_code=500,
            error_message="Server error",
            college_info=college_info,
        ),
        500,
    )


basedir = os.path.abspath(os.path.dirname(__file__))
PDF_FOLDER = os.path.join(basedir, "static", "pdfs")


@csrf.exempt
@app.route("/admin/upload-pdf", methods=["POST"])
def upload_pdf():
    if not session.get("admin"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file selected"})

    file = request.files["file"]
    course = request.form.get("course", "General")
    semester = request.form.get("semester", "N/A")
    category = request.form.get("category", "syllabus")  # ✅ New: Syllabus ya Note

    if file.filename == "":
        return jsonify({"success": False, "message": "Empty filename"})

    if file:
        try:
            if not os.path.exists(PDF_FOLDER):
                os.makedirs(PDF_FOLDER)

            # Filename clean karo
            clean_name = secure_filename(file.filename)

            # ✅ Agar Note hai toh filename me pehchan daal do (Old frontend compatibility ke liye)
            if category == "notes" and "note" not in clean_name.lower():
                clean_name = f"Note_{clean_name}"

            save_path = os.path.join(PDF_FOLDER, clean_name)
            file.save(save_path)

            # Database Update
            current_db = load_syllabus_db()

            # Duplicate hatao
            current_db = [item for item in current_db if item["filename"] != clean_name]

            new_entry = {
                "filename": clean_name,
                "course": course,
                "semester": semester,
                "category": category,  # ✅ Category save kar rahe hain
                "uploaded_at": datetime.now().strftime("%Y-%m-%d"),
            }
            current_db.append(new_entry)
            save_syllabus_db(current_db)

            return jsonify(
                {
                    "success": True,
                    "message": f"{category.title()} Uploaded Successfully!",
                }
            )

        except Exception as e:
            return jsonify({"success": False, "message": f"Server Error: {str(e)}"})

    return jsonify({"success": False, "message": "Upload failed"})


@app.route("/admin/list-pdfs")
def list_pdfs():
    """Folder me jitni PDF hain unki list JSON db ke saath bhejega"""
    if not session.get("admin"):
        return jsonify({"error": "Unauthorized"}), 401

    # 1. DB se data load karo
    db_data = load_syllabus_db()

    # 2. Cross check: Sirf wahi dikhao jo folder me actually exist karti hain
    valid_data = []
    if os.path.exists(PDF_FOLDER):
        actual_files = set(os.listdir(PDF_FOLDER))
        for item in db_data:
            # Agar file folder me hai, tabhi list me dikhao
            if item["filename"] in actual_files:
                valid_data.append(item)

    # Frontend ko bhej do
    return jsonify({"files": valid_data})


@csrf.exempt
@app.route("/admin/delete-gallery-image", methods=["POST"])
def delete_gallery_image():
    if not session.get("admin"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    data = request.get_json()
    filename = data.get("filename")

    if not filename:
        return jsonify({"success": False, "message": "Filename missing"}), 400

    # Delete file from static folder
    file_path = os.path.join(app.static_folder, "images", "gallery", filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    # Delete from gallery DB (JSON)
    db = load_gallery_db()
    db = [img for img in db if img.get("filename") != filename]
    save_gallery_db(db)

    return jsonify({"success": True})


@csrf.exempt
@app.route("/admin/delete-pdf", methods=["POST"])
def delete_pdf():
    if not session.get("admin"):
        return jsonify(success=False, message="Unauthorized"), 401

    data = request.get_json(force=True)
    filename = data.get("filename")

    if not filename:
        return jsonify(success=False, message="Filename missing"), 400

    if ".." in filename or "/" in filename or "\\" in filename:
        return jsonify(success=False, message="Invalid filename"), 400

    try:
        file_path = os.path.join(app.root_path, "static", "pdfs", filename)

        if not os.path.exists(file_path):
            return jsonify(success=False, message="File not found"), 404

        os.remove(file_path)

        # remove from DB
        current_db = load_syllabus_db()
        new_db = [item for item in current_db if item.get("filename") != filename]
        save_syllabus_db(new_db)

        return jsonify(success=True, message="File deleted successfully")

    except Exception as e:
        print("DELETE ERROR:", e)
        return jsonify(success=False, message=str(e)), 500


@app.route("/syllabus")
def syllabus_page():
    data = load_syllabus_db()

    print(f"DEBUG: Found {len(data)} files in database.")

    return render_template("syllabus.html", files=data)


@app.route("/admin/get-stats")
def get_stats():
    if not session.get("admin"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    stats = {
        "total_queries": 0,
        "resolved_queries": 0,
        "pending_queries": 0,
        "recent_feedback": [],
    }

    # Feedback queries load karne ka logic
    feedback_file = "data/feedback_queries.csv"
    if os.path.exists(feedback_file):
        try:
            with open(feedback_file, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

                stats["total_queries"] = len(rows)
                # Resolved count (Agar status column use kar rahe ho)
                stats["resolved_queries"] = len(
                    [r for r in rows if r.get("status") == "Resolved"]
                )
                stats["pending_queries"] = (
                    stats["total_queries"] - stats["resolved_queries"]
                )

                # Latest 10 feedback table ke liye
                for row in reversed(rows[-10:]):
                    stats["recent_feedback"].append(
                        {
                            "user": row.get("name", "Anonymous"),
                            "query": row.get("query", "No Message"),
                            "time": row.get("timestamp", "N/A"),
                            "status": row.get("status", "Pending"),
                        }
                    )
        except Exception as e:
            print(f"Error loading stats: {e}")

    return jsonify(stats)


GALLERY_FOLDER = os.path.join("static", "images", "gallery")
os.makedirs(GALLERY_FOLDER, exist_ok=True)


@csrf.exempt
@app.route("/admin/upload-gallery-image", methods=["POST"])
def upload_gallery_image():
    if not session.get("admin"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    if "gallery_file" not in request.files:
        return jsonify({"success": False, "message": "No file part"})

    file = request.files["gallery_file"]
    raw_category = request.form.get("category", "campus").lower()

    if "campus" in raw_category:
        category = "campus"
    elif "event" in raw_category:
        category = "events"
    elif "lab" in raw_category:
        category = "labs"
    elif "sport" in raw_category:
        category = "sports"
    else:
        category = "campus"

    if file.filename == "":
        return jsonify({"success": False, "message": "No selected file"})

    if file:
        try:
            # NEW: Safety check to ensure directory exists before saving
            os.makedirs(GALLERY_FOLDER, exist_ok=True)

            filename = secure_filename(f"img_{int(time.time())}_{file.filename}")
            file_path = os.path.join(GALLERY_FOLDER, filename)
            file.save(file_path)

            # ✅ Metadata Save Karo
            db = load_gallery_db()
            db.append(
                {
                    "filename": filename,
                    "category": category,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
            )
            save_gallery_db(db)

            return jsonify({"success": True, "message": "Image Uploaded Successfully!"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})

    return jsonify({"success": False, "message": "Unknown error"})


@app.route("/admin/get-unknown-queries")
def get_unknown_queries():
    if not session.get("admin"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    queries = []
    file_path = "data/unknown_queries.csv"
    if os.path.exists(file_path):
        with open(file_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                queries.append(row)
    return jsonify(queries[::-1])  # Taki nayi queries upar dikhen


@app.route("/gallery")
def gallery_page():
    return render_template("gallery.html")


@app.route("/admin/gallery-manager")
def admin_gallery_manager():
    if not session.get("admin"):
        return redirect("/admin-login")

    response = get_gallery_images()
    images = response.get_json()

    return render_template("admin_gallery.html", images=images)


@app.route("/api/gallery-images")
def get_gallery_images():
    images = []
    import os

    gallery_path = os.path.join(app.static_folder, "images", "gallery")

    if not os.path.exists(gallery_path):
        os.makedirs(gallery_path)

    images = []
    try:
        for filename in os.listdir(gallery_path):
            if filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):

                name_lower = filename.lower()

                if any(
                    x in name_lower
                    for x in [
                        "campus",
                        "gate",
                        "college",
                        "building",
                        "class",
                        "hostel",
                        "canteen",
                        "cafe",
                        "drone",
                        "infra",
                        "view",
                    ]
                ):
                    category = "campus"

                elif any(
                    x in name_lower
                    for x in [
                        "lab",
                        "computer",
                        "science",
                        "workshop",
                        "physics",
                        "chem",
                    ]
                ):
                    category = "labs"

                elif any(
                    x in name_lower
                    for x in [
                        "sport",
                        "cricket",
                        "football",
                        "game",
                        "play",
                        "badminton",
                    ]
                ):
                    category = "sports"

                elif any(x in name_lower for x in ["lib", "book", "read"]):
                    category = "library"

                elif any(
                    x in name_lower
                    for x in [
                        "event",
                        "function",
                        "fest",
                        "cultural",
                        "dance",
                        "music",
                        "seminar",
                        "award",
                    ]
                ):
                    category = "events"

                else:
                    parts = filename.split("_")
                    if len(parts) >= 3:
                        category = parts[2]
                    else:
                        category = "events"

                images.append({"filename": filename, "category": category})

        # Newest pehle
        images.sort(key=lambda x: x["filename"], reverse=True)
    except Exception as e:
        print(f"Error reading gallery: {e}")

    return jsonify(images)


@app.route("/delete-syllabus", methods=["POST"])
def delete_syllabus():
    try:
        data = request.json
        c_id = data.get("id")

        college_data = load_college_data()

        target_course = None
        for c in college_data.get("courses", []):
            if str(c.get("id")) == str(c_id):
                target_course = c
                break

        if not target_course:
            return jsonify({"success": False, "message": "Course not found"})

        filename = target_course.get("syllabus", "")
        if filename:
            file_path = os.path.join(app.static_folder, "pdfs", filename)
            if os.path.exists(file_path):
                os.remove(file_path)

        target_course["syllabus"] = ""

        save_college_data(college_data)

        return jsonify({"success": True, "message": "Syllabus deleted successfully!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

def load_feedback_data():
    path = os.path.join("data", "feedback.json")

    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_unknown_queries():
    path = os.path.join("data", "unknown_queries.csv")

    if not os.path.exists(path):
        return []

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)

@csrf.exempt
@app.route("/admin/update-status", methods=["POST"])
def update_status():
    if not session.get("admin"):
        return jsonify(success=False, message="Unauthorized"), 401

    data = request.get_json()
    item_type = data.get("type")
    new_status = data.get("status")
    raw_index = data.get("index")
    index = int(raw_index) if isinstance(raw_index, (int, str)) and str(raw_index).isdigit() else None


    # ---------- FEEDBACK ----------
    if item_type == "feedback":
        path = os.path.join("data", "feedback.json")
        feedback_list = load_feedback_data()

        if index is None or index < 0 or index >= len(feedback_list):
            return jsonify(success=False, message="Item not found"), 404

        feedback_list[index]["status"] = new_status
        found = True


        with open(path, "w", encoding="utf-8") as f:
            json.dump(feedback_list, f, indent=2)

        return jsonify(success=True)

        # ---------- UNKNOWN QUERIES ----------
    elif item_type == "query":
        path = os.path.join("data", "unknown_queries.csv")
        rows = load_unknown_queries()  # returns list(dict)

        # look up by unique timestamp sent from frontend
    found = False
    if index is None:
        return jsonify(success=False, message="Invalid index"), 400

    if index < 0 or index >= len(rows):
        return jsonify(success=False, message="Item not found"), 404


    rows[index]["status"] = new_status
    found = True

    if not found:
        return jsonify(success=False, message="Item not found"), 404

        # save CSV back (preserve header order)
    with open(path, "w", newline="", encoding="utf-8") as f:
            # ensure fieldnames match CSV header order
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

            return jsonify(success=True)

    return jsonify(success=False, message="Invalid type"), 400

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    return "Session expired. Please refresh the page and try again.", 400

if __name__ == "__main__":
    print("🎓 Sai College Chatbot Starting...")
    app.run(debug=True, host="0.0.0.0", port=5000)
