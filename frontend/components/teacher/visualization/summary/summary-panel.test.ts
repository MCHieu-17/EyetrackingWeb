import { describe, expect, it } from "vitest";
import { buildSummaryQuery, type SummaryQueryInput } from "./summary-panel";

function input(overrides: Partial<SummaryQueryInput> = {}): SummaryQueryInput {
  return {
    scope: "student",
    lessonId: "",
    from: "",
    to: "",
    surface: "all",
    includeDropped: false,
    onlyCounted: false,
    resolvedStudentId: "student-1",
    resolvedVisitId: "visit-1",
    selectedStudentIds: [],
    ...overrides,
  };
}

describe("buildSummaryQuery", () => {
  it("mặc định tính cả lượt ngắn", () => {
    const query = buildSummaryQuery(input());
    expect(query.includeShort).toBe(true);
    expect(query.studentIds).toEqual(["student-1"]);
  });

  it("chỉ gửi includeShort=false khi bật bộ lọc ngưỡng", () => {
    expect(buildSummaryQuery(input({ onlyCounted: true })).includeShort).toBe(
      false,
    );
  });

  it("áp dụng bộ lọc lượt ngắn cho mọi scope", () => {
    expect(
      buildSummaryQuery(
        input({ scope: "visit", resolvedVisitId: "visit-9", onlyCounted: true }),
      ),
    ).toMatchObject({ visitIds: ["visit-9"], includeShort: false });
    expect(
      buildSummaryQuery(input({ scope: "cohort", selectedStudentIds: ["a", "b"] })),
    ).toMatchObject({ studentIds: ["a", "b"], includeShort: true });
  });
});
