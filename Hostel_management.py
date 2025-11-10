import os
import gradio as gr
import mysql.connector
import pandas as pd

# =============================================================================
# DB CONFIG
# =============================================================================
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "Sohi@2341")
DB_NAME = os.getenv("DB_NAME", "college_dorm")

def get_connection():
    return mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME
    )

# =============================================================================
# UTIL: discover table columns (schema-aware queries)
# =============================================================================
def get_cols(table):
    """Return a set of existing column names for the given table (UPPERCASE)."""
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute(
            "SELECT UPPER(COLUMN_NAME) FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s",
            (DB_NAME, table)
        )
        cols = {r[0] for r in cur.fetchall()}
        return cols
    except Exception:
        return set()
    finally:
        try: cur.close(); conn.close()
        except: pass

# =============================================================================
# HELPERS
# =============================================================================
def get_total_students():
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM Student")
        n = cur.fetchone()[0] or 0
        return int(n)
    except Exception:
        return 0
    finally:
        try: cur.close(); conn.close()
        except: pass

def get_pending_fees():
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM Student WHERE Fee_Status = 'Pending'")
        n = cur.fetchone()[0] or 0
        return int(n)
    except Exception:
        return 0
    finally:
        try: cur.close(); conn.close()
        except: pass

def get_total_rooms():
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM Room")
        n = cur.fetchone()[0] or 0
        return int(n)
    except Exception:
        return 0
    finally:
        try: cur.close(); conn.close()
        except: pass

def get_complaint_counts():
    try:
        conn = get_connection(); cur = conn.cursor()
        cur.execute("SELECT Status, COUNT(*) FROM Complaint GROUP BY Status")
        rows = cur.fetchall()
        counts = {"Open": 0, "In Progress": 0, "Resolved": 0}
        for status, cnt in rows:
            if status in counts:
                counts[status] = int(cnt)
        return counts
    except Exception:
        return {"Open": 0, "In Progress": 0, "Resolved": 0}
    finally:
        try: cur.close(); conn.close()
        except: pass

def get_students():
    try:
        conn = get_connection(); cur = conn.cursor(dictionary=True)
        cur.execute("SELECT Student_ID AS ID, Name, Department, Fee_Status FROM Student")
        rows = cur.fetchall()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception:
        return pd.DataFrame()
    finally:
        try: cur.close(); conn.close()
        except: pass

# =============================================================================
# VIEW TABLE (whitelisted)
# =============================================================================
ALLOWED_TABLES = {"Staff", "Room", "Student", "Fee_Payment", "Complaint"}

def view_table(table_name):
    try:
        if table_name not in ALLOWED_TABLES:
            return pd.DataFrame({"error": [f"Table '{table_name}' is not allowed."]})
        conn = get_connection(); cur = conn.cursor(dictionary=True)
        cur.execute(f"SELECT * FROM {table_name}")
        data = cur.fetchall()
        return pd.DataFrame(data) if data else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame({"error": [f"Error: {e}"]})
    finally:
        try: cur.close(); conn.close()
        except: pass

# =============================================================================
# DASHBOARD SUMMARY
# =============================================================================
def dashboard_summary():
    try:
        conn = get_connection(); cur = conn.cursor()

        # direct normal SQL
        cur.execute("SELECT COUNT(*) FROM Student")
        total_students = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM Room WHERE Current_Occupancy < Capacity")
        available_rooms = cur.fetchone()[0] or 0

        # USING DATABASE FUNCTION NOW ✅
        cur.execute("SELECT CalculatePendingFees()")
        pending_fees = cur.fetchone()[0] or 0

        cur.execute("SELECT COUNT(*) FROM Complaint WHERE Status='Open'")
        open_complaints = cur.fetchone()[0] or 0

        summary = {
            "Total Students": total_students,
            "Available Rooms": available_rooms,
            "Pending Fees Students (using DB Function)": pending_fees,
            "Open Complaints": open_complaints
        }
        return pd.DataFrame([summary])

    except Exception as e:
        return pd.DataFrame({"error": [str(e)]})
    finally:
        try: cur.close(); conn.close()
        except: pass

# =============================================================================
# STUDENT CRUD  (Add Student now REQUIRES Student_ID)
# =============================================================================
def add_student(student_id, name, gender, department, room_id):
    try:
        conn = get_connection(); cur = conn.cursor()
        sid = int(student_id)
        rid = int(room_id) if room_id is not None else None
        cur.execute(
            "INSERT INTO Student (Student_ID, Name, Gender, Department, Room_ID) VALUES (%s, %s, %s, %s, %s)",
            (sid, name, gender, department, rid)
        )
        conn.commit()
        return "✅ Student added successfully!"
    except Exception as e:
        return f"❌ Error: {e}"
    finally:
        try: cur.close(); conn.close()
        except: pass

def update_student(student_id, department, fee_status):
    try:
        conn = get_connection(); cur = conn.cursor()
        sid = int(student_id)
        cur.execute(
            "UPDATE Student SET Department=%s, Fee_Status=%s WHERE Student_ID=%s",
            (department, fee_status, sid)
        )
        conn.commit()
        return "✅ Student updated successfully!"
    except Exception as e:
        return f"❌ Error: {e}"
    finally:
        try: cur.close(); conn.close()
        except: pass

def delete_student(student_id):
    try:
        conn = get_connection(); cur = conn.cursor()
        sid = int(student_id)
        cur.execute("DELETE FROM Student WHERE Student_ID=%s", (sid,))
        conn.commit()
        return "🗑 Student deleted successfully!"
    except Exception as e:
        return f"❌ Error: {e}"
    finally:
        try: cur.close(); conn.close()
        except: pass

# =============================================================================
# FEES  (NO STAFF_ID NEEDED)
# =============================================================================
def add_payment(student_id, amount, payment_mode):
    try:
        conn = get_connection(); cur = conn.cursor()
        sid = int(student_id); amt = float(amount)
        cur.execute(
            "INSERT INTO Fee_Payment (Student_ID, Amount, Payment_Mode) VALUES (%s, %s, %s)",
            (sid, amt, payment_mode)
        )
        # Auto-mark student as Paid (optional; remove if you don't want this)
        cur.execute("UPDATE Student SET Fee_Status='Paid' WHERE Student_ID=%s", (sid,))
        conn.commit()
        return "✅ Payment recorded successfully!"
    except Exception as e:
        return f"❌ Error: {e}"
    finally:
        try: cur.close(); conn.close()
        except: pass

# =============================================================================
# COMPLAINTS (schema-aware) + also used in Student Mgmt
# =============================================================================
def view_complaints(student_id=None):
    try:
        cols = get_cols("Complaint")
        col_id   = "Complaint_ID" if "COMPLAINT_ID" in cols else "Id"
        col_sid  = "Student_ID"   if "STUDENT_ID"   in cols else "StudentId"
        col_text = "Text" if "TEXT" in cols else ("Complaint_Text" if "COMPLAINT_TEXT" in cols else None)
        col_stat = "Status" if "STATUS" in cols else "State"

        order_col = None
        for opt in ("Created_At","CreatedAt","Created","Timestamp","Updated_At","UpdatedAt"):
            if opt.upper() in cols:
                order_col = opt
                break

        if col_text is None:
            select_cols = f"{col_id} AS Complaint_ID, {col_sid} AS Student_ID, {col_stat} AS Status"
        else:
            select_cols = f"{col_id} AS Complaint_ID, {col_sid} AS Student_ID, {col_text} AS Text, {col_stat} AS Status"

        base_sql = f"SELECT {select_cols}"
        if order_col:
            base_sql += f", {order_col} AS Created_At"
        base_sql += " FROM Complaint"

        params = None
        if student_id not in (None, ""):
            base_sql += f" WHERE {col_sid}=%s"
            params = (int(student_id),)

        if order_col:
            base_sql += f" ORDER BY {order_col} DESC"
        else:
            base_sql += f" ORDER BY {col_id} DESC"

        conn = get_connection(); cur = conn.cursor(dictionary=True)
        cur.execute(base_sql, params) if params else cur.execute(base_sql)
        rows = cur.fetchall()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame({'error': [f"Error: {e}"]})
    finally:
        try: cur.close(); conn.close()
        except: pass

def raise_complaint(student_id, text):
    if student_id in (None, ""):
        return " Error: Please provide a Student ID.", view_complaints(None)
    try:
        sid = int(student_id)
        conn = get_connection(); cur = conn.cursor()
        try:
            cur.execute("CALL RaiseComplaint(%s, %s)", (sid, text))
        except Exception:
            cols = get_cols("Complaint")
            col_sid  = "Student_ID" if "STUDENT_ID" in cols else "StudentId"
            col_text = "Text" if "TEXT" in cols else ("Complaint_Text" if "COMPLAINT_TEXT" in cols else None)
            col_stat = "Status" if "STATUS" in cols else "State"
            if col_text is None:
                sql = f"INSERT INTO Complaint ({col_sid}, {col_stat}) VALUES (%s, %s)"
                cur.execute(sql, (sid, "Open"))
            else:
                sql = f"INSERT INTO Complaint ({col_sid}, {col_text}, {col_stat}) VALUES (%s, %s, %s)"
                cur.execute(sql, (sid, text, "Open"))
        conn.commit()
        status = "⚠ Complaint raised successfully!"
    except Exception as e:
        status = f"❌ Error: {e}"
    finally:
        try: cur.close(); conn.close()
        except: pass

    try:
        updated = view_complaints(student_id)
    except Exception:
        updated = pd.DataFrame()
    return status, updated

    def update_complaint_status(complaint_id, new_status):
        try:
            conn = get_connection(); cur = conn.cursor()
            cid = int(complaint_id)
            sql = "UPDATE Complaint SET Status=%s WHERE Complaint_ID=%s"
            cur.execute(sql, (new_status, cid))
            conn.commit()
            return "✅ Complaint status updated successfully!"
        except Exception as e:
            return f"❌ Error while updating: {e}"
        finally:
            try: cur.close(); conn.close()
            except: pass



# =============================================================================
# STUDENT DETAILS (schema-aware)
# =============================================================================
def view_student_details(student_id):
    if student_id in (None, ""):
        return pd.DataFrame({'error': ['Please provide a Student ID']})
    try:
        sid = int(student_id)

        # Student columns
        s_cols = get_cols("Student")
        s_id   = "Student_ID" if "STUDENT_ID" in s_cols else "Id"
        s_name = "Name" if "NAME" in s_cols else "Student_Name"
        s_gender = "Gender" if "GENDER" in s_cols else ("Sex" if "SEX" in s_cols else None)
        s_dept = "Department" if "DEPARTMENT" in s_cols else ("Dept" if "DEPT" in s_cols else None)
        s_room = "Room_ID" if "ROOM_ID" in s_cols else ("RoomId" if "ROOMID" in s_cols else None)
        s_fee  = "Fee_Status" if "FEE_STATUS" in s_cols else ("FeeStatus" if "FEESTATUS" in s_cols else None)

        # Room columns
        r_cols = get_cols("Room")
        r_pk   = "Room_ID" if "ROOM_ID" in r_cols else "Id"
        r_num  = "Room_Number" if "ROOM_NUMBER" in r_cols else ("Number" if "NUMBER" in r_cols else None)

        # Fee_Payment columns
        f_cols = get_cols("Fee_Payment")
        f_sid  = "Student_ID" if "STUDENT_ID" in f_cols else "StudentId"
        f_amt  = "Amount" if "AMOUNT" in f_cols else ("Fee_Amount" if "FEE_AMOUNT" in f_cols else None)

        # Complaint columns
        c_cols = get_cols("Complaint")
        c_sid  = "Student_ID" if "STUDENT_ID" in c_cols else "StudentId"
        c_id   = "Complaint_ID" if "COMPLAINT_ID" in c_cols else "Id"

        sel_parts = [
            f"s.{s_id} AS Student_ID",
            f"s.{s_name} AS Name"
        ]
        if s_gender: sel_parts.append(f"s.{s_gender} AS Gender")
        if s_dept:   sel_parts.append(f"s.{s_dept} AS Department")
        if s_room:   sel_parts.append(f"s.{s_room} AS Room_ID")
        if s_fee:    sel_parts.append(f"s.{s_fee} AS Fee_Status")
        if r_num:    sel_parts.append(f"r.{r_num} AS Room_Number")
        sel = ",\n            ".join(sel_parts)

        join_room = f"LEFT JOIN Room r ON s.{s_room} = r.{r_pk}" if s_room and r_pk else "LEFT JOIN Room r ON 1=0"
        fees_sum = f"COALESCE(SUM(f.{f_amt}), 0) AS Total_Fees_Paid" if f_sid and f_amt else "0 AS Total_Fees_Paid"
        comp_cnt = f"COUNT(DISTINCT c.{c_id}) AS Total_Complaints" if c_sid and c_id else "0 AS Total_Complaints"

        sql = f"""
        SELECT 
            {sel},
            {fees_sum},
            {comp_cnt}
        FROM Student s
        {join_room}
        LEFT JOIN Fee_Payment f ON s.{s_id} = f.{f_sid}
        LEFT JOIN Complaint c   ON s.{s_id} = c.{c_sid}
        WHERE s.{s_id} = %s
        GROUP BY {", ".join([p.split(" AS ")[0] for p in sel_parts])}
        """

        conn = get_connection(); cur = conn.cursor(dictionary=True)
        cur.execute(sql, (sid,))
        rows = cur.fetchall()
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame({'error': [str(e)]})
    finally:
        try: cur.close(); conn.close()
        except: pass

# =============================================================================
# AUTH (PLAINTEXT)
# =============================================================================
def verify_user(username, password):
    """Plaintext verification with trimming + right-padding strip."""
    try:
        u = (username or "").strip()
        p = (password or "").strip()
        if not u or not p:
            return None
        conn = get_connection(); cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT Username, Password, Role, Linked_ID FROM User_Login WHERE Username=%s",
            (u,)
        )
        row = cur.fetchone()
        if not row:
            return None
        stored = (row.get("Password") or "")
        stored_norm = stored.replace("\u00A0", " ").rstrip()
        input_norm  = p.replace("\u00A0", " ").rstrip()
        if input_norm != stored_norm:
            return None
        return {
            "Username": row.get("Username"),
            "Role": row.get("Role"),
            "Linked_ID": row.get("Linked_ID"),
        }
    except Exception as e:
        print(f"[verify_user] ERROR: {e}")
        return None
    finally:
        try: cur.close(); conn.close()
        except: pass

def login_user(username, password):
    user = verify_user(username, password)
    if not user:
        return " Invalid credentials (username not found or password mismatch).", None
    else:
        return f" Welcome {user['Username']}! Logged in as {user['Role']}.", user

# =============================================================================
# DASHBOARD DATA (optional text summary)
# =============================================================================
def dashboard_data():
    students = get_total_students()
    pending = get_pending_fees()
    rooms = get_total_rooms()
    complaints = get_complaint_counts()
    return (
        f"📚 Total Students: {students}\n💰 Pending Fees: {pending}\n🏠 Total Rooms: {rooms}",
        f"🧾 Complaints:\nOpen: {complaints['Open']}\nIn Progress: {complaints['In Progress']}\nResolved: {complaints['Resolved']}"
    )

# =============================================================================
# GRADIO APP
# =============================================================================
with gr.Blocks(title="🏫 Hostel Management System", theme=gr.themes.Soft()) as app:
    gr.Markdown("# 🔐 Hostel Management System — Login")

    # Login
    with gr.Group(visible=True) as login_group:
        with gr.Row():
            username_in = gr.Textbox(label="Username")
            password_in = gr.Textbox(label="Password", type="password")
        login_btn = gr.Button("Login")
        login_status = gr.Textbox(label="Status", interactive=False)

    # Main
    with gr.Group(visible=False) as main_group:
        gr.Markdown("## 🏫 College Dorm Management System")
        nav = gr.Radio(
            choices=["Dashboard", "View Tables", "Student Mgmt", "Fee Payment", "Complaints", "Student Details", "Logout"],
            value="Dashboard",
            label="📋 Navigation"
        )

        # Panels (Groups; we toggle visibility)
        with gr.Group(visible=True) as p_dashboard:
            gr.Markdown("### 📊 Overview of Hostel Data")
            dash_btn = gr.Button("Refresh Dashboard")
            dash_out = gr.Dataframe(label="Summary", interactive=False)
            dash_btn.click(dashboard_summary, outputs=dash_out)

        with gr.Group(visible=False) as p_tables:
            gr.Markdown("### 👀 View Tables")
            table_select = gr.Dropdown(sorted(ALLOWED_TABLES), label="Select Table")
            view_btn = gr.Button("View Data")
            output_table = gr.Dataframe(label="Table Data", interactive=False)
            view_btn.click(view_table, inputs=table_select, outputs=output_table)

        with gr.Group(visible=False) as p_students:
            gr.Markdown("### 👩‍🎓 Student Management")

            gr.Markdown("#### ➕ Add Student (requires Student ID)")
            add_sid  = gr.Number(label="Student ID", precision=0)
            add_name = gr.Textbox(label="Name")
            add_gender = gr.Dropdown(["Male", "Female", "Other"], label="Gender")
            add_dept = gr.Textbox(label="Department")
            add_room = gr.Number(label="Room ID")
            btn_add_stud = gr.Button("Add Student")
            out_stud = gr.Textbox(label="Status", interactive=False)
            btn_add_stud.click(add_student, inputs=[add_sid, add_name, add_gender, add_dept, add_room], outputs=out_stud)

            gr.Markdown("#### ✏ Update Student")
            stud_id_up = gr.Number(label="Student ID", precision=0)
            new_dept = gr.Textbox(label="New Department")
            new_fee = gr.Dropdown(["Paid", "Pending"], label="Fee Status")
            update_btn = gr.Button("Update Student")
            out_update = gr.Textbox(label="Status", interactive=False)
            update_btn.click(update_student, inputs=[stud_id_up, new_dept, new_fee], outputs=out_update)

            gr.Markdown("#### ❌ Delete Student")
            del_id = gr.Number(label="Student ID to Delete", precision=0)
            del_btn = gr.Button("Delete Student")
            del_out = gr.Textbox(label="Status", interactive=False)
            del_btn.click(delete_student, inputs=del_id, outputs=del_out)

            gr.Markdown("#### ⚠ Raise Complaint (quick access)")
            rc_sid = gr.Number(label="Student ID", precision=0)
            rc_text = gr.Textbox(label="Complaint Text", lines=3)
            rc_btn = gr.Button("Raise Complaint")
            rc_status = gr.Textbox(label="Status", interactive=False)
            rc_table = gr.Dataframe(label="Complaints for Student", interactive=False)
            rc_btn.click(raise_complaint, inputs=[rc_sid, rc_text], outputs=[rc_status, rc_table])

        with gr.Group(visible=False) as p_fees:
            gr.Markdown("### 💰 Fee Payment (no Staff ID)")
            fp_sid = gr.Number(label="Student ID", precision=0)
            fp_amount = gr.Number(label="Amount")
            fp_mode = gr.Dropdown(["Cash", "Card", "UPI", "Bank Transfer"], label="Payment Mode")
            fp_btn = gr.Button("Add Payment")
            fp_out = gr.Textbox(label="Status", interactive=False)
            fp_btn.click(add_payment, inputs=[fp_sid, fp_amount, fp_mode], outputs=fp_out)

        with gr.Group(visible=False) as p_complaints:
            gr.Markdown("### ⚠ Complaints")
            comp_stud = gr.Number(label="Student ID (optional, leave empty to view all)", precision=0)
            refresh_btn = gr.Button("Refresh Complaints")
            comp_table = gr.Dataframe(label="Existing Complaints", interactive=False)

            comp_text = gr.Textbox(label="Complaint Text", lines=3)
            comp_btn = gr.Button("Raise Complaint")
            comp_out = gr.Textbox(label="Status", interactive=False)

            refresh_btn.click(view_complaints, inputs=comp_stud, outputs=comp_table)
            comp_btn.click(raise_complaint, inputs=[comp_stud, comp_text], outputs=[comp_out, comp_table])

        with gr.Group(visible=False) as p_details:
            gr.Markdown("### 🔍 View Student Details")
            stud_det_id = gr.Number(label="Student ID", precision=0)
            det_btn = gr.Button("View Details")
            det_out = gr.Dataframe(interactive=False)
            det_btn.click(view_student_details, inputs=stud_det_id, outputs=det_out)

    # State for logged-in user
    user_state = gr.State(value=None)

    # Login handler
    def handle_login(u, p):
        u = (u or "").strip()
        p = (p or "").strip()
        msg, user = login_user(u, p)
        if user:
            return msg, gr.update(visible=False), gr.update(visible=True), user
        else:
            return msg, gr.update(visible=True), gr.update(visible=False), None

    login_btn.click(
        handle_login,
        [username_in, password_in],
        [login_status, login_group, main_group, user_state]
    )

    # Navigation handler
    def update_panels(page, user):
        # default hide
        show = {
            "dashboard": False, "tables": False, "students": False,
            "fees": False, "complaints": False, "details": False
        }

        if not user:
            return (
                gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=True), gr.update(visible=False)
            )

        role = user.get("Role", "Student")

        if page == "Dashboard":
            show["dashboard"] = True
        elif page == "View Tables":
            if role in ("Admin", "Staff"): show["tables"] = True
        elif page == "Student Mgmt":
            if role in ("Admin", "Staff"): show["students"] = True
        elif page == "Fee Payment":
            if role in ("Admin", "Staff"): show["fees"] = True
        elif page == "Complaints":
            show["complaints"] = True
        elif page == "Student Details":
            show["details"] = True
        elif page == "Logout":
            return (
                gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=False), gr.update(visible=False), gr.update(visible=False),
                gr.update(visible=True), gr.update(visible=False)
            )

        return (
            gr.update(visible=show["dashboard"]),
            gr.update(visible=show["tables"]),
            gr.update(visible=show["students"]),
            gr.update(visible=show["fees"]),
            gr.update(visible=show["complaints"]),
            gr.update(visible=show["details"]),
            gr.update(visible=False),  # login hidden
            gr.update(visible=True),   # main visible
        )

    nav.change(
        fn=update_panels,
        inputs=[nav, user_state],
        outputs=[p_dashboard, p_tables, p_students, p_fees, p_complaints, p_details, login_group, main_group]
    )

if __name__ == "__main__":
    app.launch()
