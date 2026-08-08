# 📝 My Daily Tasks

Plan your day. Complete your tasks. Stay productive.

A simple, cross-device Daily To-Do Task Manager built with **Python, Streamlit, and Supabase**.
Your tasks are stored in the cloud (Supabase/PostgreSQL), so the same account shows the
same tasks whether you open the app on your laptop, phone, or tablet.

```text
Laptop  →  Supabase  →  Phone
Phone   →  Supabase  →  Laptop
```

---

## 1. Project Structure

```text
daily_task_app/
│
├── app.py
├── requirements.txt
└── README.md
```

Everything lives in `app.py` — no extra folders or modules needed.

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

## 3. Supabase Setup

### Step 1 — Create a Supabase project
Go to [supabase.com](https://supabase.com), sign in, and click **New Project**.
Choose a name, database password, and region, then wait for the project to finish provisioning.

### Step 2 — Open the SQL Editor
In your project's left sidebar, click **SQL Editor** → **New Query**.

### Step 3 — Create the `tasks` table
Paste and run the following SQL:

```sql
create table if not exists public.tasks (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    title text not null,
    description text default '',
    task_date date,
    task_time time,
    priority text default '🟡 Medium',
    category text default 'Other',
    completed boolean default false,
    recurring text default 'None',
    created_at timestamptz default now(),
    completed_at timestamptz
);

create index if not exists tasks_user_id_idx on public.tasks (user_id);
```

### Step 4 — Enable Row Level Security

```sql
alter table public.tasks enable row level security;
```

### Step 5 — Create policies so users only see their own tasks

```sql
create policy "Users can view their own tasks"
on public.tasks for select
using (auth.uid() = user_id);

create policy "Users can insert their own tasks"
on public.tasks for insert
with check (auth.uid() = user_id);

create policy "Users can update their own tasks"
on public.tasks for update
using (auth.uid() = user_id);

create policy "Users can delete their own tasks"
on public.tasks for delete
using (auth.uid() = user_id);
```

### Step 6 — Get your Supabase project URL
In your Supabase project, go to **Project Settings → API**. Copy the **Project URL**.

### Step 7 — Get your API key
On the same page, copy the **anon public** API key (NOT the service role key — the
anon key is safe to use client-side because Row Level Security protects your data).

### Step 8 — Add credentials to Streamlit secrets
Create a folder named `.streamlit` inside `daily_task_app/` and a file called `secrets.toml` inside it:

```text
daily_task_app/
├── app.py
├── requirements.txt
├── README.md
└── .streamlit/
    └── secrets.toml
```

`secrets.toml` contents:

```toml
SUPABASE_URL = "your_supabase_project_url"
SUPABASE_KEY = "your_supabase_anon_key"
```

> ⚠️ Never commit `secrets.toml` to a public repository. If you use git, add
> `.streamlit/secrets.toml` to your `.gitignore` file.

### Step 9 — Run the application

```bash
streamlit run app.py
```

Your browser should open automatically to `http://localhost:8501`.

---

## 4. Using the App

1. **Sign Up** with an email and password on first use (Supabase may require you to confirm your email — check your inbox).
2. **Log In** once your account is confirmed.
3. Use the **➕ Add Task** tab to create tasks with a date, time, priority, category, and optional recurrence.
4. Use the **🗂️ Tasks** tab to view, complete, edit, or delete tasks. Use the sidebar filters to narrow down by date, status, priority, category, or search text.
5. Use the **📊 Dashboard** tab to see today's progress and a weekly completion chart.
6. Completing a recurring task automatically creates its next occurrence (daily/weekly/monthly).

---

## 5. Deployment (Streamlit Community Cloud)

1. Push this folder to a GitHub repository (make sure `.streamlit/secrets.toml` is in `.gitignore` and NOT pushed).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app**, select your repository, branch, and `app.py` as the main file.
4. In the app's **Settings → Secrets**, paste the same contents as your local `secrets.toml`:
   ```toml
   SUPABASE_URL = "your_supabase_project_url"
   SUPABASE_KEY = "your_supabase_anon_key"
   ```
5. Click **Deploy**.

Once deployed, you can open the same app and log in with the same account from:

```text
💻 Laptop
📱 Android / iPhone
💻 Desktop
📱 Tablet
```

and your tasks will stay perfectly in sync across all of them.

---

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| "Missing Supabase configuration" error | Make sure `secrets.toml` exists locally, or Secrets are set on Streamlit Cloud. |
| Can't log in after signing up | Check your email for a confirmation link — Supabase requires email confirmation by default. |
| Tasks not showing up | Confirm the RLS policies from Step 5 were created and that you're logged in as the correct user. |
| "Invalid email or password" | Double-check credentials, or reset your password from the Supabase Auth dashboard. |

---

Built with Python, Streamlit, and Supabase. 🚀
