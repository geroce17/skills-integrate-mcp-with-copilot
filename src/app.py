"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import os
from pathlib import Path
import sqlite3
from contextlib import closing

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

DB_PATH = Path(__file__).parent / "activities.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with closing(get_connection()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activities (
                name TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                schedule TEXT NOT NULL,
                max_participants INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS enrollments (
                activity_name TEXT NOT NULL,
                email TEXT NOT NULL,
                PRIMARY KEY (activity_name, email),
                FOREIGN KEY (activity_name) REFERENCES activities(name) ON DELETE CASCADE
            )
            """
        )
        conn.commit()


def seed_db() -> None:
    with closing(get_connection()) as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM activities").fetchone()["c"]
        if count > 0:
            return

        for activity_name, details in DEFAULT_ACTIVITIES.items():
            conn.execute(
                """
                INSERT INTO activities(name, description, schedule, max_participants)
                VALUES (?, ?, ?, ?)
                """,
                (
                    activity_name,
                    details["description"],
                    details["schedule"],
                    details["max_participants"],
                ),
            )
            for email in details["participants"]:
                conn.execute(
                    """
                    INSERT INTO enrollments(activity_name, email)
                    VALUES (?, ?)
                    """,
                    (activity_name, email),
                )

        conn.commit()


def fetch_activity(activity_name: str) -> sqlite3.Row | None:
    with closing(get_connection()) as conn:
        return conn.execute(
            "SELECT name, description, schedule, max_participants FROM activities WHERE name = ?",
            (activity_name,),
        ).fetchone()


def fetch_participants(activity_name: str) -> list[str]:
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT email FROM enrollments WHERE activity_name = ? ORDER BY email",
            (activity_name,),
        ).fetchall()
        return [row["email"] for row in rows]


def get_activities_payload() -> dict:
    payload = {}
    with closing(get_connection()) as conn:
        activity_rows = conn.execute(
            "SELECT name, description, schedule, max_participants FROM activities ORDER BY name"
        ).fetchall()

        for row in activity_rows:
            participant_rows = conn.execute(
                "SELECT email FROM enrollments WHERE activity_name = ? ORDER BY email",
                (row["name"],),
            ).fetchall()
            participants = [participant["email"] for participant in participant_rows]

            payload[row["name"]] = {
                "description": row["description"],
                "schedule": row["schedule"],
                "max_participants": row["max_participants"],
                "participants": participants,
            }

    return payload

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# Default seed data for a first run.
DEFAULT_ACTIVITIES = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}

init_db()
seed_db()


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return get_activities_payload()


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    activity = fetch_activity(activity_name)
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")

    participants = fetch_participants(activity_name)
    if email in participants:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    if len(participants) >= activity["max_participants"]:
        raise HTTPException(
            status_code=400,
            detail="Activity is full"
        )

    with closing(get_connection()) as conn:
        conn.execute(
            "INSERT INTO enrollments(activity_name, email) VALUES (?, ?)",
            (activity_name, email),
        )
        conn.commit()

    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity"""
    activity = fetch_activity(activity_name)
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")

    participants = fetch_participants(activity_name)
    if email not in participants:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    with closing(get_connection()) as conn:
        conn.execute(
            "DELETE FROM enrollments WHERE activity_name = ? AND email = ?",
            (activity_name, email),
        )
        conn.commit()

    return {"message": f"Unregistered {email} from {activity_name}"}
