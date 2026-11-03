"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FullPageSpinner } from "@/components/ui/spinner";
import { AoiPreview } from "@/components/teacher/aoi-preview";
import { useTeacherCourses } from "@/hooks/use-teacher";
import {
  createAoiDefinition,
  deleteAoiDefinition,
  fetchAoiDefinitions,
  rebuildAoiHits,
  updateAoiDefinition,
  type AoiDefinition,
  type AoiRect,
} from "@/lib/api/aoi";
import { measureAoiRects } from "@/lib/aoi/measure";
import { cn } from "@/lib/utils";

const EMPTY_FORM = {
  code: "",
  name: "",
  description: "",
  parentId: "",
  selector: "",
};

type FormState = typeof EMPTY_FORM;

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
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [message, setMessage] = useState<{ tone: "ok" | "err"; text: string } | null>(
    null,
  );

  const { data: definitions = [], isLoading: definitionsLoading } = useQuery({
    queryKey: ["aoi-definitions"],
    queryFn: () => fetchAoiDefinitions(true),
  });

  const activeDefinitions = useMemo(
    () => definitions.filter((item) => item.isActive),
    [definitions],
  );

  const measure = () => {
    if (!previewRef.current) return;
    setRects(measureAoiRects(previewRef.current));
  };

  useEffect(() => {
    const timer = window.setTimeout(measure, 120);
    return () => window.clearTimeout(timer);
  }, [mode]);

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["aoi-definitions"] });

  const createMutation = useMutation({
    mutationFn: createAoiDefinition,
    onSuccess: async () => {
      await invalidate();
      setMessage({ tone: "ok", text: "Đã tạo AOI." });
      setForm(EMPTY_FORM);
      setEditingId(null);
    },
    onError: (error) => {
      setMessage({
        tone: "err",
        text: error instanceof Error ? error.message : "Không tạo được AOI.",
      });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, input }: { id: string; input: Parameters<typeof updateAoiDefinition>[1] }) =>
      updateAoiDefinition(id, input),
    onSuccess: async () => {
      await invalidate();
      setMessage({ tone: "ok", text: "Đã cập nhật AOI." });
      setForm(EMPTY_FORM);
      setEditingId(null);
    },
    onError: (error) => {
      setMessage({
        tone: "err",
        text: error instanceof Error ? error.message : "Không cập nhật được AOI.",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteAoiDefinition,
    onSuccess: async () => {
      await invalidate();
      setMessage({ tone: "ok", text: "Đã tắt AOI (soft delete)." });
      setForm(EMPTY_FORM);
      setEditingId(null);
    },
    onError: (error) => {
      setMessage({
        tone: "err",
        text: error instanceof Error ? error.message : "Không xoá được AOI.",
      });
    },
  });

  const rebuildMutation = useMutation({
    mutationFn: () => rebuildAoiHits({ courseId }),
    onSuccess: (result) => {
      setMessage({
        tone: "ok",
        text: `Đã tính lại AOI hits cho khóa học: ${result.inserted} dòng.`,
      });
    },
    onError: (error) => {
      setMessage({
        tone: "err",
        text: error instanceof Error ? error.message : "Không rebuild được AOI hits.",
      });
    },
  });

  const startEdit = (definition: AoiDefinition) => {
    setEditingId(definition.id);
    setForm({
      code: definition.code,
      name: definition.name,
      description: definition.description ?? "",
      parentId: definition.parentId ?? "",
      selector: definition.selector ?? selectorFor(definition.code),
    });
    setMessage(null);
  };

  const startFromRect = (rect: AoiRect) => {
    const existing = definitions.find((item) => item.code === rect.code);
    if (existing) {
      startEdit(existing);
      return;
    }
    setEditingId(null);
    setForm({
      code: rect.code,
      name: rect.code,
      description: "",
      parentId: "",
      selector: selectorFor(rect.code),
    });
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
        text: "Mã AOI chỉ gồm chữ thường, số và dấu gạch ngang (vd: chat-user-message).",
      });
      return;
    }
    const payload = {
      code,
      name,
      description: form.description.trim() || null,
      parentId: form.parentId || null,
      selector: form.selector.trim() || selectorFor(code),
      scope: "viewport" as const,
    };
    if (editingId) {
      updateMutation.mutate({
        id: editingId,
        input: {
          name: payload.name,
          description: payload.description,
          parentId: payload.parentId,
          selector: payload.selector,
        },
      });
    } else {
      createMutation.mutate(payload);
    }
  };

  const toggleActive = (definition: AoiDefinition) => {
    updateMutation.mutate({
      id: definition.id,
      input: { isActive: !definition.isActive },
    });
  };

  if (coursesLoading || definitionsLoading) {
    return <FullPageSpinner label="Đang tải AOI…" />;
  }
  if (!course) {
    return <Alert variant="destructive" title="Không tìm thấy khóa học" />;
  }

  const busy =
    createMutation.isPending ||
    updateMutation.isPending ||
    deleteMutation.isPending ||
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
            AOI áp dụng <strong>toàn hệ thống</strong> vì cấu trúc các khóa học giống nhau.
            Vùng được gắn với phần tử DOM qua <code className="rounded bg-black/5 px-1">data-aoi</code>;
            toạ độ thật do trình duyệt đo khi sinh viên học.
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
              <p className="text-[11px] text-black/45">
                Click để điền sẵn mã AOI
              </p>
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
              {editingId ? "Sửa AOI" : "Thêm AOI"}
            </h3>
            <div className="mt-3 space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="aoi-code">Mã (data-aoi)</Label>
                <Input
                  id="aoi-code"
                  value={form.code}
                  disabled={Boolean(editingId)}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      code: event.target.value,
                      selector: selectorFor(event.target.value),
                    }))
                  }
                  placeholder="chat-user-message"
                  className="font-mono text-xs"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="aoi-name">Tên hiển thị</Label>
                <Input
                  id="aoi-name"
                  value={form.name}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, name: event.target.value }))
                  }
                  placeholder="Tin nhắn người dùng"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="aoi-parent">AOI cha</Label>
                <select
                  id="aoi-parent"
                  value={form.parentId}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, parentId: event.target.value }))
                  }
                  className="flex h-10 w-full rounded-full border border-input bg-surface px-4 text-sm shadow-xs focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/30 focus-visible:outline-none"
                >
                  <option value="">— Không có —</option>
                  {activeDefinitions
                    .filter((item) => item.id !== editingId)
                    .map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.code} · {item.name}
                      </option>
                    ))}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="aoi-selector">Selector</Label>
                <Input
                  id="aoi-selector"
                  value={form.selector}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, selector: event.target.value }))
                  }
                  placeholder='[data-aoi="chat-user-message"]'
                  className="font-mono text-xs"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="aoi-description">Mô tả</Label>
                <Textarea
                  id="aoi-description"
                  value={form.description}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, description: event.target.value }))
                  }
                  rows={2}
                  placeholder="Vùng này dùng để phân tích gì?"
                />
              </div>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" onClick={submit} disabled={busy}>
                  <Icon name={editingId ? "ri-save-line" : "ri-add-line"} />
                  {editingId ? "Lưu thay đổi" : "Tạo AOI"}
                </Button>
                {editingId && (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setEditingId(null);
                        setForm(EMPTY_FORM);
                      }}
                    >
                      Huỷ
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                      onClick={() => deleteMutation.mutate(editingId)}
                      disabled={busy}
                    >
                      <Icon name="ri-delete-bin-line" />
                      Tắt AOI
                    </Button>
                  </>
                )}
              </div>
            </div>
          </section>

          <section className="rounded-[20px] border border-[#eeeee9] bg-white p-4 shadow-xs">
            <h3 className="text-sm font-semibold text-black">
              Danh sách AOI ({definitions.length})
            </h3>
            <div className="mt-3 space-y-2">
              {definitions.map((definition) => {
                const parent = definitions.find(
                  (item) => item.id === definition.parentId,
                );
                return (
                  <div
                    key={definition.id}
                    className={cn(
                      "rounded-xl border p-3 transition-colors",
                      definition.isActive
                        ? "border-[#eeeee9] bg-white"
                        : "border-dashed border-black/10 bg-[#fafaf7] opacity-70",
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <button
                        type="button"
                        onClick={() => startEdit(definition)}
                        className="min-w-0 flex-1 text-left"
                      >
                        <p className="truncate font-mono text-[11px] text-[#36533a]">
                          {definition.code}
                        </p>
                        <p className="mt-0.5 truncate text-sm font-medium text-black">
                          {definition.name}
                        </p>
                        <p className="mt-0.5 truncate text-[11px] text-black/45">
                          {parent ? `Thuộc ${parent.code}` : "Cấp gốc"}
                          {!definition.isActive ? " · Đã tắt" : ""}
                        </p>
                      </button>
                      <Button
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => toggleActive(definition)}
                        disabled={busy}
                        aria-label={
                          definition.isActive ? "Tắt AOI" : "Bật lại AOI"
                        }
                        title={definition.isActive ? "Tắt AOI" : "Bật lại AOI"}
                      >
                        <Icon
                          name={
                            definition.isActive
                              ? "ri-eye-off-line"
                              : "ri-eye-line"
                          }
                          className="size-4"
                        />
                      </Button>
                    </div>
                  </div>
                );
              })}
              {definitions.length === 0 && (
                <p className="rounded-xl border border-dashed border-black/10 p-4 text-center text-xs text-black/45">
                  Chưa có AOI. Chọn một phần tử ở bảng bên trái để tạo.
                </p>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
