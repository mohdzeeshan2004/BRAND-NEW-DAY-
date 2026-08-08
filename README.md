# 📝 My Daily Tasks (Local Edition)

Plan your day. Complete your tasks. Stay productive.

A simple Daily To-Do Task Manager built with **Python and Streamlit**, using a local
**SQLite** database file for storage. No cloud account, no API keys, no internet
connection required — just run it and go.

> ⚠️ **No cross-device sync.** Tasks are saved in a file called `tasks.db` next to
> `app.py`, on whichever computer you run the app on. If you want the same tasks on
> your phone and your laptop, you'd need a cloud backend (like Supabase) instead —
> this version deliberately skips that for simplicity.

---

## 1. Project Structure

```text
daily_task_app_local/
│
├── app.py
├── requirements.txt
├── README.md
└── tasks.db          ← created automatically the first time you run the app
```

---

## 2. Installation

Create a virtual environment:

```bash
python -m venv venv
```

Activate it:

**Windows**
```bash
venv\Scripts\activate
```

**macOS / Linux**
```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## 3. Run the App

```bash
streamlit run app.py
```

Your browser should open automatically to `http://localhost:8501`.

The first time it runs, it creates `tasks.db` in the same folder and sets up the
`tasks` table automatically — there's nothing else to configure.

---

## 4. Using the App

1. Use the **➕ Add Task** tab to create tasks with a title, description, date, time, priority, category, and optional recurrence.
2. Use the **🗂️ Tasks** tab to view, complete, edit, or delete tasks. Use the sidebar filters to narrow down by date, status, priority, category, or search text.
3. Use the **📊 Dashboard** tab to see today's progress and a weekly completion chart.
4. Completing a recurring task (Daily / Weekly / Monthly) automatically creates its next occurrence.

---

## 5. Backing Up or Moving Your Data

Since everything lives in one file, backing up your tasks is just copying `tasks.db`
somewhere safe. To move your tasks to another computer, copy `tasks.db` into the same
folder as `app.py` on the new machine.

---

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| "Could not open the local task database" | Make sure the folder is writable and you're not running the app from a read-only location. |
| Tasks disappeared | Check that `tasks.db` wasn't deleted or that you're running the app from the same folder each time. |
| Want to start fresh | Close the app and delete `tasks.db` — a new empty one will be created on next run. |

---

Built with Python, Streamlit, and SQLite. 🚀
