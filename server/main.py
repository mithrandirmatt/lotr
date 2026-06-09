from fastapi import FastAPI, Depends, HTTPException, status
import os
import logging
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional
import bcrypt
import jwt
import sqlite3
import datetime

# Ensure the logs directory exists so that FileHandler can create the file.
log_dir = Path("server/server/logs")
log_dir.mkdir(parents=True, exist_ok=True)

# Configure a simple logger for login attempts
logger = logging.getLogger("api_login")
logger.setLevel(logging.INFO)
handler = logging.FileHandler(log_dir / "api_login.log")
formatter = logging.Formatter(
    "%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ"
)
handler.setFormatter(formatter)
logger.addHandler(handler)

# Database setup
conn = sqlite3.connect('lotr.db', check_same_thread=False)
cur = conn.cursor()

cur.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        unique_name TEXT UNIQUE NOT NULL,
        is_admin BOOLEAN DEFAULT 0,
        is_moderator BOOLEAN DEFAULT 0
    )
''')
conn.commit()

class UserLogin(BaseModel):
    email: str
    password: str

class UserRegister(BaseModel):
    email: str
    unique_name: str
    password: str
    confirm_password: str

SECRET_KEY = 'your-secret-key'
ALGORITHM = 'HS256'
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

def get_user(email: str):
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cur.fetchone()
    if user:
        return {
            "id": user[0],
            "email": user[1],
            "password": user[2],
            "unique_name": user[3],
            "is_admin": user[4],
            "is_moderator": user[5]
        }
    return None

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())

def create_access_token(data: dict, expires_delta: Optional[datetime.timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=15)
    to_encode.update({"exp": expire.timestamp()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@app.post("/api/v1/auth/login")
async def login(user: UserLogin):
    db_user = get_user(user.email)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    logger.info("Login attempt for %s", user.email)
    if not verify_password(user.password, db_user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    access_token = create_access_token(data={"sub": user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": db_user
    }

@app.post("/api/v1/auth/register")
async def register(user: UserRegister):
    if user.password != user.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )
    cur.execute("SELECT * FROM users WHERE email = ?", (user.email,))
    existing_email = cur.fetchone()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    cur.execute("SELECT * FROM users WHERE unique_name = ?", (user.unique_name,))
    existing_name = cur.fetchone()
    if existing_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unique name already taken"
        )
    hashed_password = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt()).decode()
    cur.execute("INSERT INTO users (email, password, unique_name) VALUES (?, ?, ?)",
                 (user.email, hashed_password, user.unique_name))
    conn.commit()
    return {
        "message": "Registration successful. Please log in."}


@app.get("/api/v1/auth/check-email")
async def check_email(email: str):
    cur.execute("SELECT 1 FROM users WHERE email = ?", (email,))
    exists = cur.fetchone() is not None
    return {"exists": exists}

@app.get("/api/v1/auth/check-unique-name")
async def check_unique_name(unique_name: str):
    cur.execute("SELECT 1 FROM users WHERE unique_name = ?", (unique_name,))
    exists = cur.fetchone() is not None
    return {"exists": exists}

# ---------------------------------------------------------------------------
# Simple AI suggestion endpoint (placeholder)
# ---------------------------------------------------------------------------
@app.post("/api/v1/ai/suggest")
async def ai_suggest(body: dict):
    """Return a canned suggestion for the given text.

    The real implementation would forward *body['text']* to a local LLM
    (e.g., Ollama, OpenAI‑compatible server) and return the generated text.
    For now we just echo back a short phrase so the extension can be tested.
    """
    prompt = body.get("text", "")
    # Very naive “suggestion” – in real life replace with LLM call
    suggestion = f"[Suggested continuation of: {prompt[:30]}…]"
    return {"suggestion": suggestion}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
