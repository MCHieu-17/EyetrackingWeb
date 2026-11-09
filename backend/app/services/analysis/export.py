"""Streaming JSONL export cho analysis run."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy import text

from app.db.session import SessionLocal
from app.models.aoi import AnalysisRun
from app.models.gaze import GazeBatch
from app.services import metrics
from app.services.analysis.manifest import _manifest


async def export_lines(run_id: str) -> AsyncIterator[str]:
    async with SessionLocal() as db:
        run = await db.get(AnalysisRun, run_id)
        if run is None:
            yield json.dumps({"type": "error", "message": "not_found"}) + "\n"
            return
        manifest = await _manifest(db, run)
        yield json.dumps(manifest, ensure_ascii=False, default=str) + "\n"

        watermark_no = None
        if run.batch_watermark:
            watermark = await db.get(GazeBatch, run.batch_watermark)
            watermark_no = watermark.batch_no if watermark else None

        last_time: datetime | None = None
        last_id = 0
        while True:
            params: dict = {
                "run_id": run.id,
                "session_id": run.session_id,
                "from_time": run.from_time,
                "to_time": run.to_time,
            }
            keyset = ""
            if last_time is not None:
                keyset = "AND (gs.event_time, gs.id) > (:last_time, :last_id)"
                params["last_time"] = last_time
                params["last_id"] = last_id
            watermark = ""
            if watermark_no is not None:
                watermark = "AND gb.batch_no <= :watermark_no"
                params["watermark_no"] = watermark_no
            presentation = ""
            if run.presentation_id:
                presentation = "AND gb.presentation_id = :presentation_id"
                params["presentation_id"] = run.presentation_id
            sql = f"""
                SELECT
                    gs.id,
                    gs.event_time,
                    gs.sequence,
                    gs.capture_monotonic_ns,
                    gs.viewport_x,
                    gs.viewport_y,
                    gs.status,
                    gs.quality_flags,
                    gb.id AS batch_id,
                    gb.presentation_id,
                    gb.layout_snapshot_id,
                    als.image_transform,
                    (
                        SELECT array_agg(ad.code ORDER BY ad.code)
                        FROM aoi_hits ah
                        JOIN aoi_definitions ad ON ad.id = ah.definition_id
                        WHERE ah.run_id = :run_id
                          AND ah.sample_id = gs.id
                          AND ah.event_time = gs.event_time
                    ) AS aoi_codes
                FROM gaze_samples gs
                JOIN gaze_batches gb ON gb.id = gs.batch_id
                LEFT JOIN aoi_layout_snapshots als ON als.id = gb.layout_snapshot_id
                WHERE gs.session_id = :session_id
                  AND gs.event_time >= :from_time
                  AND gs.event_time < :to_time
                  {watermark}
                  {presentation}
                  {keyset}
                ORDER BY gs.event_time, gs.id
                LIMIT 1000
            """
            rows = (await db.execute(text(sql), params)).mappings().all()
            if not rows:
                break
            for row in rows:
                last_time = row["event_time"]
                last_id = row["id"]
                mapped = metrics._map_viewport_to_slide(
                    float(row["viewport_x"]),
                    float(row["viewport_y"]),
                    row["image_transform"],
                ) if row["viewport_x"] is not None and row["viewport_y"] is not None else None
                yield json.dumps(
                    {
                        "type": "sample",
                        "id": row["id"],
                        "eventTime": row["event_time"].isoformat(),
                        "sequence": row["sequence"],
                        "captureMonotonicNs": row["capture_monotonic_ns"],
                        "viewportX": row["viewport_x"],
                        "viewportY": row["viewport_y"],
                        "slideX": mapped[0] if mapped else None,
                        "slideY": mapped[1] if mapped else None,
                        "status": row["status"],
                        "qualityFlags": row["quality_flags"],
                        "batchId": row["batch_id"],
                        "presentationId": row["presentation_id"],
                        "layoutSnapshotId": row["layout_snapshot_id"],
                        "aoiCodes": row["aoi_codes"] or [],
                    },
                    ensure_ascii=False,
                    default=str,
                ) + "\n"
        yield json.dumps({"type": "end", "runId": run.id}) + "\n"
