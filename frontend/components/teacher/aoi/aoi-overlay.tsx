"use client";

import {
  type PointerEvent as ReactPointerEvent,
  type RefObject,
  useCallback,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import type { AoiDefinitionInput } from "@/lib/api/aoi";
import { colorFor } from "@/lib/aoi/colors";
import {
  type AoiRect,
  type Box,
  type Draft,
  findAnchor,
  measureElements,
  measureSlide,
  normalizeRect,
  numberValue,
  relativeRect,
  screenBox,
} from "@/lib/aoi/geometry";
import { cn } from "@/lib/utils";

export type { AoiRect } from "@/lib/aoi/geometry";

function AoiBox({
  box,
  code,
  name,
  selected,
  hovered,
  showLabel,
  dashed,
  dimmed,
  onSelect,
  onHover,
}: {
  box: Box;
  code: string;
  name: string;
  selected: boolean;
  hovered: boolean;
  showLabel: boolean;
  dashed?: boolean;
  dimmed?: boolean;
  onSelect: () => void;
  onHover: () => void;
}) {
  const color = dimmed ? "#9ca3af" : colorFor(code);
  return (
    <div
      className={cn("pointer-events-none absolute", dimmed && "opacity-55")}
      style={{
        left: box.left,
        top: box.top,
        width: box.width,
        height: box.height,
      }}
    >
      <div
        className={cn(
          "absolute inset-0 rounded-[4px] transition-[border-color,background-color]",
          dashed || dimmed ? "border-2 border-dashed" : "border-2",
          selected && "shadow-[0_0_0_2px_rgba(255,255,255,0.9),0_0_0_4px_rgba(0,0,0,0.18)]",
        )}
        style={{
          borderColor: color,
          backgroundColor: dimmed
            ? "rgba(156, 163, 175, 0.12)"
            : selected
              ? `${color}2e`
              : hovered
                ? `${color}24`
                : `${color}14`,
        }}
        onPointerEnter={onHover}
        onClick={onSelect}
      />
      {(showLabel || selected || hovered) && (
        <span
          className="absolute left-0 top-0 max-w-full truncate rounded-br-[4px] px-1.5 py-0.5 text-[10px] font-semibold leading-4 text-white"
          style={{ backgroundColor: color }}
        >
          {dimmed ? "Chưa đánh dấu" : name}
        </span>
      )}
    </div>
  );
}

export function AoiOverlay({
  containerRef,
  shellRef,
  slideDefinitions,
  uiDefinitions,
  tab,
  mode,
  selectedCode,
  hoveredCode,
  hiddenCodes,
  showOverlays,
  canManage,
  layoutKey,
  onSelect,
  onHover,
  onCreateSlide,
  onCreateUiComponent,
  onCreateUiCustom,
}: {
  containerRef: RefObject<HTMLDivElement | null>;
  shellRef: RefObject<HTMLDivElement | null>;
  slideDefinitions: AoiDefinitionInput[];
  uiDefinitions: AoiDefinitionInput[];
  tab: "slide" | "ui";
  mode: "edit" | "interact";
  selectedCode: string | null;
  hoveredCode: string | null;
  hiddenCodes: Set<string>;
  showOverlays: boolean;
  canManage: boolean;
  layoutKey: string;
  onSelect: (code: string | null) => void;
  onHover: (code: string | null) => void;
  onCreateSlide: (rect: AoiRect) => void;
  onCreateUiComponent: (code: string) => void;
  onCreateUiCustom: (anchor: string, rect: AoiRect) => void;
}) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const draftRef = useRef<Draft | null>(null);
  const [elements, setElements] = useState<Map<string, DOMRect[]>>(new Map());
  const [slideRect, setSlideRect] = useState<DOMRect | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);

  useLayoutEffect(() => {
    const shell = shellRef.current;
    const container = containerRef.current;
    if (!shell || !container) return;
    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        setElements(measureElements(shell, container));
        setSlideRect(measureSlide(shell, container));
      });
    };
    update();
    const resize = new ResizeObserver(update);
    resize.observe(shell);
    resize.observe(container);
    const mutation = new MutationObserver(update);
    mutation.observe(shell, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["class", "style", "data-aoi"],
    });
    window.addEventListener("resize", update);
    return () => {
      cancelAnimationFrame(frame);
      resize.disconnect();
      mutation.disconnect();
      window.removeEventListener("resize", update);
    };
  }, [containerRef, shellRef, layoutKey]);

  const localPoint = useCallback(
    (event: ReactPointerEvent<HTMLDivElement>) => {
      const container = containerRef.current;
      if (!container) return { x: 0, y: 0 };
      const rect = container.getBoundingClientRect();
      return {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
      };
    },
    [containerRef],
  );

  const slidePoint = useCallback(
    (x: number, y: number) => {
      if (!slideRect) return null;
      return {
        x: (x - slideRect.left) / slideRect.width,
        y: (y - slideRect.top) / slideRect.height,
      };
    },
    [slideRect],
  );

  const findSlideAoiAt = useCallback(
    (x: number, y: number): string | null => {
      const point = slidePoint(x, y);
      if (!point) return null;
      if (point.x < 0 || point.x > 1 || point.y < 0 || point.y > 1) {
        return null;
      }
      const find = (items: AoiDefinitionInput[]) => {
        const leaves = items
          .filter((item) => !item.isContainer)
          .map((item) => {
            const geometry = item.geometry;
            const xMin = numberValue(geometry, "xMin");
            const yMin = numberValue(geometry, "yMin");
            const xMax = numberValue(geometry, "xMax");
            const yMax = numberValue(geometry, "yMax");
            return {
              code: item.code,
              xMin,
              yMin,
              xMax,
              yMax,
              area: Math.max(0, xMax - xMin) * Math.max(0, yMax - yMin),
            };
          })
          .filter(
            (item) =>
              point.x >= item.xMin &&
              point.x <= item.xMax &&
              point.y >= item.yMin &&
              point.y <= item.yMax,
          )
          .sort((a, b) => a.area - b.area);
        return leaves[0]?.code ?? null;
      };
      // Vùng đang dùng được ưu tiên; vùng đã bỏ đánh dấu chỉ được chọn khi
      // không có vùng nào đang dùng tại điểm bấm.
      return (
        find(slideDefinitions.filter((item) => item.isActive !== false)) ??
        find(slideDefinitions.filter((item) => item.isActive === false))
      );
    },
    [slideDefinitions, slidePoint],
  );

  const findUiCodeAt = useCallback(
    (clientX: number, clientY: number): string | null => {
      const container = containerRef.current;
      if (!container) return null;
      const containerRect = container.getBoundingClientRect();
      const x = clientX - containerRect.left;
      const y = clientY - containerRect.top;
      let best: { code: string; area: number } | null = null;
      for (const [code, rects] of elements) {
        if (code === "reader-root") continue;
        for (const rect of rects) {
          if (
            x >= rect.left &&
            x <= rect.right &&
            y >= rect.top &&
            y <= rect.bottom
          ) {
            const area = rect.width * rect.height;
            if (!best || area < best.area) {
              best = { code, area };
            }
          }
        }
      }
      return best?.code ?? null;
    },
    [containerRef, elements],
  );

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (mode !== "edit") return;
    const point = localPoint(event);
    if (!canManage) {
      const code =
        tab === "slide"
          ? findSlideAoiAt(point.x, point.y)
          : findUiCodeAt(event.clientX, event.clientY);
      onSelect(code);
      return;
    }
    if (tab === "slide") {
      const start = slidePoint(point.x, point.y);
      if (!start || start.x < 0 || start.x > 1 || start.y < 0 || start.y > 1) {
        onSelect(null);
        return;
      }
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    const nextDraft = {
      startX: point.x,
      startY: point.y,
      currentX: point.x,
      currentY: point.y,
    };
    draftRef.current = nextDraft;
    setDraft(nextDraft);
  };

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (mode !== "edit") return;
    const point = localPoint(event);
    if (draftRef.current) {
      const nextDraft = {
        ...draftRef.current,
        currentX: point.x,
        currentY: point.y,
      };
      draftRef.current = nextDraft;
      setDraft(nextDraft);
      return;
    }
    const code =
      tab === "slide"
        ? findSlideAoiAt(point.x, point.y)
        : findUiCodeAt(event.clientX, event.clientY);
    onHover(code);
  };

  const handlePointerUp = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (mode !== "edit" || !draftRef.current) return;
    const point = localPoint(event);
    const start = draftRef.current;
    draftRef.current = null;
    setDraft(null);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }

    if (tab === "slide") {
      const startSlide = slidePoint(start.startX, start.startY);
      const endSlide = slidePoint(point.x, point.y);
      if (!startSlide || !endSlide) {
        onSelect(null);
        return;
      }
      const rect = normalizeRect(
        startSlide.x,
        startSlide.y,
        endSlide.x,
        endSlide.y,
      );
      const width = rect.xMax - rect.xMin;
      const height = rect.yMax - rect.yMin;
      if (width < 0.01 || height < 0.01) {
        onSelect(findSlideAoiAt(point.x, point.y));
        return;
      }
      onCreateSlide(rect);
      return;
    }

    const box = screenBox(start.startX, start.startY, point.x, point.y);
    if (box.width < 6 || box.height < 6) {
      const code = findUiCodeAt(event.clientX, event.clientY);
      if (code) onCreateUiComponent(code);
      else onSelect(null);
      return;
    }
    const anchor = findAnchor(box, elements);
    if (!anchor) return;
    onCreateUiCustom(anchor.code, relativeRect(box, anchor.rect));
  };

  const handlePointerCancel = () => {
    draftRef.current = null;
    setDraft(null);
  };

  if (mode !== "edit") return null;

  const slideRoot = slideDefinitions.find(
    (item) => item.isContainer && item.code.startsWith("slide_"),
  );
  const activeLeaves = slideDefinitions.filter(
    (item) => !item.isContainer && item.isActive !== false,
  );
  const inactiveLeaves = slideDefinitions.filter(
    (item) => !item.isContainer && item.isActive === false,
  );

  const renderSlideBoxes = () => {
    if (!slideRect) return null;
    const rect = slideRect;
    const renderLeaf = (item: AoiDefinitionInput, dimmed: boolean) => {
      if (hiddenCodes.has(item.code)) return null;
      const geometry = item.geometry;
      const box: Box = {
        left: rect.left + numberValue(geometry, "xMin") * rect.width,
        top: rect.top + numberValue(geometry, "yMin") * rect.height,
        width:
          (numberValue(geometry, "xMax") - numberValue(geometry, "xMin")) *
          rect.width,
        height:
          (numberValue(geometry, "yMax") - numberValue(geometry, "yMin")) *
          rect.height,
      };
      if (box.width <= 0 || box.height <= 0) return null;
      return (
        <AoiBox
          key={item.code}
          box={box}
          code={item.code}
          name={item.name}
          selected={selectedCode === item.code}
          hovered={hoveredCode === item.code}
          showLabel={
            dimmed ||
            (box.width > rect.width * 0.12 && box.height > rect.height * 0.08)
          }
          dimmed={dimmed}
          onSelect={() => onSelect(item.code)}
          onHover={() => onHover(item.code)}
        />
      );
    };
    return (
      <>
        {slideRoot && (
          <div
            className="pointer-events-none absolute rounded-[6px] border-2 border-dashed border-black/25"
            style={{
              left: rect.left,
              top: rect.top,
              width: rect.width,
              height: rect.height,
            }}
          >
            <span className="absolute left-0 top-0 rounded-br-[4px] bg-black/55 px-1.5 py-0.5 text-[10px] font-semibold leading-4 text-white">
              {slideRoot.name}
            </span>
          </div>
        )}
        {inactiveLeaves.map((item) => renderLeaf(item, true))}
        {activeLeaves.map((item) => renderLeaf(item, false))}
      </>
    );
  };

  const renderUiBoxes = () => {
    return (
      <>
        {uiDefinitions.map((item) => {
          if (hiddenCodes.has(item.code)) return null;
          const geometry = item.geometry;
          const anchorCode =
            typeof geometry.anchor === "string" ? geometry.anchor : null;
          if (anchorCode) {
            const anchor = elements.get(anchorCode)?.[0];
            if (!anchor) return null;
            const box: Box = {
              left: anchor.left + numberValue(geometry, "xMin") * anchor.width,
              top: anchor.top + numberValue(geometry, "yMin") * anchor.height,
              width:
                (numberValue(geometry, "xMax") - numberValue(geometry, "xMin")) *
                anchor.width,
              height:
                (numberValue(geometry, "yMax") - numberValue(geometry, "yMin")) *
                anchor.height,
            };
            if (box.width <= 0 || box.height <= 0) return null;
            return (
              <AoiBox
                key={item.code}
                box={box}
                code={item.code}
                name={item.name}
                selected={selectedCode === item.code}
                hovered={hoveredCode === item.code}
                showLabel={box.width > 80 && box.height > 28}
                onSelect={() => onSelect(item.code)}
                onHover={() => onHover(item.code)}
              />
            );
          }
          const rects = elements.get(item.code) ?? [];
          return rects.map((rect, index) => (
            <AoiBox
              key={`${item.code}-${index}`}
              box={{
                left: rect.left,
                top: rect.top,
                width: rect.width,
                height: rect.height,
              }}
              code={item.code}
              name={item.name}
              selected={selectedCode === item.code}
              hovered={hoveredCode === item.code}
              showLabel={rect.width > 80 && rect.height > 28}
              onSelect={() => onSelect(item.code)}
              onHover={() => onHover(item.code)}
            />
          ));
        })}
      </>
    );
  };

  const draftBox = (() => {
    if (!draft) return null;
    if (tab === "slide") {
      if (!slideRect) return null;
      const startSlide = slidePoint(draft.startX, draft.startY);
      const endSlide = slidePoint(draft.currentX, draft.currentY);
      if (!startSlide || !endSlide) return null;
      const rect = normalizeRect(
        startSlide.x,
        startSlide.y,
        endSlide.x,
        endSlide.y,
      );
      return {
        left: slideRect.left + rect.xMin * slideRect.width,
        top: slideRect.top + rect.yMin * slideRect.height,
        width: (rect.xMax - rect.xMin) * slideRect.width,
        height: (rect.yMax - rect.yMin) * slideRect.height,
      };
    }
    return screenBox(
      draft.startX,
      draft.startY,
      draft.currentX,
      draft.currentY,
    );
  })();

  return (
    <div
      ref={overlayRef}
      className="absolute inset-0 z-50 cursor-crosshair touch-none"
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerCancel}
      onPointerLeave={() => onHover(null)}
    >
      {showOverlays && tab === "slide" && renderSlideBoxes()}
      {showOverlays && tab === "ui" && renderUiBoxes()}
      {draftBox && (
        <div
          className="pointer-events-none absolute rounded-[4px] border-2 border-dashed border-[#36533a] bg-[#36533a]/10"
          style={{
            left: draftBox.left,
            top: draftBox.top,
            width: draftBox.width,
            height: draftBox.height,
          }}
        />
      )}
    </div>
  );
}
