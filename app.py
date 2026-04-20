"""
KCHL-J Blood Bank Help Center
Stack: Python + Streamlit + Google Gemini
Fixed Professional Light Theme
"""

import streamlit as st
import google.generativeai as genai
import re
import os
import html
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="KCHL-J Blood Bank Help Center",
    page_icon="🩸",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────
#  API KEY ROTATION
# ─────────────────────────────────────────
@st.cache_resource
def load_key_manager():
    keys = []
    for i in range(1, 11):
        k = os.getenv(f"GEMINI_API_KEY_{i}")
        if k:
            keys.append(k)
    if not keys:
        k = os.getenv("GEMINI_API_KEY")
        if k:
            keys.append(k)
    if not keys:
        st.error("⚠️ No Gemini API key found. Set GEMINI_API_KEY in .env")
        st.stop()
    return {"keys": keys, "idx": 0, "failed": set()}

def get_gemini_response(prompt: str) -> str:
    km = load_key_manager()
    keys = km["keys"]
    for attempt in range(len(keys)):
        idx = (km["idx"] + attempt) % len(keys)
        try:
            genai.configure(api_key=keys[idx])
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(prompt)
            km["idx"] = idx
            if hasattr(response, "text") and response.text:
                return response.text.strip()
        except Exception as e:
            err = str(e).lower()
            if any(x in err for x in ["quota", "limit", "invalid", "auth"]):
                km["failed"].add(idx)
            continue
    return "⚠️ All API keys exhausted. Please try again later."

# ─────────────────────────────────────────
#  SYSTEM PROMPT
# ─────────────────────────────────────────
SYSTEM_PROMPT = """You are the KCHL-J Blood Bank Clinical Decision Support Assistant for King's College Hospital London – Jeddah. Answer questions using KCHL-J blood bank policies. Always cite the specific policy number. For clinical questions ask for: patient age, weight, diagnosis, clinical indication, Hb, Plt, PT/APTT/INR, Fibrinogen. If asked in Arabic, respond fully in Arabic. Be structured, concise, and cite policies.

═══ KEY KCHL-J BLOOD BANK POLICIES ═══

【IPP-LB-02-032 Ordering Blood Products】
- All blood products ordered through TrakCare by authorized Physicians only.
- TrakCare: Login → Episode Enquiry → URN → Find → Click URN → Dots → Order → Search product → Fill form → Confirm password → Update.
- Pre-transfusion: ABO/Rh typing (2 nurses, initials+ID on tube), Antibody Screening. Specimen valid 72h (collection day = day zero).
- EMR downtime: use manual Blood Component Request Form.

【IPP-LB-02-035 Emergency Release】
- Blood Bank ext: 2125. Physician calls and fills Emergency Blood Release Request Form.
- O Negative within 5-10 min if ABO unknown. Prefer Rh-neg for females of childbearing potential.
- Group-specific within 5-10 min with sample. Max 2 O Neg units without crossmatch.
- Keep segment of each unit for 7 days. Consider Anti-D Ig for Rh-neg females.

【IPP-LB-02-070 Major Transfusion Protocol (MTP)】
- Activate: (1) TrakCare order "Massive Transfusion Protocol MTP1/MTP2" AND (2) Call ext.2125 "I want to activate the Massive Transfusion Protocol".
- Provide: Patient URN, location, ext, neonatal/pediatric/obstetric status.
- MTP Pack: 4 RBC + 4 FFP + 1 adult dose platelets. Ratio 1:1 RBC:FFP.
- FFP thawing: 20-30 minutes — must be specifically requested.
- O D POSITIVE must NOT be given to females of childbearing potential with unknown group.
- Pediatric: 10ml/kg aliquots. D neg, K neg for all children. Universal groups up to 12 months.

【IPP-LB-02-093 Blood Group Selection】
- TWO tests on TWO different samples before type-specific issue. Otherwise: O PRBC or AB FFP/Platelets.
- PRBC compatibility: O→O; A→A,O; B→B,O; AB→any.
- FFP: O→O,A,B,AB; A→A,AB; B→B,AB; AB→AB.
- Rh-neg reserved for: D-neg females of childbearing potential and unknown type emergencies.
- Inadvertent D+ to D-neg female: <15ml→IM anti-D; >15ml→IV anti-D 1500-2500 IU.

【IPP-LB-02-068 Neonatal Transfusion】
- Select blood compatible with BOTH baby AND mother. Irradiate if <1200g. HbS negative.
- PRBC thresholds (TOP trial, VLBW ≤1000g, <36wk PMA):
  Week 1: Resp support Hb<11; No support Hb<10
  Week 2: Resp Hb<10; No resp Hb<8.5
  ≥Week 3: Resp Hb<8.5; No resp Hb<7
- Platelet thresholds: Active bleed/surgery/VLBW≤30wk first 72h: <50,000; Others: <25,000.
- FFP thresholds: PT >1.5x mid-normal, aPTT >1.5x upper, INR >1.7.
- Cryoprecipitate: fibrinogen <100 mg/dL with bleeding/procedure.

【IPP-LB-02-036 Transfusion Reaction】
- STOP transfusion immediately. Report via eCellz.
- Collect: blood bag+set, post-transfusion EDTA+plain red top, first voided urine.
- Workup: Clerical check → Visual → DAT → ABO/Rh → Antibody screen → Crossmatch.
- AHTR labs: LDH, bilirubin, haptoglobin, PT, PTT, BUN, creatinine, fibrinogen, platelets.
- Notify SFDA for serious adverse reactions.

【IPP-LB-02-031 Handling/Storage (Nursing)】
- PRBC: 1-6°C. Outside >30 min = dispose. Initiate within 30 min of leaving Blood Bank.
- Platelets: 20-24°C with agitation. Never refrigerate.
- FFP: -18°C. Thawed: 1-6°C, use within 24h.
- Pre-transfusion: 2 nurses verify ID, baseline vitals. Start slowly 2mL/min first 15 min.
- Vitals: pre, 15-min, hourly, at completion, 30-min post.
- Only 0.9% NaCl with blood line.

Always format with clear headings and cite the specific IPP-LB-02-XXX policy number.
"""

# ─────────────────────────────────────────
#  DATA
# ─────────────────────────────────────────
QUICK_ACTIONS = [
    ("🚨", "MTP Activation", "#dc2626",
     "How do I activate the Massive Transfusion Protocol (MTP) at KCHL-J? Give me the complete step-by-step procedure including phone extension, TrakCare ordering, MTP pack contents, team roles, and the 1:1 ratio protocol."),
    ("🆘", "Emergency Release", "#ea580c",
     "What is the complete emergency release procedure at KCHL-J? Include timelines for O Negative, group-specific, and crossmatched blood. What forms are needed? What about females of childbearing potential?"),
    ("⚠️", "Transfusion Reaction", "#d97706",
     "A patient is having a suspected transfusion reaction. What are the immediate nursing and medical steps? What samples to collect? What is the complete blood bank workup protocol?"),
    ("📋", "TrakCare Ordering", "#2563eb",
     "Give me a complete step-by-step guide to ordering blood products in TrakCare at KCHL-J. Include login, finding patient, selecting products, mandatory fields, and confirmation steps."),
    ("👶", "Neonatal Transfusion", "#7c3aed",
     "What are the complete neonatal transfusion guidelines at KCHL-J? Include PRBC thresholds (TOP trial), platelet thresholds (PlaNeT2), FFP thresholds, compatibility with mother, irradiation, and HbS."),
    ("🔬", "Compatibility Rules", "#059669",
     "Explain the complete blood compatibility and selection rules at KCHL-J. Include ABO/Rh tables for PRBC, FFP, and Platelets. What is the two-sample rule?"),
]

STAT_CARDS = [
    ("📞", "Blood Bank Ext.", "2125", "#fef2f2", "#dc2626"),
    ("⏱️", "O-Neg Release", "5–10 min", "#fff7ed", "#ea580c"),
    ("🧪", "Sample Validity", "72 Hours", "#fefce8", "#ca8a04"),
    ("🩸", "MTP Pack Ratio", "1:1 RBC:FFP", "#f0fdf4", "#16a34a"),
]

POLICIES = [
    ("032", "Ordering Blood Products"),
    ("033", "Transfusion Process"),
    ("035", "Emergency Release"),
    ("036", "Transfusion Reactions"),
    ("068", "Neonatal Transfusion"),
    ("070", "MTP Protocol"),
    ("071", "Transfusion Guidelines"),
    ("080", "Quarantine Release"),
    ("081", "Return Unused Blood"),
    ("093", "Blood Group Selection"),
]

# ─────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────
def is_rtl(text: str) -> bool:
    rtl_chars = len(re.findall(r'[\u0600-\u06FF\u0750-\u077F]', text))
    total = len(re.sub(r'\s', '', text))
    return total > 0 and rtl_chars / total > 0.3

def build_prompt(user_input: str) -> str:
    history_text = "\n".join(
        f"User: {m['content']}" if m["role"] == "user" else f"AI: {m['content']}"
        for m in st.session_state.messages[-10:]
    )
    rtl = is_rtl(user_input)
    lang_instruction = (
        "⚠️ User is writing in Arabic/Urdu. Respond ENTIRELY in Arabic/Urdu. Do not mix languages."
        if rtl else
        "User is writing in English. Respond in clear professional English with markdown formatting."
    )
    return f"{SYSTEM_PROMPT}\n\n{lang_instruction}\n\nConversation:\n{history_text}\n\nUser: {user_input}\n\nAI:"

def send_message(user_input: str):
    user_input = user_input.strip()
    if not user_input:
        return
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.spinner("Thinking..."):
        reply = get_gemini_response(build_prompt(user_input))
    st.session_state.messages.append({"role": "assistant", "content": reply})

# ─────────────────────────────────────────
#  SESSION STATE
# ─────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

# ─────────────────────────────────────────
#  GLOBAL CSS
# ─────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif !important;
    background-color: #f8fafc !important;
    color: #1e293b !important;
}
.block-container { padding: 0 !important; max-width: 100% !important; }
header[data-testid="stHeader"] { background: transparent !important; }
.stDeployButton, footer { display: none !important; }

::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 8px; }

/* Navbar */
.navbar {
    background: #ffffff;
    border-bottom: 1px solid #e2e8f0;
    padding: 0 28px;
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.nav-brand { display: flex; align-items: center; gap: 12px; }
.nav-logo {
    width: 38px; height: 38px;
    background: linear-gradient(135deg, #dc2626, #991b1b);
    border-radius: 9px;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px;
}
.nav-title { font-size: 15px; font-weight: 700; color: #0f172a; line-height: 1.2; }
.nav-sub   { font-size: 11px; color: #64748b; }
.nav-badge {
    background: #fef2f2; border: 1px solid #fecaca;
    color: #dc2626; padding: 4px 12px;
    border-radius: 20px; font-size: 12px; font-weight: 600;
}

/* Stat cards */
.stat-card {
    display: flex; align-items: center; gap: 10px;
    padding: 9px 12px; border-radius: 10px; margin-bottom: 5px;
}
.stat-label { font-size: 10px; color: #64748b; font-weight: 500; }
.stat-value { font-size: 13px; font-weight: 700; }

/* Quick action buttons */
.stButton > button {
    background: #ffffff !important;
    color: #1e293b !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
    padding: 9px 14px !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    font-family: 'Inter', sans-serif !important;
    cursor: pointer !important;
    transition: all 0.15s !important;
    width: 100% !important;
    text-align: left !important;
    box-shadow: none !important;
}
.stButton > button:hover {
    background: #f8fafc !important;
    border-color: #cbd5e1 !important;
    transform: translateX(2px) !important;
}

/* Send button override */
div[data-testid="column"]:nth-child(2) .stButton > button {
    background: linear-gradient(135deg, #dc2626, #b91c1c) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    box-shadow: 0 2px 8px rgba(220,38,38,0.3) !important;
}
div[data-testid="column"]:nth-child(2) .stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(220,38,38,0.4) !important;
}

/* Clear button */
div[data-testid="column"]:nth-child(3) .stButton > button {
    background: #f1f5f9 !important;
    color: #64748b !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: none !important;
}
div[data-testid="column"]:nth-child(3) .stButton > button:hover {
    background: #e2e8f0 !important;
    transform: none !important;
}

/* Text input */
.stTextInput > div > div > input {
    background: #f8fafc !important;
    border: 1.5px solid #e2e8f0 !important;
    border-radius: 10px !important;
    padding: 11px 16px !important;
    font-size: 13.5px !important;
    font-family: 'Inter', sans-serif !important;
    color: #1e293b !important;
}
.stTextInput > div > div > input:focus {
    border-color: #dc2626 !important;
    box-shadow: 0 0 0 3px rgba(220,38,38,0.08) !important;
    background: #fff !important;
}
.stTextInput > div > div > input::placeholder { color: #94a3b8 !important; }

/* Spinner */
.stSpinner > div { border-top-color: #dc2626 !important; }

/* Chat message containers - user */
.user-msg-container {
    display: flex;
    justify-content: flex-end;
    margin: 10px 0;
    padding: 0 8px;
}
.user-bubble {
    background: linear-gradient(135deg, #dc2626, #b91c1c);
    color: white;
    border-radius: 16px 4px 16px 16px;
    padding: 11px 16px;
    max-width: 70%;
    font-size: 13.5px;
    line-height: 1.6;
    box-shadow: 0 2px 8px rgba(220,38,38,0.2);
    word-wrap: break-word;
}

/* Bot message */
.bot-msg-container {
    display: flex;
    justify-content: flex-start;
    margin: 10px 0;
    padding: 0 8px;
    gap: 10px;
    align-items: flex-start;
}
.bot-avatar {
    width: 32px; height: 32px;
    background: linear-gradient(135deg, #dc2626, #991b1b);
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px;
    flex-shrink: 0;
    margin-top: 2px;
}
.bot-bubble {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 4px 16px 16px 16px;
    padding: 11px 16px;
    max-width: 75%;
    font-size: 13.5px;
    line-height: 1.65;
    color: #1e293b;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    word-wrap: break-word;
}
.bot-name {
    font-size: 9px;
    font-weight: 700;
    color: #dc2626;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin-bottom: 4px;
}

/* Welcome card */
.welcome-card {
    background: linear-gradient(135deg, #fff5f5, #fff);
    border: 1px solid #fecaca;
    border-radius: 14px;
    padding: 20px 22px;
    margin-bottom: 20px;
}
.welcome-title { font-size: 15px; font-weight: 700; color: #0f172a; margin-bottom: 6px; }
.welcome-sub   { font-size: 12.5px; color: #475569; line-height: 1.6; }
.chip {
    display: inline-block;
    background: #f1f5f9; border: 1px solid #e2e8f0;
    color: #475569; padding: 3px 10px;
    border-radius: 20px; font-size: 11px; font-weight: 500;
    margin: 3px 2px;
}

.sidebar-title {
    font-size: 10px; font-weight: 700;
    color: #94a3b8; letter-spacing: 1.2px;
    text-transform: uppercase; margin-bottom: 8px;
    padding-top: 4px;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
#  NAVBAR
# ─────────────────────────────────────────
st.markdown("""
<div class="navbar">
    <div class="nav-brand">
        <div class="nav-logo">🩸</div>
        <div>
            <div class="nav-title">Blood Bank Help Center</div>
            <div class="nav-sub">King's College Hospital London — Jeddah</div>
        </div>
    </div>
    <div style="display:flex;align-items:center;gap:10px;">
        <div class="nav-badge">📞 Emergency Ext. 2125</div>
        <div style="font-size:11px;color:#94a3b8;background:#f8fafc;border:1px solid #e2e8f0;padding:4px 12px;border-radius:20px;">IPP-LB-02 Series</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
#  LAYOUT
# ─────────────────────────────────────────
left_col, right_col = st.columns([1, 2.8], gap="small")

# ══════════════════════ LEFT SIDEBAR ══════════════════════
with left_col:
    with st.container():
        st.markdown('<div class="sidebar-title">Key References</div>', unsafe_allow_html=True)
        for icon, label, value, bg, color in STAT_CARDS:
            st.markdown(f"""
            <div class="stat-card" style="background:{bg};">
                <span style="font-size:17px;">{icon}</span>
                <div>
                    <div class="stat-label">{label}</div>
                    <div class="stat-value" style="color:{color};">{value}</div>
                </div>
            </div>""", unsafe_allow_html=True)

        st.markdown('<br><div class="sidebar-title">Quick Actions</div>', unsafe_allow_html=True)
        for icon, label, color, prompt in QUICK_ACTIONS:
            if st.button(f"{icon}  {label}", key=f"qa_{label}", use_container_width=True):
                st.session_state.pending_prompt = prompt

        st.markdown('<br><div class="sidebar-title">Policy Index</div>', unsafe_allow_html=True)
        for code, title in POLICIES:
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:7px;margin-bottom:3px;background:#f8fafc;border:1px solid #f1f5f9;">
                <span style="background:#fef2f2;color:#dc2626;font-size:9px;font-weight:700;padding:2px 5px;border-radius:4px;white-space:nowrap;">LB-02-{code}</span>
                <span style="font-size:11px;color:#475569;">{title}</span>
            </div>""", unsafe_allow_html=True)

        st.markdown("""
        <div style="text-align:center;padding:12px 0 4px;font-size:10px;color:#94a3b8;border-top:1px solid #f1f5f9;margin-top:12px;">
            KCHL-J Blood Bank &nbsp;|&nbsp; Clinical reference only<br>Does not replace clinical judgment
        </div>""", unsafe_allow_html=True)

# ══════════════════════ RIGHT CHAT PANEL ══════════════════════
with right_col:
    # Process pending quick action
    if st.session_state.pending_prompt:
        p = st.session_state.pending_prompt
        st.session_state.pending_prompt = None
        send_message(p)
        st.rerun()

    # Welcome card when no messages
    if not st.session_state.messages:
        st.markdown("""
        <div class="welcome-card">
            <div class="welcome-title">🩸 KCHL-J Blood Bank AI Assistant</div>
            <div class="welcome-sub">
                I have direct access to all <strong>IPP-LB-02 series</strong> policies.
                Ask me anything about transfusion medicine, blood ordering, emergency protocols, or compatibility rules.<br><br>
                <strong>أستطيع الإجابة بالعربية أيضاً</strong> — I respond in Arabic if you write in Arabic.
            </div>
            <div style="margin-top:12px;">
                <span class="chip">🔬 Blood Ordering</span>
                <span class="chip">🚨 MTP Protocol</span>
                <span class="chip">🆘 Emergency Release</span>
                <span class="chip">👶 Neonatal</span>
                <span class="chip">⚠️ Reactions</span>
                <span class="chip">🩺 Compatibility</span>
                <span class="chip">👩‍⚕️ Nursing</span>
                <span class="chip">🌐 Arabic Support</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Chat messages ──
    for msg in st.session_state.messages:
        safe_content = html.escape(msg["content"])
        # Convert newlines to <br> after escaping
        safe_content = safe_content.replace("\n", "<br>")

        if msg["role"] == "user":
            rtl_style = 'direction:rtl;text-align:right;' if is_rtl(msg["content"]) else ''
            st.markdown(f"""
            <div class="user-msg-container">
                <div class="user-bubble" style="{rtl_style}">{safe_content}</div>
            </div>""", unsafe_allow_html=True)
        else:
            rtl_style = 'direction:rtl;text-align:right;' if is_rtl(msg["content"]) else ''
            st.markdown(f"""
            <div class="bot-msg-container">
                <div class="bot-avatar">🩸</div>
                <div>
                    <div class="bot-name">KCHL-J Blood Bank AI</div>
                    <div class="bot-bubble" style="{rtl_style}">{safe_content}</div>
                </div>
            </div>""", unsafe_allow_html=True)

    # ── Input bar ──
    st.markdown("<div style='margin-top:16px;border-top:1px solid #e2e8f0;padding-top:14px;'>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([6, 1, 1])
    with c1:
        user_input = st.text_input(
            label="",
            placeholder="Ask about blood ordering, MTP, compatibility, reactions... / اكتب سؤالك بالعربية",
            label_visibility="collapsed",
            key="chat_input",
        )
    with c2:
        send_btn = st.button("Send ➤", use_container_width=True, key="send_btn")
    with c3:
        clear_btn = st.button("🗑️ Clear", use_container_width=True, key="clear_btn")
    st.markdown("</div>", unsafe_allow_html=True)

    if send_btn and user_input and user_input.strip():
        send_message(user_input.strip())
        st.rerun()

    if clear_btn:
        st.session_state.messages = []
        st.rerun()