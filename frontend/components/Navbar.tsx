"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  { href: "/", label: "Home" },
  { href: "/inference", label: "Inference" },
  { href: "/dashboard", label: "Dashboard" },
];

export default function Navbar() {
  const pathname = usePathname();

  return (
    <header className="site-nav-wrap">
      <nav className="site-nav" aria-label="Primary">
        <Link className="brand-mark" href="/">
          <span className="brand-mark-symbol">S</span>
          <span className="brand-mark-copy">
            <strong>Smart Drone</strong>
            <span>Traffic Analyzer</span>
          </span>
        </Link>

        <div className="nav-links">
          {NAV_ITEMS.map((item) => {
            const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);

            return (
              <Link key={item.href} className={`nav-link${isActive ? " is-active" : ""}`} href={item.href}>
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </header>
  );
}