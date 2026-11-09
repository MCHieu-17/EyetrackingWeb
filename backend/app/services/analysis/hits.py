"""Insert AOI hits cho từng scope (slide/ui)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aoi import AnalysisRun
from app.services.analysis.common import _filters, _no_label_id


async def _insert_slide_hits(
    db: AsyncSession, run: AnalysisRun, watermark_no: int | None
) -> int:
    where, params = _filters(run, watermark_no)
    mapped = f"""
        WITH mapped AS (
            SELECT
                gs.id,
                gs.event_time,
                (
                    gs.viewport_x
                    - COALESCE((als.image_transform->>'left')::float, 0)
                ) / NULLIF(COALESCE((als.image_transform->>'width')::float, 1), 0) AS x,
                (
                    gs.viewport_y
                    - COALESCE((als.image_transform->>'top')::float, 0)
                ) / NULLIF(COALESCE((als.image_transform->>'height')::float, 1), 0) AS y
            FROM gaze_samples gs
            JOIN gaze_batches gb ON gb.id = gs.batch_id
            LEFT JOIN aoi_layout_snapshots als ON als.id = gb.layout_snapshot_id
            WHERE {where}
        )
    """

    # Mỗi sample chỉ nhận đúng một leaf hit. Thứ tự ưu tiên: vùng tự vẽ >
    # TEXT > TABLE > IMAGE > hình vẽ > còn lại. Nhờ vậy text đè lên ảnh sẽ
    # được tính là TEXT thay vì cả hai.
    leaf_sql = mapped + """
        , ranked AS (
            SELECT
                m.id,
                m.event_time,
                ad.id AS definition_id,
                ROW_NUMBER() OVER (
                    PARTITION BY m.id, m.event_time
                    ORDER BY
                        CASE ad.kind
                            WHEN 'custom' THEN 1
                            WHEN 'text' THEN 2
                            WHEN 'table' THEN 3
                            WHEN 'image' THEN 4
                            WHEN 'drawing' THEN 5
                            ELSE 6
                        END,
                        (
                            (ad.geometry->>'xMax')::float
                            - (ad.geometry->>'xMin')::float
                        ) * (
                            (ad.geometry->>'yMax')::float
                            - (ad.geometry->>'yMin')::float
                        )
                ) AS rn
            FROM mapped m
            JOIN aoi_definitions ad ON ad.aoi_set_id = :aoi_set_id
            WHERE ad.is_container = false
              AND ad.is_active = true
              AND ad.code <> 'no_label'
              AND m.x BETWEEN (ad.geometry->>'xMin')::float
                          AND (ad.geometry->>'xMax')::float
              AND m.y BETWEEN (ad.geometry->>'yMin')::float
                          AND (ad.geometry->>'yMax')::float
        )
        INSERT INTO aoi_hits (run_id, sample_id, event_time, definition_id)
        SELECT :run_id, id, event_time, definition_id
        FROM ranked
        WHERE rn = 1
        ON CONFLICT DO NOTHING
    """
    leaf = await db.execute(text(leaf_sql), params)

    container_sql = mapped + """
        INSERT INTO aoi_hits (run_id, sample_id, event_time, definition_id)
        SELECT :run_id, m.id, m.event_time, ad.id
        FROM mapped m
        JOIN aoi_definitions ad ON ad.aoi_set_id = :aoi_set_id
        WHERE ad.is_container = true
          AND ad.is_active = true
          AND m.x BETWEEN (ad.geometry->>'xMin')::float
                      AND (ad.geometry->>'xMax')::float
          AND m.y BETWEEN (ad.geometry->>'yMin')::float
                      AND (ad.geometry->>'yMax')::float
        ON CONFLICT DO NOTHING
    """
    container = await db.execute(text(container_sql), params)

    no_label_id = await _no_label_id(db, run.aoi_set_id)
    no_label_count = 0
    if no_label_id is not None:
        no_label_sql = mapped + """
            INSERT INTO aoi_hits (run_id, sample_id, event_time, definition_id)
            SELECT :run_id, m.id, m.event_time, :no_label_id
            FROM mapped m
            WHERE m.x BETWEEN 0 AND 1
              AND m.y BETWEEN 0 AND 1
              AND NOT EXISTS (
                  SELECT 1
                  FROM aoi_hits ah
                  JOIN aoi_definitions ad ON ad.id = ah.definition_id
                  WHERE ah.run_id = :run_id
                    AND ah.sample_id = m.id
                    AND ah.event_time = m.event_time
                    AND ad.is_container = false
                    AND ad.is_active = true
                    AND ad.code <> 'no_label'
              )
            ON CONFLICT DO NOTHING
        """
        no_label = await db.execute(
            text(no_label_sql), {**params, "no_label_id": no_label_id}
        )
        no_label_count = no_label.rowcount or 0

    return (leaf.rowcount or 0) + (container.rowcount or 0) + no_label_count


async def _insert_ui_hits(
    db: AsyncSession, run: AnalysisRun, watermark_no: int | None
) -> int:
    where, params = _filters(run, watermark_no)

    component_leaf_sql = f"""
        INSERT INTO aoi_hits (run_id, sample_id, event_time, definition_id)
        SELECT :run_id, gs.id, gs.event_time, ad.id
        FROM gaze_samples gs
        JOIN gaze_batches gb ON gb.id = gs.batch_id
        JOIN aoi_layout_rects alr ON alr.snapshot_id = gb.layout_snapshot_id
        JOIN aoi_definitions ad
          ON ad.aoi_set_id = :aoi_set_id
         AND ad.code = alr.semantic_code
        WHERE {where}
          AND ad.is_container = false
          AND ad.is_active = true
          AND ad.code <> 'no_label'
          AND (ad.geometry->>'anchor') IS NULL
          AND gs.viewport_x BETWEEN alr.x_min AND alr.x_max
          AND gs.viewport_y BETWEEN alr.y_min AND alr.y_max
        ON CONFLICT DO NOTHING
    """
    component_leaf = await db.execute(text(component_leaf_sql), params)

    custom_leaf_sql = f"""
        INSERT INTO aoi_hits (run_id, sample_id, event_time, definition_id)
        SELECT :run_id, gs.id, gs.event_time, ad.id
        FROM gaze_samples gs
        JOIN gaze_batches gb ON gb.id = gs.batch_id
        JOIN aoi_definitions ad
          ON ad.aoi_set_id = :aoi_set_id
         AND ad.is_container = false
         AND ad.is_active = true
         AND ad.code <> 'no_label'
         AND (ad.geometry->>'anchor') IS NOT NULL
        JOIN aoi_layout_rects anchor
          ON anchor.snapshot_id = gb.layout_snapshot_id
         AND anchor.semantic_code = ad.geometry->>'anchor'
        WHERE {where}
          AND gs.viewport_x BETWEEN
              anchor.x_min
              + (ad.geometry->>'xMin')::float * (anchor.x_max - anchor.x_min)
              AND anchor.x_min
              + (ad.geometry->>'xMax')::float * (anchor.x_max - anchor.x_min)
          AND gs.viewport_y BETWEEN
              anchor.y_min
              + (ad.geometry->>'yMin')::float * (anchor.y_max - anchor.y_min)
              AND anchor.y_min
              + (ad.geometry->>'yMax')::float * (anchor.y_max - anchor.y_min)
        ON CONFLICT DO NOTHING
    """
    custom_leaf = await db.execute(text(custom_leaf_sql), params)

    component_container_sql = f"""
        INSERT INTO aoi_hits (run_id, sample_id, event_time, definition_id)
        SELECT :run_id, gs.id, gs.event_time, ad.id
        FROM gaze_samples gs
        JOIN gaze_batches gb ON gb.id = gs.batch_id
        JOIN aoi_layout_rects alr ON alr.snapshot_id = gb.layout_snapshot_id
        JOIN aoi_definitions ad
          ON ad.aoi_set_id = :aoi_set_id
         AND ad.code = alr.semantic_code
        WHERE {where}
          AND ad.is_container = true
          AND ad.is_active = true
          AND (ad.geometry->>'anchor') IS NULL
          AND gs.viewport_x BETWEEN alr.x_min AND alr.x_max
          AND gs.viewport_y BETWEEN alr.y_min AND alr.y_max
        ON CONFLICT DO NOTHING
    """
    component_container = await db.execute(text(component_container_sql), params)

    custom_container_sql = f"""
        INSERT INTO aoi_hits (run_id, sample_id, event_time, definition_id)
        SELECT :run_id, gs.id, gs.event_time, ad.id
        FROM gaze_samples gs
        JOIN gaze_batches gb ON gb.id = gs.batch_id
        JOIN aoi_definitions ad
          ON ad.aoi_set_id = :aoi_set_id
         AND ad.is_container = true
         AND ad.is_active = true
         AND (ad.geometry->>'anchor') IS NOT NULL
        JOIN aoi_layout_rects anchor
          ON anchor.snapshot_id = gb.layout_snapshot_id
         AND anchor.semantic_code = ad.geometry->>'anchor'
        WHERE {where}
          AND gs.viewport_x BETWEEN
              anchor.x_min
              + (ad.geometry->>'xMin')::float * (anchor.x_max - anchor.x_min)
              AND anchor.x_min
              + (ad.geometry->>'xMax')::float * (anchor.x_max - anchor.x_min)
          AND gs.viewport_y BETWEEN
              anchor.y_min
              + (ad.geometry->>'yMin')::float * (anchor.y_max - anchor.y_min)
              AND anchor.y_min
              + (ad.geometry->>'yMax')::float * (anchor.y_max - anchor.y_min)
        ON CONFLICT DO NOTHING
    """
    custom_container = await db.execute(text(custom_container_sql), params)

    no_label_id = await _no_label_id(db, run.aoi_set_id)
    no_label_count = 0
    if no_label_id is not None:
        no_label_sql = f"""
            INSERT INTO aoi_hits (run_id, sample_id, event_time, definition_id)
            SELECT :run_id, gs.id, gs.event_time, :no_label_id
            FROM gaze_samples gs
            JOIN gaze_batches gb ON gb.id = gs.batch_id
            WHERE {where}
              AND gs.viewport_x BETWEEN 0 AND 1
              AND gs.viewport_y BETWEEN 0 AND 1
              AND NOT EXISTS (
                  SELECT 1
                  FROM aoi_hits ah
                  JOIN aoi_definitions ad ON ad.id = ah.definition_id
                  WHERE ah.run_id = :run_id
                    AND ah.sample_id = gs.id
                    AND ah.event_time = gs.event_time
                    AND ad.is_container = false
                    AND ad.is_active = true
                    AND ad.code <> 'no_label'
              )
            ON CONFLICT DO NOTHING
        """
        no_label = await db.execute(
            text(no_label_sql), {**params, "no_label_id": no_label_id}
        )
        no_label_count = no_label.rowcount or 0

    return (
        (component_leaf.rowcount or 0)
        + (custom_leaf.rowcount or 0)
        + (component_container.rowcount or 0)
        + (custom_container.rowcount or 0)
        + no_label_count
    )
