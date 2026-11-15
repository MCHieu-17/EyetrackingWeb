import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";
import { ReaderFrame } from "./index";

function renderFrame(overrides: Partial<Parameters<typeof ReaderFrame>[0]> = {}) {
  return render(
    <ReaderFrame
      courseTitle="Course"
      modules={[]}
      activeLessonId="lesson-1"
      activeLesson={null}
      activeModule={null}
      slides={[]}
      currentSlide={0}
      activeIsQuiz={false}
      chatOpen={false}
      chatAllowed
      onToggleChat={vi.fn()}
      onSelectLesson={vi.fn()}
      onPrevSlide={vi.fn()}
      onNextSlide={vi.fn()}
      slideContent={<div data-aoi="slide">Slide</div>}
      quizContent={<div data-aoi="quiz-question">Quiz</div>}
      {...overrides}
    />,
  );
}

afterEach(() => {
  cleanup();
});

describe("ReaderFrame layout", () => {
  it("không tạo vùng cuộn ngoài cho slide và đặt nav ngoài vùng nội dung", () => {
    const { container } = renderFrame();

    const main = container.querySelector('[data-aoi="lesson-content"]');
    expect(main).not.toBeNull();
    expect(main?.querySelector(".overflow-auto")).toBeNull();

    const nav = container.querySelector('[data-aoi="lesson-nav"]');
    expect(nav).not.toBeNull();
    expect(nav?.closest(".overflow-auto")).toBeNull();
    expect(nav?.parentElement?.className).toContain("shrink-0");
    expect(main?.contains(nav)).toBe(true);
  });

  it("co slide theo container query thay vì chiều cao viewport", () => {
    const { container } = renderFrame();

    const slide = container.querySelector('[data-aoi="slide"]');
    expect(slide).not.toBeNull();
    const stage = container.querySelector(
      '[data-aoi="slide"]',
    )?.parentElement;
    expect(stage?.className).toContain("100cqh");
    expect(stage?.className).toContain("aspect-video");
  });

  it("quiz dùng khung cố định, không có nav chuyển slide", () => {
    const { container } = renderFrame({ activeIsQuiz: true });

    const quiz = container.querySelector('[data-aoi="quiz"]');
    expect(quiz?.className).toContain("flex-1");
    expect(quiz?.className).toContain("overflow-hidden");
    expect(container.querySelector('[data-aoi="lesson-nav"]')).toBeNull();
  });
});
