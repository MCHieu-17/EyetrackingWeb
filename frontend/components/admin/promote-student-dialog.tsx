"use client";

import * as React from "react";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { usePromoteStudent } from "@/hooks/use-admin";
import type { AdminStudent } from "@/lib/api/admin";

function PromoteStudentForm({
  student,
  onOpenChange,
  onPromoted,
}: {
  student: AdminStudent;
  onOpenChange: (open: boolean) => void;
  onPromoted: (message: string) => void;
}) {
  const mutation = usePromoteStudent();
  const [teacherCode, setTeacherCode] = React.useState("");
  const [department, setDepartment] = React.useState("");

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (mutation.isPending) return;
    try {
      const result = await mutation.mutateAsync({
        student,
        teacherCode: teacherCode.trim() || null,
        department: department.trim() || null,
      });
      onPromoted(
        `Đã nâng cấp ${student.name} thành giáo viên. Mã giảng viên: ${result.teacherCode}.`,
      );
      onOpenChange(false);
    } catch {
      /* lỗi hiển thị bên dưới */
    }
  };

  return (
    <DialogContent className="max-w-md">
      <DialogHeader>
        <DialogTitle>Nâng cấp giáo viên</DialogTitle>
        <DialogDescription>
          {student.name} · {student.email}
        </DialogDescription>
      </DialogHeader>

      <form onSubmit={handleSubmit} className="flex min-h-0 flex-1 flex-col">
        <div className="space-y-4 px-6 pb-2">
          <div className="space-y-1.5">
            <Label htmlFor="teacher-code">Mã giảng viên</Label>
            <Input
              id="teacher-code"
              value={teacherCode}
              onChange={(event) => setTeacherCode(event.target.value)}
              placeholder="Để trống để tự sinh (VD: GV0001)"
              maxLength={30}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="teacher-department">Khoa / Bộ môn</Label>
            <Input
              id="teacher-department"
              value={department}
              onChange={(event) => setDepartment(event.target.value)}
              placeholder="VD: Khoa Công nghệ thông tin"
              maxLength={150}
            />
          </div>

          {mutation.isError && (
            <Alert variant="destructive" title="Không nâng cấp được">
              {mutation.error instanceof Error
                ? mutation.error.message
                : "Vui lòng thử lại."}
            </Alert>
          )}

          <p className="text-xs leading-5 text-muted-foreground">
            Sau khi nâng cấp, tài khoản sẽ mất quyền sinh viên và cần đăng nhập
            lại để thấy khu vực giảng viên.
          </p>
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={mutation.isPending}
          >
            Hủy
          </Button>
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Đang nâng cấp…" : "Nâng cấp"}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  );
}

export function PromoteStudentDialog({
  student,
  open,
  onOpenChange,
  onPromoted,
}: {
  student: AdminStudent | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPromoted: (message: string) => void;
}) {
  if (!student) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      {open ? (
        <PromoteStudentForm
          key={student.id}
          student={student}
          onOpenChange={onOpenChange}
          onPromoted={onPromoted}
        />
      ) : null}
    </Dialog>
  );
}
