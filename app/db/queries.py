from app.db.models import AiReportLog
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

async def save_ai_report_log(db: AsyncSession, username: str, workers_count: int, text: str):
    """Zapisuje raport AI do dziennika w bazie danych."""
    new_log = AiReportLog(
        username=username,
        workers_count=workers_count,
        report_text=text,
        created_at=datetime.now()
    )
    db.add(new_log)
    await db.commit()
    await db.refresh(new_log)
    return new_log

async def fetch_ai_report_logs(db: AsyncSession, limit: int = 10):
    """Pobiera ostatnie logi z raportami AI (od najnowszych)."""
    stmt = select(AiReportLog).order_by(AiReportLog.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()