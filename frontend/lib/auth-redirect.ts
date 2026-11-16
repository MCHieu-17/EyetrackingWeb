import { primaryRole, ROLE_HOME, type AuthUser, type Role } from "@/lib/api/auth";

const PROTECTED = ["/student", "/teacher", "/admin"] as const;

/** True khi đường dẫn thuộc một khu vực yêu cầu đăng nhập. */
function isProtected(path: string | null): path is string {
  if (!path) return false;
  return PROTECTED.some((p) => path === p || path.startsWith(`${p}/`));
}

/**
 * Chọn điểm đến sau đăng nhập: chỉ giữ `next` khi user có role tương ứng,
 * ngược lại về trang chủ của role chính.
 */
export function resolveRedirect(user: Pick<AuthUser, "roles">, next: string | null): string {
  const roles = user.roles ?? [];
  // Ưu tiên role khớp với ?next để tránh redirect chéo role
  if (isProtected(next)) {
    const zone = next.split("/")[1] as Role;
    if (roles.includes(zone)) return next;
  }
  return ROLE_HOME[primaryRole(roles)];
}
