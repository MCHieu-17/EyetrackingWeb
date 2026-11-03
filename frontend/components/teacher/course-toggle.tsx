"use client";

import { Icon } from "@/components/ui/icon";
import { Switch } from "@/components/ui/switch";

/**
 * Khung công tắc dùng chung cho các thiết lập cấp KHÓA HỌC.
 * Giữ cùng style với công tắc "Hiển thị điểm nhìn cho sinh viên".
 */
export function CourseToggle({
  icon,
  title,
  description,
  checked,
  disabled,
  busy,
  onChange,
  ariaLabel,
}: {
  icon: string;
  title: string;
  description: string;
  checked: boolean;
  disabled?: boolean;
  busy?: boolean;
  onChange: (value: boolean) => void;
  ariaLabel: string;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-[16px] border border-[#dfe9dc] bg-[#e8f1e6]/45 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <h4 className="flex items-center gap-2 text-sm font-semibold text-black">
          <Icon name={icon} className="size-4 text-[#52704f]" />
          {title}
        </h4>
        <p className="mt-1 text-xs leading-5 text-black/70">{description}</p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {busy && <Icon name="ri-loader-4-line" className="size-4 animate-spin text-[#52704f]" />}
        <Switch
          checked={checked}
          disabled={disabled || busy}
          onCheckedChange={onChange}
          ariaLabel={ariaLabel}
        />
      </div>
    </div>
  );
}
