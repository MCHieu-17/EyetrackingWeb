"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FullPageSpinner } from "@/components/ui/spinner";
import { AoiPreview } from "@/components/teacher/aoi-preview";
import { useTeacherCourses } from "@/hooks/use-teacher";
import {
  createAoiSet,
  fetchAoiSets,
  publishAoiSet,
  rebuildAoiHits,
  updateAoiSet,
  type AoiDefinitionInput,
  type AoiRect,
} from "@/lib/api/aoi";
import { measureAoiRects } from "@/lib/aoi/measure";
import { cn } from "@/lib/utils";

const UI_SCHEMA_VERSION = "reader-v1";

type FormState = {
  code: string;
  name: string;
  parentCode: string;
};

const EMPTY_FORM: FormState = { code: "", name: "", parentCode: "" };

function selectorFor(code: string): string {
  return code ? `[data-aoi="${code}"]` : "";
}

export function AoiEditor({ courseId }: { courseId: string }) {
  const queryClient = useQueryClient();
  const { data: courses = [], isLoading: coursesLoading } = useTeacherCourses();
  const course = courses.find((item) => item.id === courseId);

  const previewRef = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<"reader" | "quiz">("reader");
  const [rects, setRects] = useState<AoiRect[]>([]);
  const [definitions, setDefinitions] = useState<AoiDefinitionInput[]>([]);
  const [editingCode, setEditingCode] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [message, setMessage] = useState<{ tone: "ok" | "err"; text: string } | null>(
    null,
  );

  const { data: sets = [], isLoading: setsLoading } = useQuery({
    queryKey: ["aoi-sets", "ui", UI_SCHEMA_VERSION],
    queryFn: () =>
      fetchAoiSets({ scope: "ui", uiSchemaVersion: UI_SCHEMA_VERSION }),
  });

  const draftSet = useMemo(
    () => sets.find((item) => item.state === "draft") ?? null,
    [sets],
  );
  const publishedSet = useMemo(
    () => sets.find((item) => item.state === "published") ?? null,
    [sets],
  );

  useEffect(() => {
    const source = draftSet ?? publishedSet;
    if (!source) return;
    setDefinitions(
      source.definitions.map((item) => ({
        code: item.code,
        name: item.name,
        parentId: item.parentId,
        geometry: item.geometry,
      })),
    );
  }, [draftSet, publishedSet]);

  const measure = () => {
    if (!previewRef.current) return;
    setRects(measureAoiRects(previewRef.current));
  };

  useEffect(() => {
    const timer = window.setTimeout(measure, 120);
    return () => window.clearTimeout(timer);
  }, [mode]);

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["aoi-sets"] });

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (draftSet) {
        return updateAoiSet(draftSet.id, definitions);
      }
      return createAoiSet({
        scope: "ui",
        uiSchemaVersion: UI_SCHEMA_VERSION,
        definitions,
      });
    },
    onSuccess: async () => {
      await invalidate();
      setMessage({ tone: "ok", text: "Đã lưu bản nháp AOI." });
    },
    onError: (error) => {
      setMessage({
        tone: "err",
        text: error instanceof Error ? error.message : "Không lưu được AOI.",
      });
    },
  });

  const publishMutation = useMutation({
    mutationFn: async () => {
      const saved = draftSet
        ? await updateAoiSet(draftSet.id, definitions)
        : await createAoiSet({
            scope: "ui",
            uiSchemaVersion: UI_SCHEMA_VERSION,
            definitions,
          });
      return publishAoiSet(saved.id);
    },
    onSuccess: async () => {
      await invalidate();
      setMessage({ tone: "ok", text: "Đã publish bộ AOI. Bộ cũ được giữ lịch sử." });
    },
    onError: (error) => {
      setMessage({
        tone: "err",
        text: error instanceof Error ? error.message : "Không publish được AOI.",
      });
    },
  });

  const rebuildMutation = useMutation({
    mutationFn: () => rebuildAoiHits({ courseId }),
    onSuccess: (result) => {
      setMessage({
        tone: "ok",
        text: `Đã tạo ${result.runs} analysis run (${result.completed} xong, ${result.failed} lỗi).`,
      });
    },
    onError: (error) => {
      setMessage({
        tone: "err",
        text: error instanceof Error ? error.message : "Không rebuild được AOI.",
      });
    },
  });

  const startEdit = (definition: AoiDefinitionInput) => {
    setEditingCode(definition.code);
    setForm({
      code: definition.code,
      name: definition.name,
      parentCode: definition.parentId ?? "",
    });
    setMessage(null);
  };

  const startFromRect = (rect: AoiRect) => {
    const existing = definitions.find((item) => item.code === rect.code);
    if (existing) {
      startEdit(existing);
      return;
    }
    setEditingCode(null);
    setForm({ code: rect.code, name: rect.code, parentCode: "" });
    setMessage(null);
  };

  const submit = () => {
    const code = form.code.trim();
    const name = form.name.trim();
    if (!code || !name) {
      setMessage({ tone: "err", text: "Mã và tên AOI là bắt buộc." });
      return;
    }
    if (!/^[a-z0-9][a-z0-9-]*$/.test(code)) {
      setMessage({
        tone: "err",
        text: "Mã AOI chỉ gồm chữ thường, số và dấu gạch ngang.",
      });
      return;
    }
    const rect = rects.find((item) => item.code === code);
    const geometry = rect
      ? {
          selector: selectorFor(code),
          xMin: rect.xMin,
          yMin: rect.yMin,
          xMax: rect.xMax,
          yMax: rect.yMax,
        }
      : { selector: selectorFor(code) };
    const next: AoiDefinitionInput = {
      code,
      name,
      parentId: form.parentCode || null,
      geometry,
    };
    setDefinitions((prev) => {
      const index = prev.findIndex((item) => item.code === code);
      if (index >= 0) {
        const copy = [...prev];
        copy[index] = next;
        return copy;
      }
      return [...prev, next];
    });
    setEditingCode(null);
    setForm(EMPTY_FORM);
    setMessage({ tone: "ok", text: "Đã cập nhật danh sách (chưa lưu)." });
  };

  const remove = (code: string) => {
    setDefinitions((prev) => prev.filter((item) => item.code !== code));
    if (editingCode === code) {
      setEditingCode(null);
      setForm(EMPTY_FORM);
    }
  };

  if (coursesLoading || setsLoading) {
    return <FullPageSpinner label="Đang tải AOI…" />;
  }
  if (!course) {
    return <Alert variant="destructive" title="Không tìm thấy khóa học" />;
  }

  const busy =
    saveMutation.isPending ||
    publishMutation.isPending ||
    rebuildMutation.isPending;

  return (
    <div className="space-y-6">
      <style>{`
        .aoi-editor-preview [data-aoi] {
          outline: 2px dashed rgba(225, 29, 72, 0.65);
          outline-offset: 2px;
          position: relative;
        }
        .aoi-editor-preview [data-aoi]::after {
          content: attr(data-aoi);
          position: absolute;
          top: 0;
          left: 0;
          z-index: 60;
          background: #e11d48;
          color: #fff;
          font-size: 9px;
          line-height: 1;
          padding: 2px 4px;
          border-radius: 0 0 4px 0;
          pointer-events: none;
          white-space: nowrap;
        }
      `}</style>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold tracking-[-0.03em] text-black">
            Vùng phân tích (AOI)
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-black/65">
            Bộ AOI giao diện được version hóa. Bản published bất biến; sửa tạo
            revision nháp mới. Toạ độ thật do trình duyệt đo khi sinh viên học.
          </p>
          <p className="mt-1 text-xs text-black/45">
            {draftSet
              ? `Đang sửa revision ${draftSet.revision} (draft)`
              : publishedSet
                ? `Đang xem revision ${publishedSet.revision} (published)`
                : "Chưa có bộ AOI giao diện"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-full border border-[#eeeee9] bg-white p-1">
            {(["reader", "quiz"] as const).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setMode(item)}
                className={cn(
                  "rounded-full px-3 py-1.5 text-xs font-semibold transition-colors",
                  mode === item ? "bg-black text-white" : "text-black/60 hover:text-black",
                )}
              >
                {item === "reader" ? "Bài giảng" : "Bài tập"}
              </button>
            ))}
          </div>
          <Button variant="outline" size="sm" onClick={measure}>
            <Icon name="ri-ruler-2-line" />
            Đo lại
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => saveMutation.mutate()}
            disabled={busy || definitions.length === 0}
          >
            Lưu nháp
          </Button>
          <Button
            size="sm"
            onClick={() => publishMutation.mutate()}
            disabled={busy || definitions.length === 0}
          >
            <Icon name="ri-upload-cloud-2-line" />
            Publish AOI
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => rebuildMutation.mutate()}
            disabled={busy}
          >
            <Icon name="ri-refresh-line" />
            Tính lại AOI hits
          </Button>
        </div>
      </div>

      {message && (
        <Alert variant={message.tone === "ok" ? "success" : "destructive"}>
          {message.text}
        </Alert>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0 space-y-3">
          <div className="overflow-x-auto rounded-[20px] border border-[#eeeee9] bg-white p-3 shadow-xs">
            <AoiPreview ref={previewRef} mode={mode} />
          </div>

          <section className="rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-black">
                Phần tử DOM phát hiện ({rects.length})
              </h3>
              <p className="text-[11px] text-black/45">Click để điền sẵn mã AOI</p>
            </div>
            <div className="mt-3 max-h-64 overflow-auto">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-white text-black/45">
                  <tr>
                    <th className="py-1.5 pr-3 font-medium">data-aoi</th>
                    <th className="py-1.5 pr-3 font-medium">xMin</th>
                    <th className="py-1.5 pr-3 font-medium">yMin</th>
                    <th className="py-1.5 pr-3 font-medium">xMax</th>
                    <th className="py-1.5 font-medium">yMax</th>
                  </tr>
                </thead>
                <tbody>
                  {rects.map((rect, index) => (
                    <tr
                      key={`${rect.code}-${index}`}
                      className="cursor-pointer border-t border-black/5 hover:bg-[#f7f7f4]"
                      onClick={() => startFromRect(rect)}
                    >
                      <td className="py-1.5 pr-3 font-mono text-[11px] text-[#36533a]">
                        {rect.code}
                      </td>
                      <td className="py-1.5 pr-3 tabular-nums">{rect.xMin.toFixed(3)}</td>
                      <td className="py-1.5 pr-3 tabular-nums">{rect.yMin.toFixed(3)}</td>
                      <td className="py-1.5 pr-3 tabular-nums">{rect.xMax.toFixed(3)}</td>
                      <td className="py-1.5 tabular-nums">{rect.yMax.toFixed(3)}</td>
                    </tr>
                  ))}
                  {rects.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-4 text-center text-black/45">
                        Chưa đo được phần tử nào. Bấm “Đo lại”.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <div className="space-y-4">
          <section className="rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs">
            <h3 className="text-sm font-semibold text-black">
              {editingCode ? "Sửa AOI" : "Thêm AOI"}
            </h3>
            <div className="mt-3 space-y-3">
              <div>
                <Label htmlFor="aoi-code">Mã AOI</Label>
                <Input
                  id="aoi-code"
                  value={form.code}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, code: event.target.value }))
                  }
                  placeholder="chat-user-message"
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="aoi-name">Tên hiển thị</Label>
                <Input
                  id="aoi-name"
                  value={form.name}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, name: event.target.value }))
                  }
                  placeholder="Tin nhắn người học"
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="aoi-parent">Mã AOI cha (tuỳ chọn)</Label>
                <Input
                  id="aoi-parent"
                  value={form.parentCode}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, parentCode: event.target.value }))
                  }
                  placeholder="chatbot"
                  className="mt-1"
                />
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={submit} disabled={busy}>
                  {editingCode ? "Cập nhật" : "Thêm vào danh sách"}
                </Button>
                {editingCode && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setEditingCode(null);
                      setForm(EMPTY_FORM);
                    }}
                  >
                    Huỷ
                  </Button>
                )}
              </div>
            </div>
          </section>

          <section className="rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs">
            <h3 className="text-sm font-semibold text-black">Danh sách AOI</h3>
            <div className="mt-3 space-y-2">
              {definitions.map((definition) => (
                <div
                  key={definition.code}
                  className="flex items-center justify-between gap-2 rounded-xl border border-black/5 px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate font-mono text-[11px] text-[#36533a]">
                      {definition.code}
                    </p>
                    <p className="truncate text-xs text-black/60">{definition.name}</p>
                  </div>
                  <div className="flex shrink-0 gap-1">
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`Sửa ${definition.code}`}
                      onClick={() => startEdit(definition)}
                    >
                      <Icon name="ri-edit-line" className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label={`Xoá ${definition.code}`}
                      onClick={() => remove(definition.code)}
                    >
                      <Icon name="ri-delete-bin-line" className="size-4" />
                    </Button>
                  </div>
                </div>
              ))}
              {definitions.length === 0 && (
                <p className="text-xs text-black/45">
                  Chưa có AOI. Đo layout rồi thêm từ bảng phần tử DOM.
                </p>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
