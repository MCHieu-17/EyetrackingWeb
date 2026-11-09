"use client";

import { useState } from "react";
import Link from "next/link";
import { RiCloseLine, RiMenuLine } from "@remixicon/react";
import { BrandLogo } from "@/components/ui/brand-logo";
import { Arrow } from "./landing-arrow";

type MenuItem = readonly [label: string, href: string];

export function LandingHeader({ menuItems }: { menuItems: readonly MenuItem[] }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="ge-header">
      <div className="ge-container ge-nav">
        <Link className="ge-logo" href="/" aria-label="GazeEdu - Trang chủ">
          <BrandLogo variant="light" className="h-[28px]" priority />
        </Link>
        <nav className="ge-navlinks" aria-label="Điều hướng chính">
          {menuItems.map(([label, href]) => (
            <a href={href} key={href}>
              {label}
            </a>
          ))}
        </nav>
        <div className="ge-nav-actions">
          <Link href="/account/login" className="ge-login">
            Đăng nhập
          </Link>
          <Link className="ge-btn ge-btn-dark ge-btn-sm" href="/try">
            Bắt đầu khám phá <Arrow />
          </Link>
          <button
            type="button"
            className="ge-menu"
            onClick={() => setMobileOpen((open) => !open)}
            aria-expanded={mobileOpen}
            aria-label={mobileOpen ? "Đóng menu" : "Mở menu"}
          >
            {mobileOpen ? <RiCloseLine size={23} /> : <RiMenuLine size={23} />}
          </button>
        </div>
      </div>
      {mobileOpen && (
        <nav className="ge-mobile-panel" aria-label="Menu di động">
          {menuItems.map(([label, href]) => (
            <a href={href} key={href} onClick={() => setMobileOpen(false)}>
              {label}
            </a>
          ))}
          <Link href="/account/login">Đăng nhập</Link>
          <Link className="ge-btn ge-btn-dark" href="/try">
            Bắt đầu khám phá <Arrow />
          </Link>
        </nav>
      )}
    </header>
  );
}
