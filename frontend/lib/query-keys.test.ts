import { describe, expect, it } from "vitest";
import { queryKeys } from "./query-keys";

describe("queryKeys", () => {
  it("returns stable arrays for the same input", () => {
    expect(queryKeys.teacher.courseTree("course-1")).toEqual(
      queryKeys.teacher.courseTree("course-1"),
    );
    expect(queryKeys.teacher.courseTree("course-1")).toEqual([
      "teacher",
      "course-tree",
      "course-1",
    ]);
  });

  it("builds admin and teacher keys", () => {
    expect(queryKeys.admin.students("an")).toEqual(["admin", "students", "an"]);
    expect(queryKeys.admin.studentsRoot).toEqual(["admin", "students"]);
    expect(queryKeys.teacher.courses({ status: "draft" })).toEqual([
      "teacher",
      "courses",
      { status: "draft" },
    ]);
    expect(queryKeys.teacher.coursesRoot).toEqual(["teacher", "courses"]);
    expect(queryKeys.teacher.courseStudents("course-1")).toEqual([
      "teacher",
      "course-students",
      "course-1",
    ]);
    expect(queryKeys.teacher.lessonSlides("lesson-1")).toEqual([
      "teacher",
      "lesson-slides",
      "lesson-1",
    ]);
    expect(queryKeys.teacher.studentDirectory("an")).toEqual([
      "teacher",
      "student-directory",
      "an",
    ]);
  });

  it("builds student and quiz keys", () => {
    expect(queryKeys.student.enrollments).toEqual(["student", "enrollments"]);
    expect(queryKeys.student.courseOutline("course-1")).toEqual([
      "student",
      "course-outline",
      "course-1",
    ]);
    expect(queryKeys.student.lessonSlides("lesson-1", null)).toEqual([
      "student",
      "lesson-slides",
      "lesson-1",
      null,
    ]);
    expect(queryKeys.quiz.assignment("assignment-1")).toEqual([
      "quiz",
      "assignment",
      "assignment-1",
    ]);
    expect(queryKeys.quiz.attempt("lesson-1")).toEqual([
      "quiz",
      "attempt",
      "lesson-1",
    ]);
  });

  it("builds chat, profile and auth keys", () => {
    expect(queryKeys.chat.sessions("course-1", null, null)).toEqual([
      "chat",
      "sessions",
      "course-1",
      null,
      null,
    ]);
    expect(queryKeys.chat.sessionsRoot).toEqual(["chat", "sessions"]);
    expect(queryKeys.chat.messages("session-1")).toEqual([
      "chat",
      "messages",
      "session-1",
    ]);
    expect(queryKeys.chat.access("course-1")).toEqual([
      "chat",
      "access",
      "course-1",
    ]);
    expect(queryKeys.profile).toEqual(["me", "profile"]);
    expect(queryKeys.authUser).toEqual(["auth", "user"]);
  });
});
