import { AppShell } from "@/components/layout/app-shell";
import { DatabaseConsole } from "@/components/admin/database/database-console";

export default function AdminDatabasePage() {
  return (
    <AppShell
      role="admin"
      title="Truy vấn cơ sở dữ liệu"
      description="Chạy câu lệnh SELECT trên cơ sở dữ liệu để tra cứu dữ liệu hệ thống. Chế độ chỉ đọc, tối đa 500 dòng và 10 giây mỗi truy vấn."
    >
      <DatabaseConsole />
    </AppShell>
  );
}
