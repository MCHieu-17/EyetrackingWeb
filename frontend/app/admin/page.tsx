import { AppShell } from "@/components/layout/app-shell";
import { StudentPromotion } from "@/components/admin/student-promotion";

export default function AdminPage() {
  return (
    <AppShell
      role="admin"
      title="Nâng cấp giáo viên"
      description="Chọn một sinh viên để cấp quyền giảng viên. Sau khi nâng cấp, tài khoản sẽ không còn quyền sinh viên."
    >
      <StudentPromotion />
    </AppShell>
  );
}
