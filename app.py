"""
📝 My Daily Tasks (Local Edition)
Plan your day. Complete your tasks. Stay productive.

A single-user Daily To-Do Task Manager built with Streamlit + SQLite.
No cloud account, no login, no internet connection required.
All tasks are stored in a local file called `tasks.db` next to this script,
so your data persists between runs of the app on this machine.

Note: this version does NOT sync across devices. If you need the same
tasks on your phone and laptop, you need a cloud backend (e.g. Supabase).
"""

import sqlite3
import streamlit as st
import pandas as pd
from datetime import datetime, date, time, timedelta
from pathlib import Path

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
DB_PATH = Path(__file__).parent / "tasks.db"


# ----------------------------------------------------------------------
# 1. DATABASE CONNECTION & SETUP
# ----------------------------------------------------------------------
def connect_to_db() -> sqlite3.Connection:
    """Open (and cache) a connection to the local SQLite database."""
    if "db_conn" in st.session_state:
        return st.session_state.db_conn
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        st.session_state.db_conn = conn
        init_db(conn)
        return conn
    except Exception:
        st.error("❌ Could not open the local task database. Please try again.")
        st.stop()


def init_db(conn: sqlite3.Connection):
    """Create the tasks table if it doesn't exist yet."""
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                task_date TEXT,
                task_time TEXT,
                priority TEXT DEFAULT '🟡 Medium',
                category TEXT DEFAULT 'Other',
                completed INTEGER DEFAULT 0,
                recurring TEXT DEFAULT 'None',
                created_at TEXT,
                completed_at TEXT
            )
            """
        )
        conn.commit()
    except Exception as e:
        st.error(f"❌ Could not set up the database. ({e})")
        st.stop()


# ----------------------------------------------------------------------
# 2. TASK CRUD
# ----------------------------------------------------------------------
def get_tasks(conn: sqlite3.Connection) -> pd.DataFrame:
    try:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY task_date ASC, task_time ASC"
        ).fetchall()
        df = pd.DataFrame([dict(r) for r in rows])
        if df.empty:
            df = pd.DataFrame(
                columns=[
                    "id", "title", "description", "task_date", "task_time",
                    "priority", "category", "completed", "recurring",
                    "created_at", "completed_at",
                ]
            )
        else:
            df["completed"] = df["completed"].astype(bool)
        return df
    except Exception as e:
        st.error(f"❌ Something went wrong loading your tasks. ({e})")
        return pd.DataFrame()


def add_task(conn, title, description, task_date, task_time, priority, category, recurring):
    if not title or not title.strip():
        return False, "Task title cannot be empty."
    try:
        conn.execute(
            """
            INSERT INTO tasks
                (title, description, task_date, task_time, priority, category,
                 completed, recurring, created_at, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, NULL)
            """,
            (
                title.strip(),
                description.strip() if description else "",
                task_date.isoformat() if task_date else None,
                task_time.strftime("%H:%M:%S") if task_time else None,
                priority,
                category,
                recurring,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        return True, "✅ Task added!"
    except Exception as e:
        return False, f"❌ Could not add task. ({e})"


def update_task(conn, task_id, fields: dict):
    if not fields:
        return True, "Nothing to update."
    try:
        columns = ", ".join(f"{k} = ?" for k in fields)
        # task_id may arrive as numpy.int64 from a pandas DataFrame; sqlite3
        # silently fails to match rows against numpy int types, so coerce
        # it to a plain Python int first.
        values = list(fields.values()) + [int(task_id)]
        conn.execute(f"UPDATE tasks SET {columns} WHERE id = ?", values)
        conn.commit()
        return True, "💾 Changes saved!"
    except Exception as e:
        return False, f"❌ Could not update task. ({e})"


def delete_task(conn, task_id):
    try:
        conn.execute("DELETE FROM tasks WHERE id = ?", (int(task_id),))
        conn.commit()
        return True, "🗑️ Task deleted."
    except Exception as e:
        return False, f"❌ Could not delete task. ({e})"


def _next_recurring_date(current: date, recurring: str):
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


def complete_task(conn, task_row: pd.Series, mark_completed: bool):
    """Toggle a task's completion. If completing a recurring task, create
    the next occurrence so the user always has the upcoming task waiting."""
    task_id = task_row["id"]
    fields = {
        "completed": 1 if mark_completed else 0,
        "completed_at": datetime.now().isoformat() if mark_completed else None,
    }
    ok, msg = update_task(conn, task_id, fields)
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
                existing = conn.execute(
                    "SELECT id FROM tasks WHERE title = ? AND task_date = ?",
                    (task_row["title"], next_date.isoformat()),
                ).fetchone()
                if not existing:
                    add_task(
                        conn, task_row["title"], task_row.get("description", ""),
                        next_date,
                        datetime.strptime(task_row["task_time"], "%H:%M:%S").time()
                        if task_row.get("task_time") else None,
                        task_row.get("priority"), task_row.get("category"), recurring,
                    )
        except Exception:
            pass  # Never block the completion action on recurrence errors

    return True, msg


# ----------------------------------------------------------------------
# 3. PROGRESS / DASHBOARD HELPERS
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
# 4. TASK LIST UI
# ----------------------------------------------------------------------
def render_task_row(conn, row: pd.Series):
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
                ok, msg = complete_task(conn, row, checked)
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
            ok, msg = delete_task(conn, task_id)
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
                    ok, msg = update_task(conn, task_id, {
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


def show_task_list(conn, df: pd.DataFrame):
    st.subheader("🗂️ Tasks")
    if df.empty:
        st.info("No tasks yet. Add your first task from the sidebar! ➕")
        return
    for _, row in df.iterrows():
        render_task_row(conn, row)


# ----------------------------------------------------------------------
# 5. ADD TASK FORM
# ----------------------------------------------------------------------
def show_add_task_form(conn):
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
            ok, msg = add_task(conn, title, description, task_date, task_time, priority, category, recurring)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)


# ----------------------------------------------------------------------
# 6. FILTERS (SIDEBAR)
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
# 7. MAIN APP
# ----------------------------------------------------------------------
def main():
    conn = connect_to_db()

    st.sidebar.title("📝 Daily Task Manager")
    st.sidebar.caption(f"💾 Local database: {DB_PATH.name}")
    st.sidebar.markdown("---")

    df_all = get_tasks(conn)
    df_filtered = apply_filters(df_all)

    st.title("📝 My Daily Tasks")
    st.caption("Plan your day. Complete your tasks. Stay productive.")

    tab_dashboard, tab_tasks, tab_add = st.tabs(["📊 Dashboard", "🗂️ Tasks", "➕ Add Task"])

    with tab_dashboard:
        show_dashboard(df_all)

    with tab_tasks:
        show_task_list(conn, df_filtered)

    with tab_add:
        show_add_task_form(conn)


if __name__ == "__main__":
    main()
