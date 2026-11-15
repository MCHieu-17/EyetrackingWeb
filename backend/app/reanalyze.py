"""Reanalyze toàn bộ content view sau khi đổi quy tắc nhãn AOI.

Chạy một lần sau migration generation 12:

    docker compose exec backend python -m app.reanalyze
"""

from __future__ import annotations

import asyncio

from app.db.session import SessionLocal
from app.services import analysis


async def main() -> None:
    async with SessionLocal() as db:
        lessons = await analysis.mark_ui_changed(db)
        await db.commit()
    print(f"[reanalyze] queued {lessons} lesson(s) for AOI label reanalysis")


if __name__ == "__main__":
    asyncio.run(main())
