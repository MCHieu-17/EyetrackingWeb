-- 005_current_viewport_only.sql
-- Bỏ lớp toạ độ `original-v1` sau khi trang học đã khoá zoom.
--
-- Trước đây layout và gaze được quy đổi về viewport lúc calibration để bù
-- zoom/resize. Hiện tại:
--   * zoom/fullscreen bị display guard phát hiện và tạm dừng ghi gaze;
--   * resize/move cửa sổ được frontend quy đổi ngay về viewport hiện tại.
-- Vì vậy `view_layouts` và `gaze_samples` chỉ cần một hệ toạ độ hiện tại.
--
-- Migration chuyển các layout cũ từ hệ calibration sang hệ viewport hiện tại
-- bằng `visible_rect`, rồi bỏ các cột chỉ phục vụ bù trừ zoom:
--   * view_layouts.coordinate_space
--   * view_layouts.visible_rect
--   * gaze_samples.original_viewport_x/y
--
-- `gaze_samples.viewport_x/y` đã là toạ độ viewport tại thời điểm ghi nên
-- không cần backfill sample. Giữ schema_generation = '13'.

DO $$
DECLARE
    layout_row RECORD;
    view_left DOUBLE PRECISION;
    view_top DOUBLE PRECISION;
    view_width DOUBLE PRECISION;
    view_height DOUBLE PRECISION;
    new_slide_rect JSONB;
    new_elements JSONB;
BEGIN
    FOR layout_row IN
        SELECT id, visible_rect, slide_rect, elements
          FROM view_layouts
         WHERE coordinate_space = 'original-v1'
    LOOP
        view_left := 0;
        view_top := 0;
        view_width := NULL;
        view_height := NULL;

        BEGIN
            IF jsonb_typeof(layout_row.visible_rect -> 'left') = 'number' THEN
                view_left := (layout_row.visible_rect ->> 'left')::double precision;
            END IF;
            IF jsonb_typeof(layout_row.visible_rect -> 'top') = 'number' THEN
                view_top := (layout_row.visible_rect ->> 'top')::double precision;
            END IF;
            IF jsonb_typeof(layout_row.visible_rect -> 'width') = 'number' THEN
                view_width := (layout_row.visible_rect ->> 'width')::double precision;
            END IF;
            IF jsonb_typeof(layout_row.visible_rect -> 'height') = 'number' THEN
                view_height := (layout_row.visible_rect ->> 'height')::double precision;
            END IF;
        EXCEPTION WHEN others THEN
            view_width := NULL;
            view_height := NULL;
        END;

        -- Layout không có visible_rect hợp lệ: giữ geometry cũ, chỉ đổi cờ.
        IF view_width IS NULL OR view_width <= 0
           OR view_height IS NULL OR view_height <= 0 THEN
            UPDATE view_layouts
               SET coordinate_space = 'current-v1',
                   visible_rect = '{}'::jsonb
             WHERE id = layout_row.id;
            CONTINUE;
        END IF;

        IF jsonb_typeof(layout_row.slide_rect -> 'left') = 'number'
           AND jsonb_typeof(layout_row.slide_rect -> 'top') = 'number'
           AND jsonb_typeof(layout_row.slide_rect -> 'width') = 'number'
           AND jsonb_typeof(layout_row.slide_rect -> 'height') = 'number' THEN
            new_slide_rect := jsonb_build_object(
                'left',
                    ((layout_row.slide_rect ->> 'left')::double precision - view_left)
                    / view_width,
                'top',
                    ((layout_row.slide_rect ->> 'top')::double precision - view_top)
                    / view_height,
                'width',
                    (layout_row.slide_rect ->> 'width')::double precision
                    / view_width,
                'height',
                    (layout_row.slide_rect ->> 'height')::double precision
                    / view_height
            );
        ELSE
            new_slide_rect := layout_row.slide_rect;
        END IF;

        SELECT COALESCE(
                   jsonb_agg(
                       CASE
                           WHEN jsonb_typeof(element -> 'xMin') = 'number'
                            AND jsonb_typeof(element -> 'yMin') = 'number'
                            AND jsonb_typeof(element -> 'xMax') = 'number'
                            AND jsonb_typeof(element -> 'yMax') = 'number'
                           THEN element || jsonb_build_object(
                               'xMin',
                                   ((element ->> 'xMin')::double precision - view_left)
                                   / view_width,
                               'yMin',
                                   ((element ->> 'yMin')::double precision - view_top)
                                   / view_height,
                               'xMax',
                                   ((element ->> 'xMax')::double precision - view_left)
                                   / view_width,
                               'yMax',
                                   ((element ->> 'yMax')::double precision - view_top)
                                   / view_height
                           )
                           ELSE element
                       END
                       ORDER BY ordinality
                   ),
                   '[]'::jsonb
               )
          INTO new_elements
          FROM jsonb_array_elements(
                   COALESCE(layout_row.elements, '[]'::jsonb)
               ) WITH ORDINALITY AS item(element, ordinality);

        UPDATE view_layouts
           SET slide_rect = new_slide_rect,
               elements = new_elements,
               coordinate_space = 'current-v1',
               visible_rect = '{}'::jsonb
         WHERE id = layout_row.id;
    END LOOP;
END $$;

ALTER TABLE view_layouts
    DROP CONSTRAINT IF EXISTS view_layouts_coordinate_space_check;

ALTER TABLE view_layouts
    DROP COLUMN IF EXISTS coordinate_space,
    DROP COLUMN IF EXISTS visible_rect;

ALTER TABLE gaze_samples
    DROP COLUMN IF EXISTS original_viewport_x,
    DROP COLUMN IF EXISTS original_viewport_y;
