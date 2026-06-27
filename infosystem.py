import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import re
import os

DB_FILE = os.path.join(os.path.dirname(__file__), "student_directory.db")

def get_conn():
    conn = sqlite3.connect(DB_FILE, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    return conn

def _exec_write(statements):
    conn = get_conn()
    try:
        conn.execute("BEGIN")
        for sql, params in statements:
            conn.execute(sql, params)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

def _exec_read(sql, params=()):
    conn = get_conn()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()

def _exec_read_one(sql, params=()):
    conn = get_conn()
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()

def init_db():
    conn = get_conn()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS colleges (
                college_code TEXT PRIMARY KEY,
                name         TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS programs (
                prog_code    TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                college_code TEXT
            );
            CREATE TABLE IF NOT EXISTS students (
                id        TEXT PRIMARY KEY,
                firstname TEXT NOT NULL,
                lastname  TEXT NOT NULL,
                prog_code TEXT,
                year      TEXT NOT NULL,
                gender    TEXT NOT NULL
            );
        """)
    finally:
        conn.close()
    _migrate_schema()

def _migrate_schema():
    def needs_migration(table, col):
        rows = _exec_read(f"PRAGMA table_info({table})")
        for r in rows:
            if r["name"] == col and r["notnull"] == 1:
                return True
        return False

    if needs_migration("programs", "college_code"):
        conn = get_conn()
        try:
            conn.executescript("""
                BEGIN;
                CREATE TABLE IF NOT EXISTS programs_new (
                    prog_code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    college_code TEXT
                );
                INSERT INTO programs_new SELECT prog_code, name, college_code FROM programs;
                DROP TABLE programs;
                ALTER TABLE programs_new RENAME TO programs;
                COMMIT;
            """)
        finally:
            conn.close()

    if needs_migration("students", "prog_code"):
        conn = get_conn()
        try:
            conn.executescript("""
                BEGIN;
                CREATE TABLE IF NOT EXISTS students_new (
                    id TEXT PRIMARY KEY,
                    firstname TEXT NOT NULL,
                    lastname TEXT NOT NULL,
                    prog_code TEXT,
                    year TEXT NOT NULL,
                    gender TEXT NOT NULL
                );
                INSERT INTO students_new SELECT id, firstname, lastname, prog_code, year, gender FROM students;
                DROP TABLE students;
                ALTER TABLE students_new RENAME TO students;
                COMMIT;
            """)
        finally:
            conn.close()

init_db()

# -- Colleges ----------------------------------------------------------------

def db_get_colleges(search=""):
    if search:
        q = f"%{search}%"
        return _exec_read(
            "SELECT college_code, name FROM colleges "
            "WHERE college_code LIKE ? OR name LIKE ? ORDER BY name", (q, q))
    return _exec_read("SELECT college_code, name FROM colleges ORDER BY name")

def db_add_college(code, name):
    _exec_write([("INSERT INTO colleges (college_code, name) VALUES (?, ?)", (code, name))])

def db_update_college(old_code, new_code, new_name):
    _exec_write([
        ("UPDATE programs SET college_code=? WHERE college_code=?", (new_code, old_code)),
        ("UPDATE colleges SET college_code=?, name=? WHERE college_code=?", (new_code, new_name, old_code)),
    ])

def db_delete_colleges(codes):
    stmts = []
    for c in codes:
        stmts.append(("UPDATE programs SET college_code=NULL WHERE college_code=?", (c,)))
        stmts.append(("DELETE FROM colleges WHERE college_code=?", (c,)))
    _exec_write(stmts)

def db_college_code_exists(code, exclude_code=None):
    if exclude_code:
        return _exec_read_one(
            "SELECT 1 FROM colleges WHERE college_code=? AND college_code!=?",
            (code, exclude_code)) is not None
    return _exec_read_one(
        "SELECT 1 FROM colleges WHERE college_code=?", (code,)) is not None

# -- Programs ----------------------------------------------------------------

def db_get_programs(search=""):
    if search:
        q = f"%{search}%"
        return _exec_read(
            "SELECT p.prog_code, p.name, COALESCE(p.college_code, 'N/A') AS college_code, COALESCE(c.name,'N/A') AS college_name "
            "FROM programs p LEFT JOIN colleges c USING (college_code) "
            "WHERE p.prog_code LIKE ? OR p.name LIKE ? OR c.name LIKE ? ORDER BY p.name",
            (q, q, q))
    return _exec_read(
        "SELECT p.prog_code, p.name, COALESCE(p.college_code, 'N/A') AS college_code, COALESCE(c.name,'N/A') AS college_name "
        "FROM programs p LEFT JOIN colleges c USING (college_code) ORDER BY p.name")

def db_get_all_program_names():
    rows = _exec_read("SELECT name FROM programs ORDER BY name")
    return [r["name"] for r in rows]

def db_add_program(code, name, college_code):
    _exec_write([("INSERT INTO programs (prog_code, name, college_code) VALUES (?, ?, ?)",
                  (code, name, college_code if college_code else None))])

def db_update_program(old_code, new_code, new_name, new_college_code):
    _exec_write([
        ("UPDATE students SET prog_code=? WHERE prog_code=?", (new_code, old_code)),
        ("UPDATE programs SET prog_code=?, name=?, college_code=? WHERE prog_code=?",
         (new_code, new_name, new_college_code if new_college_code else None, old_code)),
    ])

def db_delete_programs(codes):
    stmts = []
    for c in codes:
        stmts.append(("UPDATE students SET prog_code=NULL WHERE prog_code=?", (c,)))
        stmts.append(("DELETE FROM programs WHERE prog_code=?", (c,)))
    _exec_write(stmts)

def db_prog_code_exists(code, exclude_code=None):
    if exclude_code:
        return _exec_read_one(
            "SELECT 1 FROM programs WHERE prog_code=? AND prog_code!=?",
            (code, exclude_code)) is not None
    return _exec_read_one(
        "SELECT 1 FROM programs WHERE prog_code=?", (code,)) is not None

def db_prog_code_from_name(name):
    row = _exec_read_one("SELECT prog_code FROM programs WHERE name=?", (name,))
    return row["prog_code"] if row else ""

def db_get_all_college_options():
    rows = _exec_read("SELECT college_code, name FROM colleges ORDER BY name")
    return [f"{r['college_code']} - {r['name']}" for r in rows]

def db_get_all_college_names():
    rows = _exec_read("SELECT name FROM colleges ORDER BY name")
    return [r["name"] for r in rows]

# -- Students ----------------------------------------------------------------

def db_get_students(search="", filters=None):
    filters = filters or {}
    base = (
        "SELECT s.id, s.lastname || ', ' || s.firstname AS name, "
        "s.gender, s.year, COALESCE(s.prog_code, 'N/A') AS prog_code, COALESCE(p.name,'Not Enrolled') AS program, "
        "COALESCE(p.college_code, 'N/A') AS college_code, COALESCE(c.name,'N/A') AS college "
        "FROM students s "
        "LEFT JOIN programs p ON s.prog_code = p.prog_code "
        "LEFT JOIN colleges c ON p.college_code = c.college_code"
    )
    conditions, params = [], []
    if search:
        q = f"%{search}%"
        conditions.append(
            "(s.id LIKE ? OR s.firstname LIKE ? OR s.lastname LIKE ? "
            "OR s.gender LIKE ? OR s.year LIKE ? OR s.prog_code LIKE ? OR p.name LIKE ? OR p.college_code LIKE ? OR c.name LIKE ?)"
        )
        params.extend([q, q, q, q, q, q, q, q, q])
    for key, col in [("gender","s.gender"),("year","s.year"),("program","p.name"),("college","c.name")]:
        if filters.get(key):
            ph = ",".join("?" * len(filters[key]))
            conditions.append(f"{col} IN ({ph})")
            params.extend(filters[key])
    if conditions:
        base += " WHERE " + " AND ".join(conditions)
    base += " ORDER BY s.lastname, s.firstname"
    return _exec_read(base, params)

def db_get_student_by_id(student_id):
    return _exec_read_one("SELECT * FROM students WHERE id=?", (student_id,))

def db_add_student(sid, firstname, lastname, prog_code, year, gender):
    _exec_write([("INSERT INTO students (id, firstname, lastname, prog_code, year, gender) VALUES (?,?,?,?,?,?)",
                  (sid, firstname, lastname, prog_code if prog_code else None, year, gender))])

def db_update_student(old_sid, new_sid, firstname, lastname, prog_code, year, gender):
    _exec_write([("UPDATE students SET id=?,firstname=?,lastname=?,prog_code=?,year=?,gender=? WHERE id=?",
                  (new_sid, firstname, lastname, prog_code if prog_code else None, year, gender, old_sid))])

def db_delete_students(ids):
    _exec_write([("DELETE FROM students WHERE id=?", (i,)) for i in ids])

def db_student_id_exists(sid, exclude_sid=None):
    if exclude_sid:
        return _exec_read_one(
            "SELECT 1 FROM students WHERE id=? AND id!=?", (sid, exclude_sid)) is not None
    return _exec_read_one("SELECT 1 FROM students WHERE id=?", (sid,)) is not None

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

C = {
    "bg_app":       "#0f1117",   
    "bg_sidebar":   "#161b27",   
    "bg_card":      "#1e2433",   
    "bg_input":     "#252b3b",   
    "bg_row_alt":   "#1a1f2e",   
    "bg_hover":     "#2a3147",   

    "accent":       "#6366f1",   
    "accent_hover": "#818cf8",   
    "accent_muted": "#312e81",   

    "danger":       "#ef4444",   
    "danger_hover": "#f87171",   
    "success":      "#22c55e",   

    "text_primary":   "#f1f5f9", 
    "text_secondary": "#94a3b8", 
    "text_muted":     "#475569", 

    "border":       "#2d3448",   
    "border_focus": "#6366f1",   

    "white":        "#ffffff",
    "sidebar_active": "#6366f1",
}

FONT_FAMILY = "Segoe UI"

def _font(size=11, weight="normal"):
    return (FONT_FAMILY, size, weight)

# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class StudentDirectoryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Student Directory System")
        self.configure(bg=C["bg_app"])

        self.edit_mode = False
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.handle_empty_search)
        self.active_filters = {"gender": [], "year": [], "program": [], "college": []}
        self.filter_win = None
        self.add_popup_win = None
        self.edit_popup_win = None

        self._last_mtime = self._get_db_mtime()

        self._build_styles()
        self._build_layout()

        self.bind_all("<Button-1>", self.check_filter_focus)
        self.center_window(1250, 660)
        self.switch_section("Students")
        self._start_auto_refresh()

    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("Modern.Treeview",
            background=C["bg_card"],
            foreground=C["text_primary"],
            fieldbackground=C["bg_card"],
            rowheight=36,
            borderwidth=0,
            font=_font(10),
        )
        style.configure("Modern.Treeview.Heading",
            background=C["bg_sidebar"],
            foreground=C["text_secondary"],
            font=_font(9, "bold"),
            relief="flat",
            borderwidth=0,
            padding=(12, 8),
        )
        style.map("Modern.Treeview",
            background=[("selected", C["accent_muted"])],
            foreground=[("selected", C["text_primary"])],
        )
        style.map("Modern.Treeview.Heading",
            background=[("active", C["bg_hover"])],
        )

        style.configure("Modern.Vertical.TScrollbar",
            troughcolor=C["bg_card"],
            background=C["border"],
            borderwidth=0,
            arrowsize=0,
            width=6,
        )
        style.map("Modern.Vertical.TScrollbar",
            background=[("active", C["text_muted"])],
        )

    def _build_layout(self):
        self.sidebar = tk.Frame(self, bg=C["bg_sidebar"], width=210)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand_frame = tk.Frame(self.sidebar, bg=C["bg_sidebar"])
        brand_frame.pack(fill="x", padx=20, pady=(28, 24))

        tk.Label(brand_frame, text="📚", font=("Segoe UI Emoji", 22),
                 bg=C["bg_sidebar"], fg=C["accent"]).pack(side="left", padx=(0, 10))

        title_stack = tk.Frame(brand_frame, bg=C["bg_sidebar"])
        title_stack.pack(side="left")
        tk.Label(title_stack, text="Student", font=_font(13, "bold"),
                 bg=C["bg_sidebar"], fg=C["text_primary"]).pack(anchor="w")
        tk.Label(title_stack, text="Directory System", font=_font(8),
                 bg=C["bg_sidebar"], fg=C["text_muted"]).pack(anchor="w")

        tk.Frame(self.sidebar, bg=C["border"], height=1).pack(fill="x", padx=16, pady=(0, 16))

        tk.Label(self.sidebar, text="NAVIGATION", font=_font(7, "bold"),
                 bg=C["bg_sidebar"], fg=C["text_muted"]).pack(anchor="w", padx=20, pady=(0, 8))

        self.active_section = tk.StringVar(value="Students")
        self._nav_buttons = {}
        nav_icons = {"Students": "👤", "Programs": "🎓", "Colleges": "🏛"}
        for section in ["Students", "Programs", "Colleges"]:
            btn = self._make_nav_button(section, nav_icons[section])
            self._nav_buttons[section] = btn

        tk.Frame(self.sidebar, bg=C["bg_sidebar"]).pack(fill="both", expand=True)
        tk.Frame(self.sidebar, bg=C["border"], height=1).pack(fill="x", padx=16, pady=(0, 16))

        self._add_btn = tk.Frame(self.sidebar, bg=C["accent"], cursor="hand2")
        self._add_btn.pack(fill="x", padx=16, pady=(0, 8))
        self._add_btn.bind("<Button-1>", lambda e: self.add_entry_popup())
        self._add_btn.bind("<Enter>", lambda e: self._add_btn.config(bg=C["accent_hover"]))
        self._add_btn.bind("<Leave>", lambda e: self._add_btn.config(bg=C["accent"]))

        add_inner = tk.Frame(self._add_btn, bg=C["accent"])
        add_inner.pack(padx=14, pady=10)
        add_inner.bind("<Button-1>", lambda e: self.add_entry_popup())
        add_inner.bind("<Enter>", lambda e: [self._add_btn.config(bg=C["accent_hover"]),
                                              add_inner.config(bg=C["accent_hover"])])
        add_inner.bind("<Leave>", lambda e: [self._add_btn.config(bg=C["accent"]),
                                              add_inner.config(bg=C["accent"])])
        add_lbl = tk.Label(add_inner, text="+ Add Entry", font=_font(10, "bold"),
                 bg=C["accent"], fg=C["white"])
        add_lbl.pack(side="left")
        add_lbl.bind("<Button-1>", lambda e: self.add_entry_popup())
        add_lbl.bind("<Enter>", lambda e: [self._add_btn.config(bg=C["accent_hover"]),
                                            add_inner.config(bg=C["accent_hover"]),
                                            add_lbl.config(bg=C["accent_hover"])])
        add_lbl.bind("<Leave>", lambda e: [self._add_btn.config(bg=C["accent"]),
                                            add_inner.config(bg=C["accent"]),
                                            add_lbl.config(bg=C["accent"])])

        self._edit_frame = tk.Frame(self.sidebar, bg=C["bg_card"], cursor="hand2")
        self._edit_frame.pack(fill="x", padx=16, pady=(0, 20))
        self._edit_frame.bind("<Button-1>", lambda e: self.toggle_edit_mode())
        self._edit_frame.bind("<Enter>", lambda e: self._edit_frame.config(bg=C["bg_hover"]))
        self._edit_frame.bind("<Leave>", lambda e: self._on_edit_btn_leave())

        edit_inner = tk.Frame(self._edit_frame, bg=C["bg_card"])
        edit_inner.pack(padx=14, pady=10)
        edit_inner.bind("<Button-1>", lambda e: self.toggle_edit_mode())
        edit_inner.bind("<Enter>", lambda e: [self._edit_frame.config(bg=C["bg_hover"]),
                                               edit_inner.config(bg=C["bg_hover"])])
        edit_inner.bind("<Leave>", lambda e: [self._on_edit_btn_leave(),
                                               edit_inner.config(bg=self._edit_bg())])
        self._edit_label = tk.Label(edit_inner, text="✏  Edit Mode", font=_font(10),
                                     bg=C["bg_card"], fg=C["text_secondary"])
        self._edit_label.pack(side="left")
        self._edit_label.bind("<Button-1>", lambda e: self.toggle_edit_mode())

        self.content_frame = tk.Frame(self, bg=C["bg_app"])
        self.content_frame.pack(side="right", fill="both", expand=True)
        self.content_frame.columnconfigure(0, weight=1)
        self.content_frame.rowconfigure(1, weight=1)

    def _edit_bg(self):
        return C["accent_muted"] if self.edit_mode else C["bg_card"]

    def _on_edit_btn_leave(self):
        bg = self._edit_bg()
        self._edit_frame.config(bg=bg)

    def _make_nav_button(self, section, icon):
        frame = tk.Frame(self.sidebar, bg=C["bg_sidebar"], cursor="hand2")
        frame.pack(fill="x", padx=10, pady=2)

        inner = tk.Frame(frame, bg=C["bg_sidebar"])
        inner.pack(fill="x", padx=6, pady=1)

        icon_lbl = tk.Label(inner, text=icon, font=("Segoe UI Emoji", 12),
                             bg=C["bg_sidebar"], fg=C["text_secondary"], width=2)
        icon_lbl.pack(side="left", padx=(8, 6), pady=8)

        text_lbl = tk.Label(inner, text=section, font=_font(11),
                             bg=C["bg_sidebar"], fg=C["text_secondary"], anchor="w")
        text_lbl.pack(side="left", fill="x", expand=True, pady=8)

        def on_click(e=None):
            self.reset_all_and_switch(section)

        def on_enter(e=None):
            if self.active_section.get() != section:
                for w in [frame, inner, icon_lbl, text_lbl]:
                    w.config(bg=C["bg_hover"])

        def on_leave(e=None):
            if self.active_section.get() != section:
                for w in [frame, inner, icon_lbl, text_lbl]:
                    w.config(bg=C["bg_sidebar"])

        for w in [frame, inner, icon_lbl, text_lbl]:
            w.bind("<Button-1>", on_click)
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)

        return {"frame": frame, "inner": inner, "icon": icon_lbl, "text": text_lbl}

    def _update_nav_active(self, section):
        for s, widgets in self._nav_buttons.items():
            if s == section:
                for w in [widgets["frame"], widgets["inner"]]:
                    w.config(bg=C["accent_muted"])
                widgets["icon"].config(bg=C["accent_muted"], fg=C["accent"])
                widgets["text"].config(bg=C["accent_muted"], fg=C["text_primary"],
                                       font=_font(11, "bold"))
            else:
                for w in [widgets["frame"], widgets["inner"]]:
                    w.config(bg=C["bg_sidebar"])
                widgets["icon"].config(bg=C["bg_sidebar"], fg=C["text_muted"])
                widgets["text"].config(bg=C["bg_sidebar"], fg=C["text_secondary"],
                                       font=_font(11))

    def _get_db_mtime(self):
        try:
            return os.path.getmtime(DB_FILE)
        except OSError:
            return 0

    def _start_auto_refresh(self):
        def poll():
            mtime = self._get_db_mtime()
            if mtime != self._last_mtime:
                self._last_mtime = mtime
                self.switch_section(self.active_section.get())
            self.after(1500, poll)
        self.after(1500, poll)

    def handle_empty_search(self, *args):
        if self.search_var.get() == "":
            self.switch_section(self.active_section.get())

    def toggle_edit_mode(self):
        self.edit_mode = not self.edit_mode
        bg = self._edit_bg()
        fg_label = C["accent"] if self.edit_mode else C["text_secondary"]
        self._edit_frame.config(bg=bg)
        self._edit_label.config(bg=bg, fg=fg_label)
        for child in self._edit_frame.winfo_children():
            child.config(bg=bg)
            for c2 in child.winfo_children():
                if c2 != self._edit_label:
                    c2.config(bg=bg)
        self.switch_section(self.active_section.get())

    def reset_all_and_switch(self, section):
        self.search_var.set("")
        self.active_filters = {"gender": [], "year": [], "program": [], "college": []}
        self.edit_mode = False
        self.active_section.set(section)
        bg = self._edit_bg()
        self._edit_frame.config(bg=bg)
        self._edit_label.config(bg=bg, fg=C["text_secondary"])
        for child in self._edit_frame.winfo_children():
            child.config(bg=bg)
            for c2 in child.winfo_children():
                if c2 != self._edit_label:
                    c2.config(bg=bg)
        self.switch_section(section)

    def center_window(self, width, height):
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def center_window_small(self, win, w, h):
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")

    def _styled_entry(self, parent, **kwargs):
        e = tk.Entry(parent,
                     bg=C["bg_input"],
                     fg=C["text_primary"],
                     insertbackground=C["text_primary"],
                     relief="flat",
                     font=_font(10),
                     bd=0,
                     highlightthickness=1,
                     highlightbackground=C["border"],
                     highlightcolor=C["border_focus"],
                     **kwargs)
        return e

    def _styled_button(self, parent, text, command, style="primary", **kwargs):
        styles = {
            "primary":  {"bg": C["accent"],  "fg": C["white"],        "abg": C["accent_hover"]},
            "danger":   {"bg": C["danger"],  "fg": C["white"],        "abg": C["danger_hover"]},
            "success":  {"bg": "#16a34a",    "fg": C["white"],        "abg": C["success"]},
            "neutral":  {"bg": C["bg_card"], "fg": C["text_secondary"],"abg": C["bg_hover"]},
            "ghost":    {"bg": C["bg_app"],  "fg": C["text_muted"],   "abg": C["bg_card"]},
        }
        s = styles.get(style, styles["primary"])
        btn = tk.Button(parent,
                        text=text,
                        bg=s["bg"],
                        fg=s["fg"],
                        activebackground=s["abg"],
                        activeforeground=s["fg"],
                        font=_font(10, "bold"),
                        relief="flat",
                        bd=0,
                        cursor="hand2",
                        command=command,
                        padx=16,
                        pady=7,
                        **kwargs)
        return btn

    def _field_label(self, parent, text):
        tk.Label(parent, text=text, font=_font(9, "bold"),
                 bg=C["bg_card"], fg=C["text_secondary"]).pack(anchor="w", pady=(12, 3))

    def create_popup_dropdown(self, parent, label, options, is_filter=False,
                               filter_key=None, refresh_callback=None, default_value=""):
        frame = tk.Frame(parent, bg=C["bg_card"])
        frame.pack(fill="x", pady=2)

        tk.Label(frame, text=label, font=_font(9, "bold"),
                 bg=C["bg_card"], fg=C["text_secondary"]).pack(anchor="w", pady=(10, 3))

        var = tk.StringVar(value=default_value)
        ent = self._styled_entry(frame, textvariable=var)
        ent.pack(fill="x", ipady=5)

        drop_outer = tk.Frame(frame, bg=C["border"], highlightthickness=0)
        canvas = tk.Canvas(drop_outer, bg=C["bg_input"],
                           height=100 if is_filter else 80, highlightthickness=0)
        scrollbar = ttk.Scrollbar(drop_outer, orient="vertical", command=canvas.yview,
                                   style="Modern.Vertical.TScrollbar")
        drop_inner = tk.Frame(canvas, bg=C["bg_input"])
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.create_window((0, 0), window=drop_inner, anchor="nw")
        selected_val = {"val": default_value}
        matches = []

        def update_results(*args):
            nonlocal matches
            for child in drop_inner.winfo_children():
                child.destroy()
            query = var.get().lower()
            matches = [
                o for o in options
                if query in o.lower() and
                (not is_filter or o not in self.pending_filters[filter_key])
            ]
            if matches:
                drop_outer.pack(fill="x", pady=(2, 0))
                for i, m in enumerate(matches):
                    is_first = (i == 0 and query != "")
                    bg_c = C["accent_muted"] if is_first else C["bg_input"]
                    fg_c = C["accent"] if is_first else C["text_primary"]
                    item_btn = tk.Button(
                        drop_inner, text=m, anchor="w",
                        bg=bg_c, fg=fg_c,
                        activebackground=C["bg_hover"],
                        activeforeground=C["text_primary"],
                        relief="flat", font=_font(9),
                        padx=10, pady=5,
                        command=lambda v=m: select_action(v)
                    )
                    item_btn.pack(fill="x")
                drop_inner.update_idletasks()
                canvas.config(scrollregion=canvas.bbox("all"))
                if len(matches) > 3:
                    scrollbar.pack(side="right", fill="y")
                else:
                    scrollbar.pack_forget()
                canvas.pack(side="left", fill="both", expand=True)
            else:
                drop_outer.pack_forget()

        def select_action(v):
            if is_filter:
                self.pending_filters[filter_key].append(v)
                var.set("")
                refresh_callback()
            else:
                selected_val["val"] = v
                var.set(v)
            drop_outer.pack_forget()

        var.trace_add("write", update_results)
        ent.bind("<FocusIn>", lambda e: update_results())
        ent.bind("<Return>", lambda e: select_action(matches[0]) if matches else None)
        return selected_val, ent

    def switch_section(self, section):
        self._update_nav_active(section)
        if section == "Students": self.show_students()
        elif section == "Programs": self.show_programs()
        elif section == "Colleges": self.show_colleges()

    # ------------------------------------------------------------------
    # Sorting core engine
    # ------------------------------------------------------------------
    def sort_column(self, col, reverse):
        data_list = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        
        def natural_sort_key(s):
            return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]
            
        data_list.sort(key=lambda t: natural_sort_key(t[0]), reverse=reverse)
        
        for index, (val, k) in enumerate(data_list):
            self.tree.move(k, "", index)
            if self.tree.item(k, "values")[0] != "[X]":
                tag = "odd" if index % 2 == 0 else "even"
                self.tree.item(k, tags=(tag,))
                
        self.tree.heading(col, command=lambda _col=col: self.sort_column(_col, not reverse))

    # ------------------------------------------------------------------
    # Table display
    # ------------------------------------------------------------------
    def display_table(self, columns, rows, section_type):
        for w in self.content_frame.winfo_children():
            w.destroy()

        topbar = tk.Frame(self.content_frame, bg=C["bg_app"])
        topbar.pack(fill="x", padx=28, pady=(24, 0))

        title_group = tk.Frame(topbar, bg=C["bg_app"])
        title_group.pack(side="left")
        tk.Label(title_group, text=section_type, font=_font(20, "bold"),
                 bg=C["bg_app"], fg=C["text_primary"]).pack(side="left")
        count_lbl = tk.Label(title_group, text=f"  {len(rows)} records",
                             font=_font(11), bg=C["bg_app"], fg=C["text_muted"])
        count_lbl.pack(side="left", padx=(8, 0), pady=6)

        ctrls = tk.Frame(topbar, bg=C["bg_app"])
        ctrls.pack(side="right")

        if self.edit_mode:
            self._styled_button(ctrls, "🗑  Delete Selected", style="danger",
                                 command=lambda: self.delete_selected(section_type)).pack(side="left", padx=4)
            edit_cmd = {
                "Students": self.edit_selected_student,
                "Programs": self.edit_selected_program,
                "Colleges": self.edit_selected_college,
            }.get(section_type)
            if edit_cmd:
                self._styled_button(ctrls, "✎  Edit Selected", style="success",
                                     command=edit_cmd).pack(side="left", padx=4)
            self._styled_button(ctrls, "✕  Cancel", style="neutral",
                                 command=self.toggle_edit_mode).pack(side="left", padx=4)
        else:
            search_wrap = tk.Frame(ctrls, bg=C["bg_input"],
                                   highlightthickness=1,
                                   highlightbackground=C["border"],
                                   highlightcolor=C["border_focus"])
            search_wrap.pack(side="left", padx=4)

            tk.Label(search_wrap, text="🔍", font=("Segoe UI Emoji", 10),
                     bg=C["bg_input"], fg=C["text_muted"]).pack(side="left", padx=(10, 4))
            s_ent = tk.Entry(search_wrap, textvariable=self.search_var,
                             font=_font(10), width=24,
                             bg=C["bg_input"], fg=C["text_primary"],
                             insertbackground=C["text_primary"],
                             relief="flat", bd=0)
            s_ent.pack(side="left", ipady=7, padx=(0, 10))
            s_ent.bind("<Return>", lambda e: self.switch_section(section_type))

            self._styled_button(ctrls, "Search", style="primary",
                                 command=lambda: self.switch_section(section_type)).pack(side="left", padx=4)
            if section_type == "Students":
                filter_count = sum(len(v) for v in self.active_filters.values())
                f_label = f"Sort  ▾" if filter_count == 0 else f"Sort ({filter_count})  ▾"
                f_btn = self._styled_button(ctrls, f_label, style="neutral", command=None)
                f_btn.config(command=lambda: self.show_filter_menu(f_btn))
                f_btn.pack(side="left", padx=4)

        card = tk.Frame(self.content_frame, bg=C["bg_card"],
                        highlightthickness=1, highlightbackground=C["border"])
        card.pack(fill="both", expand=True, padx=28, pady=16)
        card.columnconfigure(0, weight=1)
        card.rowconfigure(0, weight=1)

        display_cols = ["Select"] + columns if self.edit_mode else columns
        self.tree = ttk.Treeview(card, columns=display_cols, show="headings",
                                 style="Modern.Treeview", selectmode="none")

        for col in self.tree["columns"]:
            self.tree.heading(col, text=col.upper(), command=lambda _col=col: self.sort_column(_col, False))
            if col == "Select":
                self.tree.column(col, width=60, minwidth=60, anchor="center", stretch=False)
            elif col in ("ID", "Code", "Prog Code", "Coll Code"):
                self.tree.column(col, width=110, minwidth=80, anchor="center", stretch=False)
            elif col in ("Gender", "Year"):
                self.tree.column(col, width=80, minwidth=70, anchor="center", stretch=False)
            else:
                self.tree.column(col, width=160, minwidth=100, anchor="w", stretch=True)

        tree_scroll = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview,
                                     style="Modern.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side="right", fill="y", pady=1, padx=(0, 2))
        self.tree.pack(fill="both", expand=True, padx=1, pady=1)

        self.tree.tag_configure("odd",  background=C["bg_card"])
        self.tree.tag_configure("even", background=C["bg_row_alt"])
        self.tree.tag_configure("checked", background=C["accent_muted"])

        if rows:
            for idx, r in enumerate(rows):
                tag = "odd" if idx % 2 == 0 else "even"
                vals = ["[ ]"] + list(r) if self.edit_mode else list(r)
                self.tree.insert("", "end", values=vals, tags=(tag,))
        else:
            self.tree.pack_forget()
            tree_scroll.pack_forget()
            empty_frame = tk.Frame(card, bg=C["bg_card"])
            empty_frame.place(relx=0.5, rely=0.45, anchor="center")
            tk.Label(empty_frame, text="📭", font=("Segoe UI Emoji", 32),
                     bg=C["bg_card"], fg=C["text_muted"]).pack()
            msg = "No search results found." if self.search_var.get().strip() else "No records yet."
            tk.Label(empty_frame, text=msg, font=_font(12),
                     bg=C["bg_card"], fg=C["text_muted"]).pack(pady=(8, 0))

        if self.edit_mode:
            self.tree.bind("<ButtonRelease-1>", self.on_tree_click)

    def show_students(self):
        rows = db_get_students(search=self.search_var.get(), filters=self.active_filters)
        self.display_table(["ID", "Name", "Gender", "Year", "Prog Code", "Program", "Coll Code", "College"], rows, "Students")

    def show_programs(self):
        rows = db_get_programs(search=self.search_var.get())
        self.display_table(["Code", "Program Name", "Coll Code", "College"], rows, "Programs")

    def show_colleges(self):
        rows = db_get_colleges(search=self.search_var.get())
        self.display_table(["Code", "College Name"], rows, "Colleges")

    def _make_popup(self, title, width, height):
        win = tk.Toplevel(self)
        win.title(title)
        win.configure(bg=C["bg_app"])
        win.transient(self)
        win.grab_set()
        self.center_window_small(win, width, height)
        win.resizable(False, False)

        bar = tk.Frame(win, bg=C["bg_sidebar"])
        bar.pack(fill="x")
        tk.Label(bar, text=title, font=_font(13, "bold"),
                 bg=C["bg_sidebar"], fg=C["text_primary"],
                 pady=16, padx=24).pack(side="left")

        container = tk.Frame(win, bg=C["bg_card"], padx=24, pady=20)
        container.pack(fill="both", expand=True, padx=16, pady=16)
        return win, container

    def add_entry_popup(self):
        if self.add_popup_win and self.add_popup_win.winfo_exists():
            self.add_popup_win.lift()
            return
        current = self.active_section.get()
        self.add_popup_win, container = self._make_popup(f"Add {current}", 420, 700)

        if current == "Students":
            self._field_label(container, "ID Number")
            id_ent = self._styled_entry(container)
            id_ent.pack(fill="x", ipady=6)
            err_msg = tk.Label(container,
                text="Invalid format. Use YYYY-NNNN (e.g. 2024-0001)",
                font=_font(8, "italic"), fg=C["danger"], bg=C["bg_card"], justify="right")

            self._field_label(container, "First Name")
            fn_ent = self._styled_entry(container)
            fn_ent.pack(fill="x", ipady=6)

            self._field_label(container, "Last Name")
            ln_ent = self._styled_entry(container)
            ln_ent.pack(fill="x", ipady=6)

            prog_names = ["Not Enrolled"] + db_get_all_program_names()
            prog_sel, _ = self.create_popup_dropdown(container, "Program", prog_names)
            year_sel, _ = self.create_popup_dropdown(container, "Year Level", ["1", "2", "3", "4", "5"])
            gen_sel,  _ = self.create_popup_dropdown(container, "Gender", ["Male", "Female", "Other"])

            def save():
                err_msg.pack_forget()
                raw_id = id_ent.get().strip()
                if not re.match(r"^\d{4}-\d{4}$", raw_id):
                    err_msg.pack(anchor="e", pady=(2, 0))
                    return
                if db_student_id_exists(raw_id):
                    messagebox.showerror("Error", f"Student ID '{raw_id}' already exists.")
                    return
                firstname = fn_ent.get().strip().title()
                lastname  = ln_ent.get().strip().title()
                prog_name = prog_sel["val"]
                year      = year_sel["val"]
                gender    = gen_sel["val"]
                if not all([firstname, lastname, prog_name, year, gender]):
                    messagebox.showwarning("!", "Fill all fields.")
                    return
                prog_code = None if prog_name == "Not Enrolled" else db_prog_code_from_name(prog_name)
                if prog_name != "Not Enrolled" and not prog_code:
                    messagebox.showerror("Error", "Invalid program selected.")
                    return
                db_add_student(raw_id, firstname, lastname, prog_code, year, gender)
                self._last_mtime = self._get_db_mtime()
                self.show_students()
                self.add_popup_win.destroy()

            btn_row = tk.Frame(container, bg=C["bg_card"])
            btn_row.pack(fill="x", pady=(20, 0))
            self._styled_button(btn_row, "Save", command=save, style="primary").pack(side="right")
            self._styled_button(btn_row, "Cancel", command=self.add_popup_win.destroy,
                                 style="neutral").pack(side="right", padx=(0, 8))

        elif current == "Programs":
            self._field_label(container, "Program Code")
            c_ent = self._styled_entry(container)
            c_ent.pack(fill="x", ipady=6)

            self._field_label(container, "Program Name")
            n_ent = self._styled_entry(container)
            n_ent.pack(fill="x", ipady=6)

            coll_opts = ["N/A"] + db_get_all_college_options()
            coll_sel, _ = self.create_popup_dropdown(container, "College", coll_opts)

            def save_p():
                code = c_ent.get().strip().upper()
                name = n_ent.get().strip().title()
                coll_val = coll_sel["val"]
                if not all([code, name, coll_val]):
                    messagebox.showwarning("!", "Fill all fields.")
                    return
                if db_prog_code_exists(code):
                    messagebox.showerror("Error", f"Program code '{code}' already exists.")
                    return
                college_code = None if coll_val == "N/A" else (coll_val.split(" - ")[0] if " - " in coll_val else None)
                db_add_program(code, name, college_code)
                self._last_mtime = self._get_db_mtime()
                self.show_programs()
                self.add_popup_win.destroy()

            btn_row = tk.Frame(container, bg=C["bg_card"])
            btn_row.pack(fill="x", pady=(20, 0))
            self._styled_button(btn_row, "Save", command=save_p, style="primary").pack(side="right")
            self._styled_button(btn_row, "Cancel", command=self.add_popup_win.destroy,
                                 style="neutral").pack(side="right", padx=(0, 8))

        elif current == "Colleges":
            self._field_label(container, "College Code")
            c_ent = self._styled_entry(container)
            c_ent.pack(fill="x", ipady=6)

            self._field_label(container, "College Name")
            n_ent = self._styled_entry(container)
            n_ent.pack(fill="x", ipady=6)

            def save_c():
                code = c_ent.get().strip().upper()
                name = n_ent.get().strip().title()
                if not all([code, name]):
                    messagebox.showwarning("!", "Fill all fields.")
                    return
                if db_college_code_exists(code):
                    messagebox.showerror("Error", f"College code '{code}' already exists.")
                    return
                db_add_college(code, name)
                self._last_mtime = self._get_db_mtime()
                self.show_colleges()
                self.add_popup_win.destroy()

            btn_row = tk.Frame(container, bg=C["bg_card"])
            btn_row.pack(fill="x", pady=(20, 0))
            self._styled_button(btn_row, "Save", command=save_c, style="primary").pack(side="right")
            self._styled_button(btn_row, "Cancel", command=self.add_popup_win.destroy,
                                 style="neutral").pack(side="right", padx=(0, 8))

    def _get_one_selected(self, label):
        selected = [
            item for item in self.tree.get_children()
            if self.tree.item(item, "values")[0] == "[X]"
        ]
        if not selected:
            messagebox.showwarning("Warning", f"Please select a {label} to edit.")
            return None
        if len(selected) > 1:
            messagebox.showwarning("Warning", f"Please select only one {label} to edit.")
            return None
        return selected[0]

    def edit_selected_student(self):
        item = self._get_one_selected("student")
        if not item:
            return
        student_id = self.tree.item(item, "values")[1]
        student_data = db_get_student_by_id(student_id)
        if not student_data:
            messagebox.showerror("Error", "Student data not found.")
            return
        self.open_edit_student_popup(dict(student_data))

    def open_edit_student_popup(self, student_data):
        if self.edit_popup_win and self.edit_popup_win.winfo_exists():
            self.edit_popup_win.lift()
            return
        self.edit_popup_win, container = self._make_popup("Edit Student", 420, 740)

        self._field_label(container, "ID Number")
        id_ent = self._styled_entry(container)
        id_ent.pack(fill="x", ipady=6)
        id_ent.insert(0, student_data["id"])
        id_err = tk.Label(container, text="", font=_font(8, "italic"),
                          fg=C["danger"], bg=C["bg_card"], justify="right", wraplength=360)

        self._field_label(container, "First Name")
        fn_ent = self._styled_entry(container)
        fn_ent.pack(fill="x", ipady=6)
        fn_ent.insert(0, student_data["firstname"])

        self._field_label(container, "Last Name")
        ln_ent = self._styled_entry(container)
        ln_ent.pack(fill="x", ipady=6)
        ln_ent.insert(0, student_data["lastname"])

        prog_names = ["Not Enrolled"] + db_get_all_program_names()
        prog_row = _exec_read_one("SELECT name FROM programs WHERE prog_code=?", (student_data["prog_code"],))
        current_prog_name = prog_row["name"] if prog_row else "Not Enrolled"

        prog_sel, _ = self.create_popup_dropdown(container, "Program", prog_names,
                                                  default_value=current_prog_name)
        year_sel, _ = self.create_popup_dropdown(container, "Year Level", ["1", "2", "3", "4", "5"],
                                                  default_value=student_data["year"])
        gen_sel, _  = self.create_popup_dropdown(container, "Gender", ["Male", "Female", "Other"],
                                                  default_value=student_data["gender"])

        def save_changes():
            id_err.pack_forget()
            new_id = id_ent.get().strip()
            if not re.match(r"^\d{4}-\d{4}$", new_id):
                id_err.config(text="ID must follow YYYY-NNNN format (e.g. 2024-0001)")
                id_err.pack(anchor="e", pady=(2, 0))
                return
            if db_student_id_exists(new_id, exclude_sid=student_data["id"]):
                id_err.config(text=f"Student ID '{new_id}' already exists.")
                id_err.pack(anchor="e", pady=(2, 0))
                return
            new_firstname = fn_ent.get().strip().title()
            new_lastname  = ln_ent.get().strip().title()
            new_gender    = gen_sel["val"]
            new_year      = year_sel["val"]
            new_prog_name = prog_sel["val"]
            if not all([new_firstname, new_lastname, new_gender, new_year, new_prog_name]):
                messagebox.showwarning("Warning", "Please fill all fields.")
                return
            new_prog_code = None if new_prog_name == "Not Enrolled" else db_prog_code_from_name(new_prog_name)
            if new_prog_name != "Not Enrolled" and not new_prog_code:
                messagebox.showerror("Error", "Invalid program selected.")
                return
            db_update_student(student_data["id"], new_id, new_firstname, new_lastname,
                              new_prog_code, new_year, new_gender)
            self._last_mtime = self._get_db_mtime()
            self.show_students()
            self.edit_popup_win.destroy()
            messagebox.showinfo("Success", "Student information updated successfully!")

        btn_row = tk.Frame(container, bg=C["bg_card"])
        btn_row.pack(fill="x", pady=(20, 0))
        self._styled_button(btn_row, "Save Changes", command=save_changes, style="primary").pack(side="right")
        self._styled_button(btn_row, "Cancel", command=self.edit_popup_win.destroy,
                             style="neutral").pack(side="right", padx=(0, 8))

    def edit_selected_program(self):
        item = self._get_one_selected("program")
        if not item:
            return
        prog_code = self.tree.item(item, "values")[1]
        prog_data = _exec_read_one(
            "SELECT p.prog_code, p.name, p.college_code, COALESCE(c.name,'') AS college_name "
            "FROM programs p LEFT JOIN colleges c USING(college_code) WHERE p.prog_code=?",
            (prog_code,))
        if not prog_data:
            messagebox.showerror("Error", "Program data not found.")
            return
        self.open_edit_program_popup(dict(prog_data))

    def open_edit_program_popup(self, prog_data):
        if self.edit_popup_win and self.edit_popup_win.winfo_exists():
            self.edit_popup_win.lift()
            return
        self.edit_popup_win, container = self._make_popup("Edit Program", 420, 500)

        self._field_label(container, "Program Code")
        code_ent = self._styled_entry(container)
        code_ent.pack(fill="x", ipady=6)
        code_ent.insert(0, prog_data["prog_code"])
        code_err = tk.Label(container, text="", font=_font(8, "italic"),
                            fg=C["danger"], bg=C["bg_card"], justify="right")

        self._field_label(container, "Program Name")
        name_ent = self._styled_entry(container)
        name_ent.pack(fill="x", ipady=6)
        name_ent.insert(0, prog_data["name"])

        coll_opts = ["N/A"] + db_get_all_college_options()
        current_coll = "N/A"
        if prog_data["college_code"]:
            for opt in coll_opts:
                if opt.startswith(prog_data["college_code"] + " - "):
                    current_coll = opt
                    break
        coll_sel, _ = self.create_popup_dropdown(container, "College", coll_opts, default_value=current_coll)

        def save_changes():
            code_err.pack_forget()
            new_code = code_ent.get().strip().upper()
            new_name = name_ent.get().strip().title()
            coll_val = coll_sel["val"]
            if not all([new_code, new_name, coll_val]):
                messagebox.showwarning("Warning", "Fill all fields.")
                return
            if db_prog_code_exists(new_code, exclude_code=prog_data["prog_code"]):
                code_err.config(text=f"Program code '{new_code}' already exists.")
                code_err.pack(anchor="e", pady=(2, 0))
                return
            new_college_code = None if coll_val == "N/A" else (coll_val.split(" - ")[0] if " - " in coll_val else None)
            db_update_program(prog_data["prog_code"], new_code, new_name, new_college_code)
            self._last_mtime = self._get_db_mtime()
            self.show_programs()
            self.edit_popup_win.destroy()
            messagebox.showinfo("Success", "Program updated successfully!")

        btn_row = tk.Frame(container, bg=C["bg_card"])
        btn_row.pack(fill="x", pady=(20, 0))
        self._styled_button(btn_row, "Save Changes", command=save_changes, style="primary").pack(side="right")
        self._styled_button(btn_row, "Cancel", command=self.edit_popup_win.destroy,
                             style="neutral").pack(side="right", padx=(0, 8))

    def edit_selected_college(self):
        item = self._get_one_selected("college")
        if not item:
            return
        college_code = self.tree.item(item, "values")[1]
        coll_data = _exec_read_one(
            "SELECT college_code, name FROM colleges WHERE college_code=?", (college_code,))
        if not coll_data:
            messagebox.showerror("Error", "College data not found.")
            return
        self.open_edit_college_popup(dict(coll_data))

    def open_edit_college_popup(self, coll_data):
        if self.edit_popup_win and self.edit_popup_win.winfo_exists():
            self.edit_popup_win.lift()
            return
        self.edit_popup_win, container = self._make_popup("Edit College", 420, 360)

        self._field_label(container, "College Code")
        code_ent = self._styled_entry(container)
        code_ent.pack(fill="x", ipady=6)
        code_ent.insert(0, coll_data["college_code"])
        code_err = tk.Label(container, text="", font=_font(8, "italic"),
                            fg=C["danger"], bg=C["bg_card"], justify="right")

        self._field_label(container, "College Name")
        name_ent = self._styled_entry(container)
        name_ent.pack(fill="x", ipady=6)
        name_ent.insert(0, coll_data["name"])

        def save_changes():
            code_err.pack_forget()
            new_code = code_ent.get().strip().upper()
            new_name = name_ent.get().strip().title()
            if not all([new_code, new_name]):
                messagebox.showwarning("Warning", "Fill all fields.")
                return
            if db_college_code_exists(new_code, exclude_code=coll_data["college_code"]):
                code_err.config(text=f"College code '{new_code}' already exists.")
                code_err.pack(anchor="e", pady=(2, 0))
                return
            db_update_college(coll_data["college_code"], new_code, new_name)
            self._last_mtime = self._get_db_mtime()
            self.show_colleges()
            self.edit_popup_win.destroy()
            messagebox.showinfo("Success", "College updated successfully!")

        btn_row = tk.Frame(container, bg=C["bg_card"])
        btn_row.pack(fill="x", pady=(20, 0))
        self._styled_button(btn_row, "Save Changes", command=save_changes, style="primary").pack(side="right")
        self._styled_button(btn_row, "Cancel", command=self.edit_popup_win.destroy,
                             style="neutral").pack(side="right", padx=(0, 8))

    def show_filter_menu(self, widget):
        if self.filter_win and self.filter_win.winfo_exists():
            self.filter_win.destroy()
            self.filter_win = None
            return
        self.pending_filters = {k: list(v) for k, v in self.active_filters.items()}
        self.filter_win = tk.Toplevel(self)
        self.filter_win.withdraw()
        self.filter_win.overrideredirect(True)
        w_width, w_height = 340, 500
        app_x, app_y = self.winfo_rootx(), self.winfo_rooty()
        app_w, app_h = self.winfo_width(), self.winfo_height()
        start_x = widget.winfo_rootx() - 150
        start_y = widget.winfo_rooty() + 36
        if start_x + w_width > app_x + app_w: start_x = (app_x + app_w) - w_width - 10
        if start_x < app_x: start_x = app_x + 10
        if start_y + w_height > app_y + app_h: start_y = (app_y + app_h) - w_height - 10
        self.filter_win.geometry(f"{w_width}x{w_height}+{start_x}+{start_y}")
        self.filter_win.deiconify()

        container = tk.Frame(self.filter_win, bg=C["bg_card"],
                             highlightthickness=1, highlightbackground=C["border"])
        container.pack(fill="both", expand=True)

        hdr = tk.Frame(container, bg=C["bg_sidebar"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="Filters", font=_font(12, "bold"),
                 bg=C["bg_sidebar"], fg=C["text_primary"],
                 padx=16, pady=12).pack(side="left")

        def apply_filters():
            self.active_filters = self.pending_filters
            self.show_students()
            self.filter_win.destroy()
            self.filter_win = None

        bottom_bar = tk.Frame(container, bg=C["bg_sidebar"])
        bottom_bar.pack(side="bottom", fill="x")
        self._styled_button(bottom_bar, "Apply Filters", command=apply_filters,
                             style="primary").pack(fill="x", padx=16, pady=12)

        scroll_cont = tk.Frame(container, bg=C["bg_card"])
        scroll_cont.pack(fill="both", expand=True)

        c_area = tk.Frame(scroll_cont, bg=C["bg_card"])
        c_area.pack(fill="x", padx=12)

        tag_canvas = tk.Canvas(scroll_cont, bg=C["bg_app"], height=0, highlightthickness=0)
        tag_frame = tk.Frame(tag_canvas, bg=C["bg_app"])
        cl_btn_cont = tk.Frame(scroll_cont, bg=C["bg_card"])

        def refresh_tags():
            for c in tag_frame.winfo_children():
                c.destroy()
            total_tags = sum(len(v) for v in self.pending_filters.values())
            for w in cl_btn_cont.winfo_children():
                w.destroy()
            if total_tags > 0:
                tag_canvas.pack(fill="x", padx=12, pady=4)
                cl_btn_cont.pack(fill="x", padx=12)
                tk.Button(
                    cl_btn_cont, text="Clear All ✕",
                    bg=C["bg_card"], fg=C["danger"],
                    activebackground=C["bg_hover"], activeforeground=C["danger_hover"],
                    font=_font(8, "bold"), bd=0, cursor="hand2",
                    command=lambda: [
                        self.pending_filters.update({k: [] for k in self.pending_filters}),
                        refresh_tags()
                    ]
                ).pack(side="right")
                for k, vs in self.pending_filters.items():
                    for v in vs:
                        t = tk.Frame(tag_frame, bg=C["accent_muted"], padx=6, pady=2)
                        t.pack(side="left", padx=3, pady=3)
                        tk.Label(t, text=v, bg=C["accent_muted"], fg=C["accent"],
                                 font=_font(8, "bold")).pack(side="left")
                        tk.Button(
                            t, text="✕", bg=C["accent_muted"], fg=C["text_muted"],
                            activebackground=C["accent_muted"], activeforeground=C["danger"],
                            bd=0, font=_font(8), cursor="hand2",
                            command=lambda key=k, val=v: [
                                self.pending_filters[key].remove(val), refresh_tags()
                            ]
                        ).pack(side="left", padx=(4, 0))
                tag_frame.update_idletasks()
                tag_canvas.config(height=min(tag_frame.winfo_reqheight(), 64))
            else:
                tag_canvas.pack_forget()
                cl_btn_cont.pack_forget()
            tag_canvas.create_window((0, 0), window=tag_frame, anchor="nw")
            tag_canvas.config(scrollregion=tag_canvas.bbox("all"))

        self.create_popup_dropdown(c_area, "Gender", ["Male", "Female", "Other"],
                                   True, "gender", refresh_tags)
        self.create_popup_dropdown(c_area, "Year Level", ["1", "2", "3", "4", "5"],
                                   True, "year", refresh_tags)
        self.create_popup_dropdown(c_area, "Program", db_get_all_program_names(),
                                   True, "program", refresh_tags)
        self.create_popup_dropdown(c_area, "College", db_get_all_college_names(),
                                   True, "college", refresh_tags)
        refresh_tags()

    def check_filter_focus(self, event):
        if self.filter_win and self.filter_win.winfo_exists():
            x, y = event.x_root, event.y_root
            fx, fy = self.filter_win.winfo_rootx(), self.filter_win.winfo_rooty()
            fw, fh = self.filter_win.winfo_width(), self.filter_win.winfo_height()
            if not (fx <= x <= fx + fw and fy <= y <= fy + fh):
                self.filter_win.destroy()
                self.filter_win = None

    def on_tree_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            vals = list(self.tree.item(item, "values"))
            if vals[0] == "[ ]":
                vals[0] = "[X]"
                self.tree.item(item, values=vals, tags=("checked",))
            else:
                vals[0] = "[ ]"
                idx = self.tree.index(item)
                tag = "odd" if idx % 2 == 0 else "even"
                self.tree.item(item, values=vals, tags=(tag,))

    def delete_selected(self, section):
        selected_keys = [
            self.tree.item(i, "values")[1]
            for i in self.tree.get_children()
            if self.tree.item(i, "values")[0] == "[X]"
        ]
        if not selected_keys:
            messagebox.showwarning("Warning", "No items selected.")
            return

        if section == "Students":
            if not messagebox.askyesno("Confirm", f"Delete {len(selected_keys)} student(s)?"):
                return
            db_delete_students(selected_keys)

        elif section == "Programs":
            affected = sum(
                _exec_read_one("SELECT COUNT(*) AS cnt FROM students WHERE prog_code=?", (k,))["cnt"]
                for k in selected_keys
            )
            msg = f"Delete {len(selected_keys)} program(s)?"
            if affected:
                msg += f"\n\n⚠ {affected} enrolled student(s) will be set to 'Not Enrolled'."
            if not messagebox.askyesno("Confirm", msg):
                return
            db_delete_programs(selected_keys)

        elif section == "Colleges":
            affected_progs = sum(
                _exec_read_one("SELECT COUNT(*) AS cnt FROM programs WHERE college_code=?", (k,))["cnt"]
                for k in selected_keys
            )
            msg = f"Delete {len(selected_keys)} college(s)?"
            if affected_progs:
                msg += f"\n\n⚠ {affected_progs} program(s) will be unlinked (college → N/A)."
            if not messagebox.askyesno("Confirm", msg):
                return
            db_delete_colleges(selected_keys)

        self._last_mtime = self._get_db_mtime()
        self.switch_section(section)


if __name__ == "__main__":
    app = StudentDirectoryApp()
    app.mainloop()