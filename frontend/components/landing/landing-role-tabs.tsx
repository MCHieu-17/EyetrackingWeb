"use client";

import { useState } from "react";
import Link from "next/link";
import { RiBookOpenLine } from "@remixicon/react";
import { Arrow } from "./landing-arrow";

type Role = "student" | "teacher";

const roles: Record<Role, { title: string; desc: string; points: string[] }> = {
  student: {
    title: "Chủ động với hành trình của mình.",
    desc: "Quản lý khóa học và đọc tài liệu bài giảng trong cùng một nơi.",
    points: [
      "Khóa học và tài liệu trong cùng một nơi",
      "Xem bài giảng dạng slide",
      "Xem lại kết quả và quá trình học",
    ],
  },
  teacher: {
    title: "Thấu hiểu cách người học tương tác.",
    desc: "Tổ chức nội dung giảng dạy và tham khảo trực quan hóa điểm nhìn để hiểu rõ hơn cách học viên tiếp cận tài liệu.",
    points: [
      "Tổ chức và quản lý khóa học",
      "Quan sát bản đồ nhiệt điểm nhìn",
      "Tham khảo dữ liệu hỗ trợ giảng dạy",
    ],
  },
};

export function LandingRoleTabs() {
  const [role, setRole] = useState<Role>("student");
  const current = roles[role];

  return (
    <div className="ge-role-tabs-wrap">
      <div className="ge-tabs" role="tablist" aria-label="Vai trò sử dụng">
        {(["student", "teacher"] as const).map((key) => (
          <button
            key={key}
            type="button"
            className="ge-tab"
            role="tab"
            id={`role-${key}`}
            aria-controls="ge-role-panel"
            aria-selected={role === key}
            onClick={() => setRole(key)}
          >
            {key === "student" ? "Người học" : "Giảng viên"}
          </button>
        ))}
      </div>
      <div
        id="ge-role-panel"
        role="tabpanel"
        aria-labelledby={`role-${role}`}
        className="ge-role-detail"
      >
        <div className="ge-role-icon">
          <RiBookOpenLine size={21} />
        </div>
        <div>
          <h3>{current.title}</h3>
          <p>{current.desc}</p>
          <ul className="ge-role-points">
            {current.points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
          <Link href="/try" className="ge-text-link">
            Khám phá trải nghiệm học tập <Arrow />
          </Link>
        </div>
      </div>
    </div>
  );
}
