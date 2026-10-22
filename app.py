
import os
from functools import wraps
from urllib.parse import urlencode

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash
from database import create_database, get_db_connection

app = Flask(__name__)

secret_key = os.environ.get("SECRET_KEY")
if not secret_key:
    raise RuntimeError(
        "SECRET_KEY is missing. Set it in your environment before starting Flask."
    )

app.config["SECRET_KEY"] = secret_key
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("COOKIE_SECURE", "0") == "1"
)

# Enable CSRF protection for POST requests
csrf = CSRFProtect(app)

create_database()



def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped_view


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped_view(*args, **kwargs):
        if session.get("role") != "admin":
            flash(
                "You do not have permission to access this page.",
                "error"
            )
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)
    return wrapped_view


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        connection = get_db_connection()
        try:
            user = connection.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,)
            ).fetchone()
        finally:
            connection.close()

        valid_password = (
            user is not None
            and check_password_hash(user["password_hash"], password)
        )

        
        if valid_password:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "error")


    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    connection = get_db_connection()
    try:
        total_tickets = connection.execute(
            "SELECT COUNT(*) FROM tickets"
        ).fetchone()[0]

        open_tickets = connection.execute(
            "SELECT COUNT(*) FROM tickets WHERE status = ?",
            ("Open",)
        ).fetchone()[0]

        in_progress_tickets = connection.execute(
            "SELECT COUNT(*) FROM tickets WHERE status = ?",
            ("In Progress",)
        ).fetchone()[0]

        resolved_tickets = connection.execute(
            "SELECT COUNT(*) FROM tickets WHERE status = ?",
            ("Resolved",)
        ).fetchone()[0]

        closed_tickets = connection.execute(
            "SELECT COUNT(*) FROM tickets WHERE status = ?",
            ("Closed",)
        ).fetchone()[0]

        low_tickets = connection.execute(
            "SELECT COUNT(*) FROM tickets WHERE priority = ?",
            ("Low",)
        ).fetchone()[0]

        medium_tickets = connection.execute(
            "SELECT COUNT(*) FROM tickets WHERE priority = ?",
            ("Medium",)
        ).fetchone()[0]

        high_tickets = connection.execute(
            "SELECT COUNT(*) FROM tickets WHERE priority = ?",
            ("High",)
        ).fetchone()[0]

        critical_tickets = connection.execute(
            "SELECT COUNT(*) FROM tickets WHERE priority = ?",
            ("Critical",)
        ).fetchone()[0]
    finally:
        connection.close()

    resolved_rate = 0
    if total_tickets > 0:
        resolved_rate = round(
            (resolved_tickets / total_tickets) * 100
        )

    return render_template(
        "dashboard.html",
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        in_progress_tickets=in_progress_tickets,
        resolved_tickets=resolved_tickets,
        closed_tickets=closed_tickets,
        low_tickets=low_tickets,
        medium_tickets=medium_tickets,
        high_tickets=high_tickets,
        critical_tickets=critical_tickets,
        resolved_rate=resolved_rate
    )


@app.route("/create-ticket", methods=["GET", "POST"])
@login_required
def create_ticket():
    if request.method == "POST":
        employee_name = request.form.get("employee_name", "").strip()
        email = request.form.get("email", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        priority = request.form.get("priority", "").strip()
        assigned_to = request.form.get("assigned_to", "").strip()

        if not all([
            employee_name, email, title,
            description, priority, assigned_to
        ]):
            flash("Please complete all required fields.", "error")
            return render_template("create_ticket.html"), 400

        if priority not in {"Low", "Medium", "High", "Critical"}:
            flash("Invalid priority.", "error")
            return render_template("create_ticket.html"), 400

        connection = get_db_connection()
        try:
            connection.execute("""
                INSERT INTO tickets (
                    employee_name, email, title, description,
                    priority, assigned_to
                )
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                employee_name, email, title, description,
                priority, assigned_to
            ))
            connection.commit()
        finally:
            connection.close()

        return redirect(url_for("tickets"))

    return render_template("create_ticket.html")


@app.route("/tickets")
@login_required
def tickets():
    status = request.args.get("status", "")
    priority = request.args.get("priority", "")
    assigned_to = request.args.get("assigned_to", "")
    search = request.args.get("search", "")

    connection = get_db_connection()
    try:
        query = "SELECT * FROM tickets WHERE 1=1"
        parameters = []

        if search:
            query += """
                AND (
                    employee_name LIKE ?
                    OR title LIKE ?
                    OR description LIKE ?
                )
            """
            search_value = f"%{search}%"
            parameters.extend([search_value] * 3)

        if status:
            query += " AND status = ?"
            parameters.append(status)

        if priority:
            query += " AND priority = ?"
            parameters.append(priority)

        if assigned_to:
            query += " AND assigned_to = ?"
            parameters.append(assigned_to)

        query += " ORDER BY id DESC"

        ticket_rows = connection.execute(
            query, parameters
        ).fetchall()
    finally:
        connection.close()

    return render_template("tickets.html", tickets=ticket_rows)


@app.route("/ticket/<int:ticket_id>")
@login_required
def ticket_details(ticket_id):
    connection = get_db_connection()
    try:
        ticket = connection.execute(
            "SELECT * FROM tickets WHERE id = ?",
            (ticket_id,)
        ).fetchone()
    finally:
        connection.close()

    if ticket is None:
        return "Ticket not found", 404

    return render_template("ticket_details.html", ticket=ticket)


@app.route("/update-status", methods=["POST"])
@login_required
def update_status():
    ticket_id = request.form.get("ticket_id", type=int)
    status = request.form.get("status", "")

    allowed_statuses = {"Open", "In Progress", "Resolved", "Closed"}
    if not ticket_id or status not in allowed_statuses:
        return "Invalid ticket ID or status", 400

    search = request.form.get("search", "")
    priority = request.form.get("priority", "")
    current_status = request.form.get("current_status", "")

    connection = get_db_connection()
    try:
        connection.execute(
            "UPDATE tickets SET status = ? WHERE id = ?",
            (status, ticket_id)
        )
        connection.commit()
    finally:
        connection.close()

    return redirect(url_for("tickets") + "?" + urlencode({
        "search": search,
        "priority": priority,
        "status": current_status
    }))


@app.route("/update-assignment", methods=["POST"])
@login_required
def update_assignment():
    ticket_id = request.form.get("ticket_id", type=int)
    assigned_to = request.form.get("assigned_to", "").strip()

    if not ticket_id or not assigned_to:
        return "Invalid ticket ID or assignment", 400

    search = request.form.get("search", "")
    priority = request.form.get("priority", "")
    status = request.form.get("status", "")

    connection = get_db_connection()
    try:
        connection.execute(
            "UPDATE tickets SET assigned_to = ? WHERE id = ?",
            (assigned_to, ticket_id)
        )
        connection.commit()
    finally:
        connection.close()

    return redirect(url_for("tickets") + "?" + urlencode({
        "search": search,
        "priority": priority,
        "status": status
    }))


if __name__ == "__main__":
    app.run(debug=True)
