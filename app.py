"""
📝 My Daily Tasks
Plan your day. Complete your tasks. Stay productive.

A cross-device Daily To-Do Task Manager built with Streamlit + Supabase.
All task data lives in Supabase (PostgreSQL) so it stays in sync across
every device the user logs in from. st.session_state is used ONLY for
temporary UI state (which form is open, which task is being edited, etc.)
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta
from supabase import create_client, Client

# ----------------------------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="My Daily Tasks",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)

PRIORITY_OPTIONS = ["🔴 High", "🟡 Medium", "🟢 Low"]
CATEGORY_OPTIONS = ["Study", "Work", "Personal", "Fitness", "Shopping", "Other"]
RECURRING_OPTIONS = ["None", "Daily", "Weekly", "Monthly"]
TABLE_NAME = "tasks"


# ----------------------------------------------------------------------
# 1. SUPABASE CONNECTION
# ----------------------------------------------------------------------
def connect_to_supabase() -> Client | None:
    """Create (or reuse) a Supabase client for this browser session."""
    if "supabase_client" in st.session_state:
        return st.session_state.supabase_client

    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except Exception:
        st.error(
            "❌ Missing Supabase configuration. Please add SUPABASE_URL and "
            "SUPABASE_KEY to your Streamlit secrets (see README.md)."
        )
        st.stop()

    try:
        client = create_client(url, key)
        st.session_state.supabase_client = client
        return client
    except Exception:
        st.error("❌ Could not connect to Supabase. Please try again later.")
        st.stop()


# ----------------------------------------------------------------------
# 2. AUTHENTICATION
# ----------------------------------------------------------------------
def signup_user(client: Client, email: str, password: str, confirm_password: str):
    if not email or not password:
        return False, "Email and password are required."
    if password != confirm_password:
        return False, "Passwords do not match."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    try:
        result = client.auth.sign_up({"email": email, "password": password})
        if result.user:
            return True, "✅ Account created! Please check your email to confirm, then log in."
        return False, "❌ Something went wrong. Please try again."
    except Exception as e:
        return False, f"❌ Signup failed: {e}"


def login_user(client: Client, email: str, password: str):
    if not email or not password:
        return False, "Please enter both email and password."

    try:
        result = client.auth.sign_in_with_password({"email": email, "password": password})
        if result.user and result.session:
            # Attach the user's access token so PostgREST requests respect RLS
            client.postgrest.auth(result.session.access_token)
            st.session_state.user = {"id": result.user.id, "email": result.user.email}
            st.session_state.access_token = result.session.access_token
            st.session_state.refresh_token = result.session.refresh_token
            return True, None
        return False, "❌ Invalid email or password."
    except Exception:
        return False, "❌ Invalid email or password."


def logout_user(client: Client):
    try:
        client.auth.sign_out()
    except Exception:
        pass
    for key in ["user", "access_token", "refresh_token", "confirm_delete_id", "edit_task_id"]:
        st.session_state.pop(key, None)
    st.rerun()


# ----------------------------------------------------------------------
# 3. TASK CRUD
# ----------------------------------------------------------------------
def get_tasks(client: Client, user_id: str) -> pd.DataFrame:
    try:
        response = (
            client.table(TABLE_NAME)
            .select("*")
            .eq("user_id", user_id)
            .order("task_date", desc=False)
            .order("task_time", desc=False)
            .execute()
        )
        data = response.data or []
        df = pd.DataFrame(data)
        if df.empty:
            df = pd.DataFrame(
                columns=[
                    "id", "user_id", "title", "description", "task_date",
                    "task_time", "priority", "category", "completed",
                    "recurring", "created_at", "completed_at",
                ]
            )
        return df
    except Exception as e:
        st.error(f"❌ Something went wrong loading your tasks. ({e})")
        return pd.DataFrame()


def add_task(client, user_id, title, description, task_date, task_time, priority, category, recurring):
    if not title or not title.strip():
        return False, "Task title cannot be empty."
    try:
        payload = {
            "user_id": user_id,
            "title": title.strip(),
            "description": description.strip() if description else "",
            "task_date": task_date.isoformat() if task_date else None,
            "task_time": task_time.strftime("%H:%M:%S") if task_time else None,
            "priority": priority,
            "category": category,
            "completed": False,
            "recurring": recurring,
            "created_at": datetime.utcnow().isoformat(),
            "completed_at": None,
        }
        client.table(TABLE_NAME).insert(payload).execute()
        return True, "✅ Task added!"
    except Exception as e:
        return False, f"❌ Could not add task. ({e})"


def update_task(client, task_id, fields: dict):
    try:
        client.table(TABLE_NAME).update(fields).eq("id", task_id).execute()
        return True, "💾 Changes saved!"
    except Exception as e:
        return False, f"❌ Could not update task. ({e})"


def delete_task(client, task_id):
    try:
        client.table(TABLE_NAME).delete().eq("id", task_id).execute()
        return True, "🗑️ Task deleted."
    except Exception as e:
        return False, f"❌ Could not delete task. ({e})"


def _next_recurring_date(current: date, recurring: str) -> date | None:
    if recurring == "Daily":
        return current + timedelta(days=1)
    if recurring == "Weekly":
        return current + timedelta(weeks=1)
    if recurring == "Monthly":
        month = current.month + 1
        year = current.year + (1 if month > 12 else 0)
        month = 1 if month > 12 else month
        day = min(current.day, 28)  # keep it simple & safe for all months
        return date(year, month, day)
    return None


def complete_task(client, task_row: pd.Series, mark_completed: bool):
    """Toggle a task's completion. If completing a recurring task, create
    the next occurrence so the user always has the upcoming task waiting."""
    task_id = task_row["id"]
    fields = {
        "completed": mark_completed,
        "completed_at": datetime.utcnow().isoformat() if mark_completed else None,
    }
    ok, msg = update_task(client, task_id, fields)
    if not ok:
        return ok, msg

    recurring = task_row.get("recurring")
    if mark_completed and recurring and recurring != "None":
        try:
            current_date = (
                datetime.fromisoformat(str(task_row["task_date"])).date()
                if task_row.get("task_date") else date.today()
            )
            next_date = _next_recurring_date(current_date, recurring)
            if next_date:
                # Avoid duplicate next-occurrence creation
                existing = (
                    client.table(TABLE_NAME)
                    .select("id")
                    .eq("user_id", task_row["user_id"])
                    .eq("title", task_row["title"])
                    .eq("task_date", next_date.isoformat())
                    .execute()
                )
                if not existing.data:
                    add_task(
                        client, task_row["user_id"], task_row["title"],
                        task_row.get("description", ""), next_date,
                        datetime.strptime(task_row["task_time"], "%H:%M:%S").time()
                        if task_row.get("task_time") else None,
                        task_row.get("priority"), task_row.get("category"), recurring,
                    )
        except Exception:
            pass  # Never block the completion action on recurrence errors

    return True, msg


# ----------------------------------------------------------------------
# 4. PROGRESS / DASHBOARD HELPERS
# ----------------------------------------------------------------------
def calculate_progress(df: pd.DataFrame, target_date: date):
    if df.empty:
        return 0, 0, 0, 0.0
    day_tasks = df[df["task_date"] == target_date.isoformat()]
    total = len(day_tasks)
    completed = int(day_tasks["completed"].sum()) if total else 0
    pending = total - completed
    pct = (completed / total * 100) if total else 0.0
    return total, completed, pending, pct


def calculate_overdue(df: pd.DataFrame):
    if df.empty:
        return pd.DataFrame()
    now = datetime.now()

    def is_overdue(row):
        if row["completed"] or not row["task_date"]:
            return False
        try:
            t = row["task_time"] if row["task_time"] else "23:59:59"
            dt = datetime.fromisoformat(f"{row['task_date']}T{t}")
            return dt < now
        except Exception:
            return False

    mask = df.apply(is_overdue, axis=1)
    return df[mask]


def show_dashboard(df: pd.DataFrame):
    st.subheader("📊 Today's Dashboard")
    today = date.today()
    total, completed, pending, pct = calculate_progress(df, today)
    overdue_df = calculate_overdue(df)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📋 Today's Tasks", total)
    c2.metric("✅ Completed", completed)
    c3.metric("⏳ Pending", pending)
    c4.metric("⚠️ Overdue", len(overdue_df))

    st.caption(f"Today's Progress — {pct:.0f}%")
    st.progress(min(pct / 100, 1.0))

    with st.expander("📈 Productivity Overview"):
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Weekly Completion**")
            if not df.empty:
                week_start = today - timedelta(days=6)
                dates = pd.date_range(week_start, today)
                weekly = []
                for d in dates:
                    t, c, p, _ = calculate_progress(df, d.date())
                    weekly.append({"date": d.strftime("%a"), "completed": c, "total": t})
                weekly_df = pd.DataFrame(weekly).set_index("date")
                st.bar_chart(weekly_df)
            else:
                st.write("No data yet.")
        with col2:
            st.write("**Overall Totals**")
            total_all = len(df)
            completed_all = int(df["completed"].sum()) if not df.empty else 0
            st.metric("Total Tasks", total_all)
            st.metric("Completed Tasks", completed_all)


# ----------------------------------------------------------------------
# 5. TASK LIST UI
# ----------------------------------------------------------------------
def render_task_row(client, row: pd.Series):
    task_id = row["id"]
    is_overdue = not row["completed"] and row["task_date"] and (
        (datetime.fromisoformat(f"{row['task_date']}T{row['task_time'] or '23:59:59'}") < datetime.now())
        if row["task_date"] else False
    )

    with st.container(border=True):
        col_check, col_info, col_actions = st.columns([0.5, 5, 2])

        with col_check:
            checked = st.checkbox(
                "", value=bool(row["completed"]), key=f"chk_{task_id}",
                label_visibility="collapsed",
            )
            if checked != bool(row["completed"]):
                ok, msg = complete_task(client, row, checked)
                if ok:
                    st.rerun()
                else:
                    st.error(msg)

        with col_info:
            title_display = f"~~{row['title']}~~" if row["completed"] else f"**{row['title']}**"
            if row["completed"]:
                st.markdown(f"✅ {title_display}")
            elif is_overdue:
                st.markdown(f"⚠️ {title_display}  \n**OVERDUE**")
            else:
                st.markdown(title_display)

            meta_bits = []
            if row["task_date"]:
                meta_bits.append(f"📅 {row['task_date']}")
            if row["task_time"]:
                meta_bits.append(f"🕐 {row['task_time'][:5]}")
            if row.get("priority"):
                meta_bits.append(str(row["priority"]))
            if row.get("category"):
                meta_bits.append(f"📂 {row['category']}")
            if row.get("recurring") and row["recurring"] != "None":
                meta_bits.append(f"🔁 {row['recurring']}")
            st.caption(" · ".join(meta_bits))
            if row.get("description"):
                st.caption(row["description"])

        with col_actions:
            b1, b2 = st.columns(2)
            if b1.button("✏️", key=f"edit_{task_id}", help="Edit task"):
                st.session_state.edit_task_id = task_id
            if b2.button("🗑️", key=f"del_{task_id}", help="Delete task"):
                st.session_state.confirm_delete_id = task_id

    # Delete confirmation
    if st.session_state.get("confirm_delete_id") == task_id:
        st.warning(f"Delete '{row['title']}'? This cannot be undone.")
        cc1, cc2 = st.columns(2)
        if cc1.button("Yes, delete", key=f"confirm_del_{task_id}"):
            ok, msg = delete_task(client, task_id)
            st.session_state.confirm_delete_id = None
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
        if cc2.button("Cancel", key=f"cancel_del_{task_id}"):
            st.session_state.confirm_delete_id = None
            st.rerun()

    # Edit form
    if st.session_state.get("edit_task_id") == task_id:
        with st.expander("Edit Task", expanded=True):
            with st.form(key=f"edit_form_{task_id}"):
                new_title = st.text_input("Task Title", value=row["title"])
                new_desc = st.text_area("Description", value=row.get("description") or "")
                col_a, col_b = st.columns(2)
                default_date = (
                    datetime.fromisoformat(str(row["task_date"])).date()
                    if row["task_date"] else date.today()
                )
                default_time = (
                    datetime.strptime(row["task_time"], "%H:%M:%S").time()
                    if row["task_time"] else time(9, 0)
                )
                new_date = col_a.date_input("Date", value=default_date)
                new_time = col_b.time_input("Time", value=default_time)
                new_priority = st.selectbox(
                    "Priority", PRIORITY_OPTIONS,
                    index=PRIORITY_OPTIONS.index(row["priority"]) if row.get("priority") in PRIORITY_OPTIONS else 1,
                )
                new_category = st.selectbox(
                    "Category", CATEGORY_OPTIONS,
                    index=CATEGORY_OPTIONS.index(row["category"]) if row.get("category") in CATEGORY_OPTIONS else 5,
                )
                new_recurring = st.selectbox(
                    "Recurring", RECURRING_OPTIONS,
                    index=RECURRING_OPTIONS.index(row["recurring"]) if row.get("recurring") in RECURRING_OPTIONS else 0,
                )

                save, cancel = st.columns(2)
                if save.form_submit_button("💾 Save Changes"):
                    ok, msg = update_task(client, task_id, {
                        "title": new_title.strip(),
                        "description": new_desc.strip(),
                        "task_date": new_date.isoformat(),
                        "task_time": new_time.strftime("%H:%M:%S"),
                        "priority": new_priority,
                        "category": new_category,
                        "recurring": new_recurring,
                    })
                    st.session_state.edit_task_id = None
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
                if cancel.form_submit_button("Cancel"):
                    st.session_state.edit_task_id = None
                    st.rerun()


def show_task_list(client, df: pd.DataFrame):
    st.subheader("🗂️ Tasks")
    if df.empty:
        st.info("No tasks yet. Add your first task from the sidebar! ➕")
        return
    for _, row in df.iterrows():
        render_task_row(client, row)


# ----------------------------------------------------------------------
# 6. ADD TASK FORM
# ----------------------------------------------------------------------
def show_add_task_form(client, user_id):
    st.subheader("➕ Add Task")
    with st.form("add_task_form", clear_on_submit=True):
        title = st.text_input("Task Title")
        description = st.text_area("Description", height=80)
        col_a, col_b = st.columns(2)
        task_date = col_a.date_input("Date", value=date.today())
        task_time = col_b.time_input("Time", value=time(9, 0))
        col_c, col_d, col_e = st.columns(3)
        priority = col_c.selectbox("Priority", PRIORITY_OPTIONS, index=1)
        category = col_d.selectbox("Category", CATEGORY_OPTIONS)
        recurring = col_e.selectbox("Recurring", RECURRING_OPTIONS)

        submitted = st.form_submit_button("➕ Add Task", use_container_width=True)
        if submitted:
            ok, msg = add_task(client, user_id, title, description, task_date, task_time, priority, category, recurring)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


# ----------------------------------------------------------------------
# 7. FILTERS (SIDEBAR)
# ----------------------------------------------------------------------
def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    st.sidebar.markdown("---")
    selected_date = st.sidebar.date_input("📅 Select Date", value=date.today())
    use_date_filter = st.sidebar.checkbox("Filter by this date", value=False)

    search = st.sidebar.text_input("🔎 Search tasks...")

    status = st.sidebar.selectbox("📌 Status", ["All", "Today", "Pending", "Completed", "Overdue"])
    priority_filter = st.sidebar.multiselect("⭐ Priority", PRIORITY_OPTIONS)
    category_filter = st.sidebar.multiselect("📂 Category", CATEGORY_OPTIONS)

    filtered = df.copy()

    if use_date_filter:
        filtered = filtered[filtered["task_date"] == selected_date.isoformat()]

    if search:
        s = search.lower()
        filtered = filtered[
            filtered["title"].str.lower().str.contains(s, na=False)
            | filtered["description"].fillna("").str.lower().str.contains(s, na=False)
        ]

    today_str = date.today().isoformat()
    if status == "Today":
        filtered = filtered[filtered["task_date"] == today_str]
    elif status == "Pending":
        filtered = filtered[filtered["completed"] == False]  # noqa: E712
    elif status == "Completed":
        filtered = filtered[filtered["completed"] == True]  # noqa: E712
    elif status == "Overdue":
        filtered = calculate_overdue(filtered)

    if priority_filter:
        filtered = filtered[filtered["priority"].isin(priority_filter)]
    if category_filter:
        filtered = filtered[filtered["category"].isin(category_filter)]

    return filtered.reset_index(drop=True)


# ----------------------------------------------------------------------
# 8. AUTH SCREENS
# ----------------------------------------------------------------------
def show_auth_screen(client):
    st.title("📝 My Daily Tasks")
    st.caption("Plan your day. Complete your tasks. Stay productive.")

    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            if st.form_submit_button("Login", use_container_width=True):
                ok, err = login_user(client, email, password)
                if ok:
                    st.rerun()
                else:
                    st.error(err)

    with tab_signup:
        with st.form("signup_form"):
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            confirm = st.text_input("Confirm Password", type="password", key="signup_confirm")
            if st.form_submit_button("Create Account", use_container_width=True):
                ok, msg = signup_user(client, email, password, confirm)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)


# ----------------------------------------------------------------------
# 9. MAIN APP
# ----------------------------------------------------------------------
def main():
    client = connect_to_supabase()

    if "user" not in st.session_state:
        show_auth_screen(client)
        return

    user = st.session_state.user

    # Sidebar
    st.sidebar.title("📝 Daily Task Manager")
    st.sidebar.caption(f"👤 Logged in as:\n{user['email']}")
    st.sidebar.markdown("---")

    df_all = get_tasks(client, user["id"])
    df_filtered = apply_filters(df_all)

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        logout_user(client)

    # Main area
    st.title("📝 My Daily Tasks")
    st.caption("Plan your day. Complete your tasks. Stay productive.")

    tab_dashboard, tab_tasks, tab_add = st.tabs(["📊 Dashboard", "🗂️ Tasks", "➕ Add Task"])

    with tab_dashboard:
        show_dashboard(df_all)

    with tab_tasks:
        show_task_list(client, df_filtered)

    with tab_add:
        show_add_task_form(client, user["id"])


if __name__ == "__main__":
    main()
