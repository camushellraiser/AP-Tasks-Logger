import streamlit as st
from streamlit_quill import st_quill
from datetime import datetime
import json
import os
import re
from pytz import timezone
import pytz
import gspread
from google.oauth2.service_account import Credentials

# Google Sheets setup
GSHEET_ID = "1MbElYeHw8bCK9kOyFjv1AtsSEu2H9Qmk8aC3seFhIVE"
SERVICE_ACCOUNT_FILE = "credentials.json"
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(GSHEET_ID).sheet1

CATEGORIES = [
    "Feedback", "Pending", "Question", "Request", "Other", "Update"
]

USERS = ["Aldo", "Moni"]

CATEGORY_COLORS = {
    "Question": "#2979FF",
    "Pending": "#FF9800",
    "Update": "#009688",
    "Request": "#8E24AA",
    "Feedback": "#43A047",
    "Other": "#546E7A"
}

def format_datetime_la(dt):
    tz = timezone("America/Los_Angeles")
    return dt.astimezone(tz).strftime("%d %b %Y %H:%M")

def colored_name(user):
    if user == "Aldo":
        return f'<span style="color:#23c053;font-weight:bold">{user}</span>'
    else:
        return f'<span style="color:#e754c5;font-weight:bold">{user}</span>'

def load_entries():
    rows = sheet.get_all_records()
    entries = []
    for row in rows:
        replies = []
        if row.get("replies_json"):
            try:
                replies = json.loads(row["replies_json"])
            except Exception:
                replies = []
        entry = {
            "user": row.get("user", ""),
            "category": row.get("category", ""),
            "comment": row.get("comment", ""),
            "datetime": row.get("datetime", ""),
            "closed": row.get("closed", False),
            "replies": replies
        }
        entries.append(entry)
    return entries

def save_entries(entries):
    sheet.resize(rows=1)
    rows = []
    for e in entries:
        replies_json = json.dumps(e.get("replies", []))
        rows.append([
            e.get("user", ""),
            e.get("category", ""),
            e.get("comment", ""),
            e.get("datetime", ""),
            str(e.get("closed", False)),
            replies_json
        ])
    if rows:
        sheet.append_rows(rows, value_input_option="USER_ENTERED")

def pending_count(entries, viewing_user):
    other_user = USERS[1] if viewing_user == USERS[0] else USERS[0]
    count = 0
    for entry in entries:
        if entry["user"] == other_user and not entry.get("closed", False):
            has_reply = any(r["user"] == viewing_user for r in entry.get("replies", []))
            if not has_reply:
                count += 1
    return count

def main():
    st.set_page_config(page_title="Aldo/Moni Logger")
    st.title("📝 Logger for Aldo & Moni")

    if "entries" not in st.session_state:
        st.session_state.entries = load_entries()
    entries = st.session_state.entries

    if "user" not in st.session_state or st.session_state.user is None:
        st.markdown("""
            <style>
            .login-btn-row {
                display: flex;
                justify-content: center;
                gap: 60px;
                margin-bottom: 32px;
                margin-top: 38px;
            }
            .big-login-btn {
                position: relative;
                width: 220px;
                height: 90px;
                border-radius: 38px;
                border: none;
                font-size: 2em;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: bold;
                letter-spacing: 0.20em;
                color: white;
                margin-bottom: 0;
                box-shadow: 0 4px 16px #0001;
                cursor: pointer;
                outline: none;
                transition: filter 0.15s;
                margin-top: 0;
            }
            .big-login-btn:active { filter: brightness(0.94);}
            .aldo-btn { background: #23c053; }
            .moni-btn { background: #ffa8d6; color: white;}
            .noti-badge {
                position: absolute;
                top: 12px;
                right: 22px;
                background: #ff4136;
                color: white;
                font-size: 1.15em;
                font-weight: bold;
                padding: 2px 12px 2px 12px;
                border-radius: 18px;
                box-shadow: 0 2px 10px #0002;
                z-index: 99;
            }
            </style>
        """, unsafe_allow_html=True)

        st.markdown('<div class="login-btn-row">', unsafe_allow_html=True)
        for user in USERS:
            pending = pending_count(entries, user)
            badge_html = f'<span class="noti-badge">{pending}</span>' if pending > 0 else ''
            btn_class = "aldo-btn" if user == "Aldo" else "moni-btn"
            button_html = f"""
                <button onclick="window.parent.postMessage({{type: 'streamlit_select_user', user: '{user}'}}, '*');" 
                        class="big-login-btn {btn_class}">
                    {user.upper()}
                    {badge_html}
                </button>
            """
            st.markdown(button_html, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("""
        <script>
        window.addEventListener('message', function(event) {
            if (event.data && event.data.type === 'streamlit_select_user') {
                window.parent.postMessage({
                    isStreamlitMessage: true,
                    type: 'streamlit:setComponentValue',
                    key: 'selected_user',
                    value: event.data.user
                }, '*');
            }
        });
        </script>
        """, unsafe_allow_html=True)

        selected_user = st.session_state.get("selected_user", None)
        if selected_user in USERS:
            st.session_state.user = selected_user
            st.experimental_rerun()

        st.stop()

    user = st.session_state.user
    other_user = USERS[1] if user == USERS[0] else USERS[0]

    if "expanded_reply_idx" not in st.session_state:
        st.session_state.expanded_reply_idx = None

    editor_key = f"quill_editor_main_{user}"
    if editor_key not in st.session_state:
        st.session_state[editor_key] = ""

    if st.session_state.get("reply_success"):
        st.success(st.session_state.reply_success)
        st.session_state.reply_success = ""
    if st.session_state.get("reply_error"):
        st.warning(st.session_state.reply_error)
        st.session_state.reply_error = ""

    st.header(f"{user}")

    st.header("Add a new comment")
    category = st.selectbox("Category", sorted(CATEGORIES), key=f"category_main_{user}")
    comment = st_quill(html=True, key=editor_key)

    def add_comment():
        if not comment or comment.strip() in ("", "<p><br></p>"):
            st.warning("Please enter a comment.")
        else:
            new_entry = {
                "user": user,
                "category": category,
                "comment": comment,
                "datetime": format_datetime_la(datetime.now(pytz.utc)),
                "closed": False,
                "replies": []
            }
            st.session_state.entries.append(new_entry)
            save_entries(st.session_state.entries)
            st.session_state[editor_key] = ""
            st.session_state.reply_success = "Comment added."
            st.experimental_rerun()

    st.button("Add comment", on_click=add_comment)

    st.header("Comments thread")

    if not entries:
        st.info("No comments yet.")
    else:
        for idx, entry in enumerate(entries):
            color = CATEGORY_COLORS.get(entry["category"], "#888")
            header_html = (
                f"{colored_name(entry['user'])} | "
                f"<i style='color:{color}'>{entry['category']}</i> | "
                f"<span style='background-color:#222;padding:2px 8px;border-radius:6px;color:#4CAF50;font-size:0.9em'>{entry['datetime']}</span>"
            )
            if entry.get("closed"):
                header_html += " 🔒 Closed"

            st.markdown(header_html, unsafe_allow_html=True)
            st.markdown(entry["comment"], unsafe_allow_html=True)

            if entry.get("replies"):
                for reply in entry["replies"]:
                    reply_color = CATEGORY_COLORS.get(reply.get("category", ""), "#888")
                    reply_header = (
                        f"{colored_name(reply['user'])} | "
                        f"<i style='color:{reply_color}'>Answer</i> | "
                        f"<span style='background-color:#222;padding:2px 8px;border-radius:6px;color:#4CAF50;font-size:0.9em'>{reply['datetime']}</span>"
                    )
                    st.markdown(reply_header, unsafe_allow_html=True)
                    st.markdown(reply["comment"], unsafe_allow_html=True)

            if entry["user"] != user and not entry.get("closed", False):
                reply_key = f"reply_{idx}_{user}"
                if reply_key not in st.session_state:
                    st.session_state[reply_key] = ""
                expanded = (st.session_state.expanded_reply_idx == idx)
                with st.expander(f"Reply as {user}", expanded=expanded):
                    comment_reply = st_quill(key=reply_key, html=True)
                    reply_btn = st.button(f"Reply to comment #{idx+1}", key=f"replybtn_{idx}_{user}")
                    if reply_btn:
                        reply_text = st.session_state.get(reply_key, "")
                        if not reply_text or reply_text.strip() in ("", "<p><br></p>"):
                            st.warning("Please enter a reply.")
                        else:
                            reply = {
                                "user": user,
                                "comment": reply_text,
                                "datetime": format_datetime_la(datetime.now(pytz.utc)),
                                "category": "Answer"
                            }
                            st.session_state.entries[idx]["replies"].append(reply)
                            save_entries(st.session_state.entries)
                            st.session_state[reply_key] = ""
                            st.session_state.reply_success = f"Reply to comment #{idx+1} added!"
                            st.session_state.expanded_reply_idx = idx
                            st.experimental_rerun()
                if st.session_state.expanded_reply_idx != idx and st.session_state.get(reply_key):
                    st.session_state.expanded_reply_idx = idx

            # Close thread button
            if entry["user"] == user and not entry.get("closed", False):
                close_btn = st.button(f"Close thread #{idx+1}", key=f"closebtn_{idx}_{user}")
                if close_btn:
                    st.session_state.entries[idx]["closed"] = True
                    save_entries(st.session_state.entries)
                    st.success(f"Thread #{idx+1} closed.")
                    st.experimental_rerun()

            st.markdown("---")

    if st.button("Switch user", key="switchuserbtn"):
        st.session_state.user = None
        st.experimental_rerun()

if __name__ == "__main__":
    main()
