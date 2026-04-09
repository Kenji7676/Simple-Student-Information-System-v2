import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import re

DB_FILE = "student_directory.db"

# ---------------------------------------------------------------------------
# Database layer
# ---------------------------------------------------------------------------

def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row          # access columns by name
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS colleges (
                college_code TEXT PRIMARY KEY,
                name         TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS programs (
                prog_code    TEXT PRIMARY KEY,
                name         TEXT NOT NULL,
                college_code TEXT NOT NULL,
                FOREIGN KEY (college_code) REFERENCES colleges (college_code)
                    ON UPDATE CASCADE ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS students (
                id        TEXT PRIMARY KEY,
                firstname TEXT NOT NULL,
                lastname  TEXT NOT NULL,
                prog_code TEXT,
                year      TEXT NOT NULL,
                gender    TEXT NOT NULL,
                FOREIGN KEY (prog_code) REFERENCES programs (prog_code)
                    ON UPDATE CASCADE ON DELETE SET NULL
            );
        """)

init_db()

# -- Colleges ----------------------------------------------------------------

def db_get_colleges(search=""):
    with get_conn() as conn:
        if search:
            q = f"%{search}%"
            return conn.execute(
                "SELECT college_code, name FROM colleges "
                "WHERE college_code LIKE ? OR name LIKE ? ORDER BY name",
                (q, q)
            ).fetchall()
        return conn.execute(
            "SELECT college_code, name FROM colleges ORDER BY name"
        ).fetchall()

def db_add_college(code, name):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO colleges (college_code, name) VALUES (?, ?)",
            (code, name)
        )

def db_delete_colleges(codes):
    with get_conn() as conn:
        conn.executemany(
            "DELETE FROM colleges WHERE college_code = ?",
            [(c,) for c in codes]
        )

def db_college_code_exists(code):
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM colleges WHERE college_code = ?", (code,)
        ).fetchone() is not None

def db_college_has_programs(code):
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM programs WHERE college_code = ?", (code,)
        ).fetchone() is not None

# -- Programs ----------------------------------------------------------------

def db_get_programs(search=""):
    with get_conn() as conn:
        if search:
            q = f"%{search}%"
            return conn.execute(
                "SELECT p.prog_code, p.name, COALESCE(c.name,'N/A') AS college_name "
                "FROM programs p LEFT JOIN colleges c USING (college_code) "
                "WHERE p.prog_code LIKE ? OR p.name LIKE ? OR c.name LIKE ? "
                "ORDER BY p.name",
                (q, q, q)
            ).fetchall()
        return conn.execute(
            "SELECT p.prog_code, p.name, COALESCE(c.name,'N/A') AS college_name "
            "FROM programs p LEFT JOIN colleges c USING (college_code) "
            "ORDER BY p.name"
        ).fetchall()

def db_get_all_program_names():
    with get_conn() as conn:
        rows = conn.execute("SELECT name FROM programs ORDER BY name").fetchall()
        return [r["name"] for r in rows]

def db_add_program(code, name, college_code):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO programs (prog_code, name, college_code) VALUES (?, ?, ?)",
            (code, name, college_code)
        )

def db_delete_programs(codes):
    with get_conn() as conn:
        conn.executemany(
            "DELETE FROM programs WHERE prog_code = ?",
            [(c,) for c in codes]
        )

def db_prog_code_exists(code):
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM programs WHERE prog_code = ?", (code,)
        ).fetchone() is not None

def db_prog_has_students(code):
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM students WHERE prog_code = ?", (code,)
        ).fetchone() is not None

def db_prog_code_from_name(name):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT prog_code FROM programs WHERE name = ?", (name,)
        ).fetchone()
        return row["prog_code"] if row else ""

# -- Students ----------------------------------------------------------------

def db_get_students(search="", filters=None):
    filters = filters or {}
    base = (
        "SELECT s.id, s.lastname || ', ' || s.firstname AS name, "
        "s.gender, s.year, "
        "COALESCE(p.name,'N/A') AS program, "
        "COALESCE(c.name,'N/A') AS college "
        "FROM students s "
        "LEFT JOIN programs p ON s.prog_code = p.prog_code "
        "LEFT JOIN colleges c ON p.college_code = c.college_code"
    )
    conditions, params = [], []

    if search:
        q = f"%{search}%"
        conditions.append(
            "(s.id LIKE ? OR s.firstname LIKE ? OR s.lastname LIKE ? "
            "OR s.gender LIKE ? OR s.year LIKE ? OR p.name LIKE ? OR c.name LIKE ?)"
        )
        params.extend([q, q, q, q, q, q, q])

    if filters.get("gender"):
        placeholders = ",".join("?" * len(filters["gender"]))
        conditions.append(f"s.gender IN ({placeholders})")
        params.extend(filters["gender"])

    if filters.get("year"):
        placeholders = ",".join("?" * len(filters["year"]))
        conditions.append(f"s.year IN ({placeholders})")
        params.extend(filters["year"])

    if filters.get("program"):
        placeholders = ",".join("?" * len(filters["program"]))
        conditions.append(f"p.name IN ({placeholders})")
        params.extend(filters["program"])

    if filters.get("college"):
        placeholders = ",".join("?" * len(filters["college"]))
        conditions.append(f"c.name IN ({placeholders})")
        params.extend(filters["college"])

    if conditions:
        base += " WHERE " + " AND ".join(conditions)
    base += " ORDER BY s.lastname, s.firstname"

    with get_conn() as conn:
        return conn.execute(base, params).fetchall()

def db_get_student_by_id(student_id):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM students WHERE id = ?", (student_id,)
        ).fetchone()

def db_add_student(sid, firstname, lastname, prog_code, year, gender):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO students (id, firstname, lastname, prog_code, year, gender) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (sid, firstname, lastname, prog_code, year, gender)
        )

def db_update_student(sid, firstname, lastname, prog_code, year, gender):
    with get_conn() as conn:
        conn.execute(
            "UPDATE students SET firstname=?, lastname=?, prog_code=?, year=?, gender=? "
            "WHERE id=?",
            (firstname, lastname, prog_code, year, gender, sid)
        )

def db_delete_students(ids):
    with get_conn() as conn:
        conn.executemany(
            "DELETE FROM students WHERE id = ?",
            [(i,) for i in ids]
        )

def db_student_id_exists(sid):
    with get_conn() as conn:
        return conn.execute(
            "SELECT 1 FROM students WHERE id = ?", (sid,)
        ).fetchone() is not None

def db_get_all_college_options():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT college_code, name FROM colleges ORDER BY name"
        ).fetchall()
        return [f"{r['college_code']} - {r['name']}" for r in rows]

def db_get_all_college_names():
    with get_conn() as conn:
        rows = conn.execute("SELECT name FROM colleges ORDER BY name").fetchall()
        return [r["name"] for r in rows]

# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

class StudentDirectoryApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Student Directory System")
        self.configure(bg="#f5f5dc")

        self.edit_mode = False
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.handle_empty_search)

        self.active_filters = {"gender": [], "year": [], "program": [], "college": []}
        self.filter_win = None
        self.add_popup_win = None
        self.edit_popup_win = None

        self.sidebar = tk.Frame(self, bg="#d2b48c", width=180)
        self.sidebar.pack(side="left", fill="y", padx=10, pady=10)
        self.active_section = tk.StringVar(value="Students")
        for section in ["Students", "Programs", "Colleges"]:
            tk.Radiobutton(
                self.sidebar, text=section, variable=self.active_section, value=section,
                indicatoron=0, width=15, padx=10, pady=10, bg="#d2b48c", fg="white",
                selectcolor="#8b4513", font=("Arial", 12),
                command=lambda s=section: self.reset_all_and_switch(s)
            ).pack(pady=5)

        self.content_frame = tk.Frame(self, bg="white")
        self.content_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.button_container = tk.Frame(self, bg="#f5f5dc")
        self.button_container.place(relx=0.98, rely=0.95, anchor="se")
        tk.Button(
            self.button_container, text="+", font=("Arial", 18, "bold"),
            bg="#8b4513", fg="white", command=self.add_entry_popup, bd=0, width=2
        ).pack(side="left", padx=5)
        self.edit_btn = tk.Button(
            self.button_container, text="📝", font=("Arial", 18),
            bg="#d2b48c", fg="white", command=self.toggle_edit_mode, bd=0, width=2
        )
        self.edit_btn.pack(side="left")

        self.bind_all("<Button-1>", self.check_filter_focus)
        self.center_window(1150, 600)
        self.switch_section("Students")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def handle_empty_search(self, *args):
        if self.search_var.get() == "":
            self.switch_section(self.active_section.get())

    def toggle_edit_mode(self):
        self.edit_mode = not self.edit_mode
        self.edit_btn.config(bg="#8b4513" if self.edit_mode else "#d2b48c")
        self.switch_section(self.active_section.get())

    def reset_all_and_switch(self, section):
        self.search_var.set("")
        self.active_filters = {"gender": [], "year": [], "program": [], "college": []}
        self.edit_mode = False
        self.edit_btn.config(bg="#d2b48c")
        self.switch_section(section)

    def center_window(self, width, height):
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def center_window_small(self, win, w, h):
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")

    def create_popup_dropdown(self, parent, label, options, is_filter=False,
                               filter_key=None, refresh_callback=None, default_value=""):
        frame = tk.Frame(parent, bg="white")
        frame.pack(fill="x", pady=2)
        tk.Label(frame, text=label, font=("Arial", 8, "bold"), bg="white", fg="#555").pack(anchor="w")
        var = tk.StringVar(value=default_value)
        ent = tk.Entry(frame, textvariable=var, font=("Arial", 10), bg="#f4f4f4", bd=0)
        ent.pack(fill="x", ipady=3)
        drop_outer = tk.Frame(frame, bg="white", highlightbackground="#d2b48c", highlightthickness=1)

        canvas = tk.Canvas(drop_outer, bg="white", height=100 if is_filter else 80, highlightthickness=0)
        scrollbar = tk.Scrollbar(drop_outer, orient="vertical", command=canvas.yview)
        drop_inner = tk.Frame(canvas, bg="white")
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
                drop_outer.pack(fill="x")
                for i, m in enumerate(matches):
                    bg_c = "#8b4513" if (i == 0 and query != "") else "white"
                    fg_c = "white"  if (i == 0 and query != "") else "black"
                    tk.Button(
                        drop_inner, text=m, anchor="w", bg=bg_c, fg=fg_c,
                        relief="flat", font=("Arial", 8),
                        command=lambda v=m: select_action(v)
                    ).pack(fill="x")
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

    # ------------------------------------------------------------------
    # Section routing
    # ------------------------------------------------------------------

    def switch_section(self, section):
        if section == "Students":  self.show_students()
        elif section == "Programs": self.show_programs()
        elif section == "Colleges": self.show_colleges()

    # ------------------------------------------------------------------
    # Table display
    # ------------------------------------------------------------------

    def display_table(self, columns, rows, section_type):
        for w in self.content_frame.winfo_children():
            w.destroy()

        header = tk.Frame(self.content_frame, bg="white")
        header.pack(fill="x", pady=10)
        tk.Label(header, text=section_type, font=("Arial", 16, "bold"),
                 bg="white", fg="#8b4513").pack(side="left", padx=10)

        ctrls = tk.Frame(header, bg="white")
        ctrls.pack(side="right", padx=10)

        if self.edit_mode:
            tk.Button(ctrls, text="Delete Selected", bg="#ff4d4d", fg="white",
                      command=lambda: self.delete_selected(section_type)).pack(side="left", padx=2)
            if section_type == "Students":
                tk.Button(ctrls, text="Edit Selected", bg="#4CAF50", fg="white",
                          command=self.edit_selected_student).pack(side="left", padx=2)
            tk.Button(ctrls, text="Cancel", bg="gray", fg="white",
                      command=self.toggle_edit_mode).pack(side="left", padx=2)
        else:
            s_ent = tk.Entry(ctrls, textvariable=self.search_var, font=("Arial", 10),
                             width=25, bg="#f4f4f4", bd=0)
            s_ent.pack(side="left", padx=5, ipady=3)
            s_ent.bind("<Return>", lambda e: self.switch_section(section_type))
            tk.Button(ctrls, text="Search", bg="#d2b48c", fg="white",
                      command=lambda: self.switch_section(section_type)).pack(side="left", padx=2)
            if section_type == "Students":
                f_btn = tk.Button(ctrls, text="Filter ▽", bg="#8b4513", fg="white",
                                  padx=12, command=lambda: self.show_filter_menu(f_btn))
                f_btn.pack(side="left", padx=2)

        display_cols = ["Select"] + columns if self.edit_mode else columns
        self.tree = ttk.Treeview(self.content_frame, columns=display_cols, show="headings")

        for col in self.tree["columns"]:
            self.tree.heading(col, text=col)
            if col == "Select":
                self.tree.column(col, width=50, minwidth=50, anchor="center", stretch=False)
            else:
                self.tree.column(col, width=100, minwidth=80, anchor="center", stretch=True)

        tree_scroll = ttk.Scrollbar(self.content_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        if rows:
            for r in rows:
                self.tree.insert("", "end", values=(["[ ]"] + list(r) if self.edit_mode else list(r)))
        elif self.search_var.get().strip():
            lbl_frame = tk.Frame(self.tree, bg="white")
            lbl_frame.place(relx=0.5, rely=0.4, anchor="center")
            tk.Label(lbl_frame, text="No search results found.",
                     font=("Arial", 12, "italic"), fg="gray", bg="white").pack()

        if self.edit_mode:
            self.tree.bind("<ButtonRelease-1>", self.on_tree_click)

    # ------------------------------------------------------------------
    # Section views
    # ------------------------------------------------------------------

    def show_students(self):
        rows = db_get_students(
            search=self.search_var.get(),
            filters=self.active_filters
        )
        self.display_table(["ID", "Name", "Gender", "Year", "Program", "College"], rows, "Students")

    def show_programs(self):
        rows = db_get_programs(search=self.search_var.get())
        self.display_table(["Code", "Program Name", "College"], rows, "Programs")

    def show_colleges(self):
        rows = db_get_colleges(search=self.search_var.get())
        self.display_table(["Code", "College Name"], rows, "Colleges")

    # ------------------------------------------------------------------
    # Add popup
    # ------------------------------------------------------------------

    def add_entry_popup(self):
        if self.add_popup_win and self.add_popup_win.winfo_exists():
            self.add_popup_win.lift()
            return
        self.add_popup_win = tk.Toplevel(self)
        current = self.active_section.get()
        self.add_popup_win.title(f"Add {current}")
        self.add_popup_win.configure(bg="white")
        self.add_popup_win.transient(self)
        self.add_popup_win.grab_set()
        self.center_window_small(self.add_popup_win, 400, 680)
        container = tk.Frame(self.add_popup_win, bg="white", padx=20, pady=20)
        container.pack(fill="both", expand=True)

        if current == "Students":
            tk.Label(container, text="ID Number", bg="white", font=("Arial", 8, "bold")).pack(anchor="w")
            id_ent = tk.Entry(container, bg="#f4f4f4", bd=0)
            id_ent.pack(fill="x", pady=(5, 0), ipady=3)
            err_msg = tk.Label(
                container,
                text="Invalid Input. ID Number must follow the\nformat YYYY-NNNN (e.g. 2024-0001)",
                font=("Arial", 7, "italic"), fg="red", bg="white", justify="right"
            )
            tk.Label(container, text="First Name", bg="white", font=("Arial", 8, "bold")).pack(anchor="w", pady=(10, 0))
            fn_ent = tk.Entry(container, bg="#f4f4f4", bd=0)
            fn_ent.pack(fill="x", pady=5, ipady=3)
            tk.Label(container, text="Last Name", bg="white", font=("Arial", 8, "bold")).pack(anchor="w")
            ln_ent = tk.Entry(container, bg="#f4f4f4", bd=0)
            ln_ent.pack(fill="x", pady=5, ipady=3)

            prog_names = db_get_all_program_names()
            prog_sel, _ = self.create_popup_dropdown(container, "Program", prog_names)
            year_sel, _ = self.create_popup_dropdown(container, "Year Level", ["1", "2", "3", "4", "5"])
            gen_sel,  _ = self.create_popup_dropdown(container, "Gender", ["Male", "Female", "Other"])

            def save():
                err_msg.pack_forget()
                raw_id = id_ent.get().strip()
                if not re.match(r"^\d{4}-\d{4}$", raw_id):
                    err_msg.pack(anchor="e")
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
                prog_code = db_prog_code_from_name(prog_name)
                if not prog_code:
                    messagebox.showerror("Error", "Invalid program selected.")
                    return
                db_add_student(raw_id, firstname, lastname, prog_code, year, gender)
                self.show_students()
                self.add_popup_win.destroy()

            tk.Button(container, text="SAVE", bg="#8b4513", fg="white",
                      font=("Arial", 10, "bold"), command=save).pack(pady=20)

        elif current == "Programs":
            tk.Label(container, text="Code", bg="white", font=("Arial", 8, "bold")).pack(anchor="w")
            c_ent = tk.Entry(container, bg="#f4f4f4", bd=0)
            c_ent.pack(fill="x", pady=5, ipady=3)
            tk.Label(container, text="Name", bg="white", font=("Arial", 8, "bold")).pack(anchor="w")
            n_ent = tk.Entry(container, bg="#f4f4f4", bd=0)
            n_ent.pack(fill="x", pady=5, ipady=3)
            coll_opts = db_get_all_college_options()
            coll_sel, _ = self.create_popup_dropdown(container, "College", coll_opts)

            def save_p():
                code = c_ent.get().strip().upper()
                name = n_ent.get().strip().title()
                coll_val = coll_sel["val"]
                college_code = coll_val.split(" - ")[0] if " - " in coll_val else ""
                if not all([code, name, college_code]):
                    messagebox.showwarning("!", "Fill all fields.")
                    return
                if db_prog_code_exists(code):
                    messagebox.showerror("Error", f"Program code '{code}' already exists.")
                    return
                db_add_program(code, name, college_code)
                self.show_programs()
                self.add_popup_win.destroy()

            tk.Button(container, text="SAVE", bg="#8b4513", fg="white",
                      font=("Arial", 10, "bold"), command=save_p).pack(pady=20)

        elif current == "Colleges":
            tk.Label(container, text="Code", bg="white", font=("Arial", 8, "bold")).pack(anchor="w")
            c_ent = tk.Entry(container, bg="#f4f4f4", bd=0)
            c_ent.pack(fill="x", pady=5, ipady=3)
            tk.Label(container, text="Name", bg="white", font=("Arial", 8, "bold")).pack(anchor="w")
            n_ent = tk.Entry(container, bg="#f4f4f4", bd=0)
            n_ent.pack(fill="x", pady=5, ipady=3)

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
                self.show_colleges()
                self.add_popup_win.destroy()

            tk.Button(container, text="SAVE", bg="#8b4513", fg="white",
                      font=("Arial", 10, "bold"), command=save_c).pack(pady=20)

    # ------------------------------------------------------------------
    # Edit student
    # ------------------------------------------------------------------

    def edit_selected_student(self):
        selected_items = [
            item for item in self.tree.get_children()
            if self.tree.item(item, "values")[0] == "[X]"
        ]
        if not selected_items:
            messagebox.showwarning("Warning", "Please select a student to edit.")
            return
        if len(selected_items) > 1:
            messagebox.showwarning("Warning", "Please select only one student to edit.")
            return

        # In edit mode: Select(0), ID(1), Name(2), Gender(3), Year(4), Program(5), College(6)
        student_id = self.tree.item(selected_items[0], "values")[1]
        student_data = db_get_student_by_id(student_id)
        if not student_data:
            messagebox.showerror("Error", "Student data not found.")
            return
        self.open_edit_student_popup(dict(student_data))

    def open_edit_student_popup(self, student_data):
        if self.edit_popup_win and self.edit_popup_win.winfo_exists():
            self.edit_popup_win.lift()
            return
        self.edit_popup_win = tk.Toplevel(self)
        self.edit_popup_win.title("Edit Student")
        self.edit_popup_win.configure(bg="white")
        self.edit_popup_win.transient(self)
        self.edit_popup_win.grab_set()
        self.center_window_small(self.edit_popup_win, 400, 680)

        container = tk.Frame(self.edit_popup_win, bg="white", padx=20, pady=20)
        container.pack(fill="both", expand=True)

        tk.Label(container, text="ID Number (Read Only)", bg="white", font=("Arial", 8, "bold")).pack(anchor="w")
        id_ent = tk.Entry(container, bg="#e0e0e0", bd=0)
        id_ent.pack(fill="x", pady=(5, 0), ipady=3)
        id_ent.insert(0, student_data["id"])
        id_ent.config(state="readonly")

        tk.Label(container, text="First Name", bg="white", font=("Arial", 8, "bold")).pack(anchor="w", pady=(10, 0))
        fn_ent = tk.Entry(container, bg="#f4f4f4", bd=0)
        fn_ent.pack(fill="x", pady=5, ipady=3)
        fn_ent.insert(0, student_data["firstname"])

        tk.Label(container, text="Last Name", bg="white", font=("Arial", 8, "bold")).pack(anchor="w")
        ln_ent = tk.Entry(container, bg="#f4f4f4", bd=0)
        ln_ent.pack(fill="x", pady=5, ipady=3)
        ln_ent.insert(0, student_data["lastname"])

        prog_names = db_get_all_program_names()
        with get_conn() as conn:
            prog_row = conn.execute(
                "SELECT name FROM programs WHERE prog_code = ?",
                (student_data["prog_code"],)
            ).fetchone()
        current_prog_name = prog_row["name"] if prog_row else ""

        prog_sel, _ = self.create_popup_dropdown(container, "Program", prog_names,
                                                  default_value=current_prog_name)
        year_sel, _ = self.create_popup_dropdown(container, "Year Level", ["1", "2", "3", "4", "5"],
                                                  default_value=student_data["year"])
        gen_sel, _  = self.create_popup_dropdown(container, "Gender", ["Male", "Female", "Other"],
                                                  default_value=student_data["gender"])

        btn_frame = tk.Frame(container, bg="white")
        btn_frame.pack(pady=20)

        def save_changes():
            new_firstname = fn_ent.get().strip().title()
            new_lastname  = ln_ent.get().strip().title()
            new_gender    = gen_sel["val"]
            new_year      = year_sel["val"]
            new_prog_name = prog_sel["val"]
            if not all([new_firstname, new_lastname, new_gender, new_year, new_prog_name]):
                messagebox.showwarning("Warning", "Please fill all fields.")
                return
            new_prog_code = db_prog_code_from_name(new_prog_name)
            if not new_prog_code:
                messagebox.showerror("Error", "Invalid program selected.")
                return
            db_update_student(student_data["id"], new_firstname, new_lastname,
                              new_prog_code, new_year, new_gender)
            self.show_students()
            self.edit_popup_win.destroy()
            messagebox.showinfo("Success", "Student information updated successfully!")

        tk.Button(btn_frame, text="SAVE CHANGES", bg="#8b4513", fg="white",
                  font=("Arial", 10, "bold"), command=save_changes).pack(side="left", padx=5)
        tk.Button(btn_frame, text="CANCEL", bg="gray", fg="white",
                  font=("Arial", 10, "bold"),
                  command=self.edit_popup_win.destroy).pack(side="left", padx=5)

    # ------------------------------------------------------------------
    # Filter menu
    # ------------------------------------------------------------------

    def show_filter_menu(self, widget):
        if self.filter_win and self.filter_win.winfo_exists():
            self.filter_win.destroy()
            self.filter_win = None
            return
        self.pending_filters = {k: list(v) for k, v in self.active_filters.items()}
        self.filter_win = tk.Toplevel(self)
        self.filter_win.withdraw()
        self.filter_win.overrideredirect(True)
        w_width, w_height = 330, 480
        app_x, app_y = self.winfo_rootx(), self.winfo_rooty()
        app_w, app_h = self.winfo_width(), self.winfo_height()
        start_x = widget.winfo_rootx() - 150
        start_y = widget.winfo_rooty() + 30
        if start_x + w_width > app_x + app_w: start_x = (app_x + app_w) - w_width - 10
        if start_x < app_x: start_x = app_x + 10
        if start_y + w_height > app_y + app_h: start_y = (app_y + app_h) - w_height - 10
        self.filter_win.geometry(f"{w_width}x{w_height}+{start_x}+{start_y}")
        self.filter_win.deiconify()

        container = tk.Frame(self.filter_win, bg="white", bd=2, relief="groove")
        container.pack(fill="both", expand=True)
        tk.Label(container, text="Filters", font=("Arial", 10, "bold"),
                 bg="#8b4513", fg="white", pady=5).pack(fill="x")

        def apply_filters():
            self.active_filters = self.pending_filters
            self.show_students()
            self.filter_win.destroy()
            self.filter_win = None

        tk.Button(container, text="APPLY FILTERS", bg="#8b4513", fg="white",
                  font=("Arial", 9, "bold"), command=apply_filters).pack(side="bottom", pady=15)

        scroll_cont = tk.Frame(container, bg="white")
        scroll_cont.pack(fill="both", expand=True)
        c_area = tk.Frame(scroll_cont, bg="white")
        c_area.pack(fill="x", padx=5)
        tag_canvas = tk.Canvas(scroll_cont, bg="#f9f9f9", height=0, highlightthickness=0)
        tag_frame = tk.Frame(tag_canvas, bg="#f9f9f9")
        cl_btn_cont = tk.Frame(scroll_cont, bg="white")

        def refresh_tags():
            for c in tag_frame.winfo_children():
                c.destroy()
            total_tags = sum(len(v) for v in self.pending_filters.values())
            for w in cl_btn_cont.winfo_children():
                w.destroy()
            if total_tags > 0:
                tag_canvas.pack(fill="x", padx=10, pady=5)
                cl_btn_cont.pack(fill="x", padx=10)
                tk.Button(
                    cl_btn_cont, text="Clear All ✕", bg="white", fg="#cc0000",
                    font=("Arial", 8, "bold"), bd=0,
                    command=lambda: [
                        self.pending_filters.update({k: [] for k in self.pending_filters}),
                        refresh_tags()
                    ]
                ).pack(side="right")
                for k, vs in self.pending_filters.items():
                    for v in vs:
                        t = tk.Frame(tag_frame, bg="#d2b48c", padx=4, pady=1)
                        t.pack(side="left", padx=2, pady=2)
                        tk.Label(t, text=v, bg="#d2b48c", fg="white", font=("Arial", 8)).pack(side="left")
                        tk.Button(
                            t, text="✕", bg="#d2b48c", fg="white", bd=0,
                            command=lambda key=k, val=v: [
                                self.pending_filters[key].remove(val), refresh_tags()
                            ]
                        ).pack(side="left")
                tag_frame.update_idletasks()
                tag_canvas.config(height=min(tag_frame.winfo_reqheight(), 60))
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

    # ------------------------------------------------------------------
    # Tree interaction
    # ------------------------------------------------------------------

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
            vals[0] = "[X]" if vals[0] == "[ ]" else "[ ]"
            self.tree.item(item, values=vals)

    def delete_selected(self, section):
        # Column index 1 holds the primary key in all three sections when in edit mode
        selected_keys = [
            self.tree.item(i, "values")[1]
            for i in self.tree.get_children()
            if self.tree.item(i, "values")[0] == "[X]"
        ]
        if not selected_keys:
            messagebox.showwarning("Warning", "No items selected.")
            return
        if not messagebox.askyesno("Confirm", f"Delete {len(selected_keys)} item(s)?"):
            return

        if section == "Students":
            db_delete_students(selected_keys)
        elif section == "Programs":
            blocked = [k for k in selected_keys if db_prog_has_students(k)]
            if blocked:
                messagebox.showerror(
                    "Cannot Delete",
                    f"{len(blocked)} program(s) still have enrolled students.\n"
                    "Remove or reassign those students first."
                )
                return
            db_delete_programs(selected_keys)
        elif section == "Colleges":
            blocked = [k for k in selected_keys if db_college_has_programs(k)]
            if blocked:
                messagebox.showerror(
                    "Cannot Delete",
                    f"{len(blocked)} college(s) still have programs assigned.\n"
                    "Remove those programs first."
                )
                return
            db_delete_colleges(selected_keys)

        self.switch_section(section)


if __name__ == "__main__":
    app = StudentDirectoryApp()
    app.mainloop()