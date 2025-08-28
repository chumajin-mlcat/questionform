import os
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


APP_DIR = os.path.dirname(__file__)
DB_PATH = os.path.join(APP_DIR, "data.db")


def ensure_db(path: str = DB_PATH) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                votes INTEGER NOT NULL DEFAULT 0,
                hidden INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_votes ON questions(votes DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_questions_created ON questions(created_at DESC)")
        conn.commit()
    finally:
        conn.close()


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class Question(BaseModel):
    id: int
    text: str
    votes: int
    hidden: bool
    created_at: str


class CreateQuestion(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class VoteResponse(BaseModel):
    id: int
    votes: int


ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")  # 必要に応じてREADME参照


def require_admin(admin_token: Optional[str]) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="ADMIN_TOKEN が未設定です。")
    if not admin_token or admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="管理者トークンが不正です。")


app = FastAPI(title="QuestionForm", version="1.0.0")


@app.on_event("startup")
def _startup():
    ensure_db(DB_PATH)


# 静的ファイルとルート
static_dir = os.path.join(APP_DIR, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def root():
    return FileResponse(os.path.join(static_dir, "index.html"))


@app.get("/projector")
def projector():
    return FileResponse(os.path.join(static_dir, "projector.html"))


def row_to_question(row: sqlite3.Row) -> Question:
    return Question(
        id=row["id"],
        text=row["text"],
        votes=row["votes"],
        hidden=bool(row["hidden"]),
        created_at=row["created_at"],
    )


@app.get("/api/questions", response_model=List[Question])
def list_questions(
    include_hidden: bool = Query(False, description="非表示も含めるか"),
    order: str = Query("new", regex="^(new|top)$", description="並び順: new|top"),
    conn: sqlite3.Connection = Depends(get_conn),
):
    clauses = []
    params: list = []
    if not include_hidden:
        clauses.append("hidden = 0")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    order_by = "ORDER BY votes DESC, created_at ASC" if order == "top" else "ORDER BY datetime(created_at) DESC"
    rows = conn.execute(f"SELECT * FROM questions{where} {order_by}").fetchall()
    return [row_to_question(r) for r in rows]


@app.post("/api/questions", response_model=Question)
def create_question(payload: CreateQuestion, conn: sqlite3.Connection = Depends(get_conn)):
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="テキストが空です。")
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO questions (text, votes, hidden, created_at) VALUES (?, 0, 0, ?)",
        (text, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (cur.lastrowid,)).fetchone()
    return row_to_question(row)


@app.post("/api/questions/{qid}/vote", response_model=VoteResponse)
def vote(qid: int, conn: sqlite3.Connection = Depends(get_conn)):
    # 非表示の投稿は投票不可
    row = conn.execute("SELECT id, votes, hidden FROM questions WHERE id = ?", (qid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="質問が見つかりません。")
    if row["hidden"]:
        raise HTTPException(status_code=403, detail="非表示のため投票できません。")
    conn.execute("UPDATE questions SET votes = votes + 1 WHERE id = ?", (qid,))
    conn.commit()
    new_votes = conn.execute("SELECT votes FROM questions WHERE id = ?", (qid,)).fetchone()["votes"]
    return VoteResponse(id=qid, votes=new_votes)


@app.post("/api/questions/{qid}/hide", response_model=Question)
def hide_question(
    qid: int,
    conn: sqlite3.Connection = Depends(get_conn),
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    require_admin(x_admin_token)
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="質問が見つかりません。")
    conn.execute("UPDATE questions SET hidden = 1 WHERE id = ?", (qid,))
    conn.commit()
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
    return row_to_question(row)


@app.post("/api/questions/{qid}/unhide", response_model=Question)
def unhide_question(
    qid: int,
    conn: sqlite3.Connection = Depends(get_conn),
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    require_admin(x_admin_token)
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="質問が見つかりません。")
    conn.execute("UPDATE questions SET hidden = 0 WHERE id = ?", (qid,))
    conn.commit()
    row = conn.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
    return row_to_question(row)


@app.delete("/api/questions/{qid}", response_model=dict)
def delete_question(
    qid: int,
    conn: sqlite3.Connection = Depends(get_conn),
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
):
    require_admin(x_admin_token)
    cur = conn.execute("DELETE FROM questions WHERE id = ?", (qid,))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="質問が見つかりません。")
    return {"status": "ok", "deleted": qid}

