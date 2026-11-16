import type {
  AoiDefinition,
  AoiDefinitionInput,
  AoiCollection,
} from "@/lib/api/aoi";

export function firstAoiCollection(
  collections: AoiCollection[] | undefined,
): AoiCollection | null {
  return collections?.[0] ?? null;
}

/** Collection rỗng vẫn là object truthy — chỉ coi là có dữ liệu khi có AOI thật. */
export function hasStoredAois(
  collection: AoiCollection | null | undefined,
): boolean {
  return Boolean(
    collection?.definitions.some((item) => item.code !== "no_label"),
  );
}

export function toInputs(definitions: AoiDefinition[]): AoiDefinitionInput[] {
  const codeById = new Map(
    definitions.map((item) => [item.id, item.code] as const),
  );
  return definitions
    .filter((item) => item.code !== "no_label")
    .map((item) => ({
      code: item.code,
      name: item.name,
      ...(item.label ? { label: item.label } : {}),
      parentId: item.parentId
        ? (codeById.get(item.parentId) ?? item.parentId)
        : null,
      geometry: item.geometry,
      isContainer: item.isContainer,
      kind: item.kind,
      isActive: item.isActive,
    }));
}

export function nextCustomCode(
  definitions: AoiDefinitionInput[],
  rootCode: string,
): string {
  let index = 1;
  while (definitions.some((item) => item.code === `${rootCode}_custom_${index}`)) {
    index += 1;
  }
  return `${rootCode}_custom_${index}`;
}

export function nextUiCustomCode(definitions: AoiDefinitionInput[]): string {
  let index = 1;
  while (definitions.some((item) => item.code === `ui_custom_${index}`)) {
    index += 1;
  }
  return `ui_custom_${index}`;
}

/** Nhãn vùng slide do giáo viên đặt: AOI_ + 1..60 ký tự A-Z/0-9/_ (tối đa 64). */
const SLIDE_LABEL_PATTERN = /^AOI_[A-Z0-9_]{1,60}$/;

const SLIDE_LABEL_PREFIX = "AOI_";
const SLIDE_LABEL_MAX_LENGTH = 64;

/**
 * Chuẩn hóa chuỗi giáo viên gõ thành nhãn slide hợp lệ:
 * bỏ dấu, viết hoa, bỏ tiền tố SLIDE_, thay ký tự lạ bằng "_", thêm AOI_.
 * Trả "" khi không còn nội dung để đặt nhãn.
 */
export function normalizeSlideLabelInput(raw: string): string {
  let value = raw
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .trim()
    .toUpperCase()
    .replace(/^SLIDE_/, "")
    .replace(/[^A-Z0-9_]/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
  // Chỉ còn đúng tiền tố (người dùng gõ "AOI_") thì coi như chưa có nhãn.
  if (!value || value === "AOI") return "";
  if (!value.startsWith(SLIDE_LABEL_PREFIX)) {
    value = `${SLIDE_LABEL_PREFIX}${value}`;
  }
  if (value.length > SLIDE_LABEL_MAX_LENGTH) {
    value = value.slice(0, SLIDE_LABEL_MAX_LENGTH).replace(/_+$/g, "");
  }
  return SLIDE_LABEL_PATTERN.test(value) ? value : "";
}

/** Trả thông báo lỗi tiếng Việt, hoặc null nếu nhãn hợp lệ và không trùng. */
export function validateSlideLabel(
  label: string,
  definitions: AoiDefinitionInput[],
  currentCode: string,
): string | null {
  const clean = label.trim();
  if (!clean) {
    return "Nhãn phân tích không được để trống.";
  }
  if (!SLIDE_LABEL_PATTERN.test(clean)) {
    return "Nhãn phải có dạng AOI_..., chỉ gồm A-Z, 0-9 và dấu gạch dưới (tối đa 64 ký tự).";
  }
  const duplicate = definitions.some(
    (item) =>
      item.code !== currentCode &&
      item.code !== "no_label" &&
      !item.isContainer &&
      (item.label ?? "").trim().toUpperCase() === clean,
  );
  if (duplicate) {
    return `Nhãn ${clean} đã được dùng cho vùng khác trên slide này.`;
  }
  return null;
}

/** Nhãn slide kế tiếp: AOI_<max+1>. */
export function nextSlideLabel(definitions: AoiDefinitionInput[]): string {
  const numbers = definitions
    .map((item) => /^AOI_(\d+)$/.exec(item.label ?? ""))
    .filter((match): match is RegExpExecArray => match !== null)
    .map((match) => Number(match[1]));
  return `AOI_${Math.max(0, ...numbers) + 1}`;
}

/** Mã của vùng và toàn bộ vùng con (dùng khi xóa). */
export function collectAoiCodes(
  definitions: AoiDefinitionInput[],
  code: string,
): Set<string> {
  const targets = new Set([code]);
  let changed = true;
  while (changed) {
    changed = false;
    for (const item of definitions) {
      if (
        item.parentId &&
        targets.has(item.parentId) &&
        !targets.has(item.code)
      ) {
        targets.add(item.code);
        changed = true;
      }
    }
  }
  return targets;
}

export function countCustom(definitions: AoiDefinitionInput[]): number {
  return definitions.filter((item) => item.kind === "custom").length;
}
