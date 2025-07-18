import streamlit as st
from streamlit_quill import st_quill
from datetime import datetime
import json
import os
from pytz import timezone
import pytz
import re

# Google Sheets imports
import gspread
from google.oauth2.service_account import Credentials

# Google Sheets setup
GSPREAD_SHEET_ID = "1MbElYeHw8bCK9kOyFjv1AtsSEu2H9Qmk8aC3seFhIVE"

# Load credentials from Streamlit secrets or local file
if "gcp_service_account" in st.secrets:
    creds_info = st.secrets["gcp_service_account"]
    creds = Credentials.from_service_account_info(creds_info)
else:
    creds = Credentials.from_service_account_file("credentials.json")

gc = gspread.authorize(creds)
sheet = gc.open_by_key(GSPREAD_SHEET_ID).sheet1

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

USER_COLORS = {
    "Aldo": "#23c053",
    "Moni": "#e754c5"
}

def format_datetime_la(dt):
    la_tz = timezone('America/Los_Angeles')
    dt_la = dt.astimezone(la_tz)
    # Determine if PDT or PST based on date
    is_dst = bool(dt_la.dst())
    tz_abbr = "PDT" if is_dst else "PST"
    return dt_la.strftime(f"%d %b %Y - %I:%M %p ({tz_abbr})")

def save_entries(entries):
    # Clear all rows except header
    sheet.resize(1)
    # Prepare data for sheet
    rows = []
    for e in entries:
        row = [
            e.get("user", ""),
            e.get("category", ""),
            e.get("comment", ""),
            e.get("datetime", ""),
            str(e.get("closed", False)),
            json.dumps(e.get("replies", []))
        ]
        rows.append(row)
    if rows:
        sheet.append_rows(rows)

def load_entries():
    all_records = sheet.get_all_records()
    for r in all_records:
        # Parse replies json string back to list
        try:
            r["replies"] = json.loads(r.get("replies_json", "[]"))
        except Exception:
            r["replies"] = []
        r["closed"] = r.get("closed", "False") in [True, "True", "true"]
    return all_records

def pending_count_by_category(entries, viewing_user):
    other_user = USERS[1] if viewing_user == USERS[0] else USERS[0]
    counts = {cat: 0 for cat in CATEGORIES}
    for entry in entries:
        if entry.get("closed", False):
            continue
        if entry["user"] == other_user:
            replies = entry.get("replies", [])
            if not replies or replies[-1]["user"] != viewing_user:
                cat = entry.get("category", "Other")
                if cat not in counts:
                    counts[cat] = 0
                counts[cat] += 1
    return counts

def colored_name(user):
    color = USER_COLORS.get(user, "#888")
    return f'<span style="color:{color};font-weight:bold">{user}</span>'

def category_badge_html(category, count, margin_left=4):
    color = CATEGORY_COLORS.get(category, "#888")
    initial = category[0]
    return f"""<span style='background:{color};
    color:#fff;border-radius:10px;padding:2px 9px;font-size:0.89em;
    margin-left:{margin_left}px;display:inline-block;'>{initial}:{count}</span>"""

def category_label_html(category):
    color = CATEGORY_COLORS.get(category, "#888")
    return f"""<span style='background:{color};color:#fff;
    border-radius:6px;padding:2px 10px;font-size:0.95em;margin-left:7px;'>{category}</span>"""

def highlight_text(text, query):
    if not query.strip():
        return text
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    def repl(m):
        return f"<mark style='background: #ffe066'>{m.group(0)}</mark>"
    return pattern.sub(repl, text)

def get_entry_date(entry):
    dt_txt = entry["datetime"].split(" - ")[0]
    return datetime.strptime(dt_txt, "%d %b %Y").date()

def main():
    st.set_page_config(page_title="Aldo/Moni Logger")

    if "entries" not in st.session_state:
        st.session_state.entries = load_entries()
    entries = st.session_state.entries

    if "user" not in st.session_state:
        st.session_state.user = USERS[0]
    user = st.session_state.user

    user = st.sidebar.radio(
        "Select user:",
        USERS,
        index=USERS.index(user),
        key="user_radio"
    )
    st.session_state.user = user

    st.sidebar.markdown("**Notifications:**", unsafe_allow_html=True)
    for user_iter in USERS:
        counts = pending_count_by_category(entries, user_iter)
        badges = "".join([category_badge_html(cat, n) for cat, n in counts.items() if n > 0])
        user_label = f"<span style='font-weight:600'>{user_iter}</span>"
        st.sidebar.markdown(
            f"{user_label}{badges if badges else '<span style=\"color:#888;font-size:0.95em\"> 0</span>'}",
            unsafe_allow_html=True
        )

    unique_dates = sorted({get_entry_date(e) for e in entries})
    if unique_dates:
        st.sidebar.markdown("**Filter by day:**")
        calendar_selected = st.sidebar.date_input(
            "Jump to day",
            value=None,
            min_value=min(unique_dates),
            max_value=max(unique_dates),
            format="YYYY-MM-DD",
            key="calendar_input"
        )
    else:
        calendar_selected = None

    user_color = USER_COLORS.get(user, "#888")

    st.markdown(
        f"<h1 style='color:{user_color};font-size:2.8em;text-align:center;margin-bottom:10px;margin-top:4px'>{user}</h1>",
        unsafe_allow_html=True
    )
    st.markdown("<div style='height: 2px'></div>", unsafe_allow_html=True)

    if "expanded_reply_idx" not in st.session_state:
        st.session_state.expanded_reply_idx = None

    editor_key = f"quill_editor_main_{user}"

    if editor_key not in st.session_state:
        st.session_state[editor_key] = ""

    if st.session_state.get("show_success"):
        st.success("Comment added.")
        st.session_state["show_success"] = False

    if st.session_state.get("reply_success"):
        st.success(st.session_state.reply_success)
        st.session_state.reply_success = ""
    if st.session_state.get("reply_error"):
        st.warning(st.session_state.reply_error)
        st.session_state.reply_error = ""

    st.header("Add a new comment")
    category = st.selectbox("Category", sorted(CATEGORIES), key=f"category_main_{user}")
    comment = st_quill(html=True, key=editor_key)

    add_comment_btn = st.button("Add comment")
    if add_comment_btn:
        if not comment or comment.strip() in ("", "<p><br></p>"):
            st.warning("Please enter a comment.")
        else:
            new_entry = {
                "user": user,
                "category": category,
                "comment": comment,
                "datetime": format_datetime_la(datetime.now(pytz.utc)),
                "replies": [],
                "closed": False
            }
            st.session_state.entries.append(new_entry)
            save_entries(st.session_state.entries)
            st.session_state["show_success"] = True
            st.session_state[editor_key] = ""  # Clear editor content immediately

    st.header("Comments thread")
    search_text = st.text_input("🔍 Search in all comments and replies", value="", placeholder="Type to search...")

    def entry_matches(entry, search):
        search = search.lower()
        def clean_html(raw_html):
            cleanr = re.compile('<.*?>')
            return re.sub(cleanr, '', raw_html)
        if search in clean_html(entry["comment"]).lower():
            return True
        for reply in entry.get("replies", []):
            if search in clean_html(reply["comment"]).lower():
                return True
        return False

    if unique_dates and calendar_selected:
        if isinstance(calendar_selected, list):
            calendar_selected = calendar_selected[0]
        calendar_filtered = [e for e in entries if get_entry_date(e) == calendar_selected]
    else:
        calendar_filtered = entries

    if search_text:
        filtered_entries = [e for e in calendar_filtered if entry_matches(e, search_text)]
    else:
        filtered_entries = calendar_filtered

    if not filtered_entries:
        st.info("No results found.")
    else:
        for idx, entry in enumerate(filtered_entries):
            cat_html = category_label_html(entry['category'])
            header_html = (
                f"{colored_name(entry['user'])} "
                f"{cat_html} "
                f"<span style='background-color:#222;padding:2px 8px;border-radius:6px;color:#4CAF50;font-size:0.9em'>{entry['datetime']}</span>"
            )
            st.markdown(header_html, unsafe_allow_html=True)
            st.markdown(highlight_text(entry["comment"], search_text), unsafe_allow_html=True)

            if entry.get("closed", False):
                st.markdown("<span style='color:#888;font-size:1em;font-style:italic'>[Thread closed]</span>", unsafe_allow_html=True)
            if entry.get("replies"):
                for reply in entry["replies"]:
                    reply_header = (
                        f"{colored_name(reply['user'])} "
                        f"{category_label_html(entry['category'])} "
                        f"<span style='background-color:#222;padding:2px 8px;border-radius:6px;color:#4CAF50;font-size:0.9em'>{reply['datetime']}</span>"
                    )
                    st.markdown(reply_header, unsafe_allow_html=True)
                    st.markdown(highlight_text(reply["comment"], search_text), unsafe_allow_html=True)

            if not entry.get("closed", False):
                if st.button(f"Close thread #{idx+1}", key=f"closebtn_{idx}"):
                    st.session_state.entries[entries.index(entry)]["closed"] = True
                    save_entries(st.session_state.entries)
                    st.success("Thread closed!")

                if entry["user"] != user:
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
                                    "datetime": format_datetime_la(datetime.now(pytz.utc))
                                }
                                st.session_state.entries[entries.index(entry)]["replies"].append(reply)
                                save_entries(st.session_state.entries)
                                st.session_state[reply_key] = ""
                                st.success("Reply added.")
                                st.session_state.expanded_reply_idx = idx
            st.markdown("---")

if __name__ == "__main__":
    main()
