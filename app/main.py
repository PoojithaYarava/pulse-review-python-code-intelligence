import json
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .analyzer import analyze
from .database import Base, engine, get_db
from .models import Review
from .schemas import HistoryItem, ReviewRequest, ReviewResponse

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Pulse Review", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


@app.get("/", include_in_schema=False)
def serve_dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/review", response_model=ReviewResponse)
def create_review(payload: ReviewRequest, db: Session = Depends(get_db)):
    result = analyze(payload.code)
    review = Review(
        code=payload.code,
        score=result["score"],
        complexity=result["complexity"]["estimate"],
        issues_json=json.dumps(result["issues"]),
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return {**result, "id": review.id, "created_at": review.created_at}


@app.get("/reviews", response_model=list[HistoryItem])
def list_reviews(limit: int = 20, db: Session = Depends(get_db)):
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    reviews = db.scalars(select(Review).order_by(Review.created_at.desc()).limit(limit)).all()
    return [
        {"id": item.id, "score": item.score, "complexity": item.complexity, "issue_count": len(json.loads(item.issues_json)), "created_at": item.created_at}
        for item in reviews
    ]


@app.get("/stats")
def stats(db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(Review.id))) or 0
    average = db.scalar(select(func.avg(Review.score))) or 0
    reviews = db.scalars(select(Review)).all()
    issues = [issue for review in reviews for issue in json.loads(review.issues_json)]
    return {
        "total_reviews": total,
        "average_score": round(average),
        "critical_issues": sum(issue["severity"] == "critical" for issue in issues),
        "complexity_warnings": sum(issue["category"] == "complexity" for issue in issues),
    }
