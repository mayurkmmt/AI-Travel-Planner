"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import styles from "./Navbar.module.css";

export default function Navbar() {
  const router = useRouter();
  const pathname = usePathname();
  const [initials, setInitials] = useState("U");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const user = JSON.parse(localStorage.getItem("user") || "{}");
      setFullName(user.full_name || "");
      setEmail(user.email || "");
      setInitials(
        (user.full_name || "U")
          .split(" ")
          .map((name: string) => name[0])
          .join("")
          .toUpperCase()
          .slice(0, 2),
      );
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleLogout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.push("/login");
  }

  return (
    <header className={styles.navbar}>
      <div className={`container ${styles.inner}`}>
        <Link href="/dashboard" className={styles.logo}>
          <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
            <rect width="32" height="32" rx="8" fill="#1B4332" />
            <path d="M16 6L26 26H6L16 6Z" fill="white" />
          </svg>
          <span>AI Travel Planner</span>
        </Link>

        <nav className={styles.nav}>
          {([
            { href: "/dashboard", label: "My trips" },
            { href: "/discover", label: "Discover destinations" },
            { href: "/how-it-works", label: "How it works" },
            { href: "/faq", label: "FAQ" },
          ] as { href: string; label: string }[]).map(({ href, label }) => {
            const isActive = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={`${styles.navLink} ${isActive ? styles.navLinkActive : ""}`}
              >
                {label}
              </Link>
            );
          })}
        </nav>

        <div className={styles.actions}>
          <Link
            href="/chat"
            className="btn btn-primary btn-sm"
            style={{ visibility: (!pathname.startsWith("/chat") && pathname !== "/dashboard") ? "visible" : "hidden" }}
          >+ New conversation</Link>

          <div className={styles.avatarWrapper} ref={dropdownRef}>
            <button
              className={styles.avatar}
              onClick={() => setDropdownOpen((o) => !o)}
              aria-haspopup="true"
              aria-expanded={dropdownOpen}
            >
              {initials}
            </button>

            {dropdownOpen && (
              <div className={styles.dropdown}>
                <div className={styles.dropdownHeader}>
                  <div className={styles.dropdownAvatar}>{initials}</div>
                  <div>
                    {fullName && <p className={styles.dropdownName}>{fullName}</p>}
                    {email && <p className={styles.dropdownEmail}>{email}</p>}
                  </div>
                </div>
                <div className={styles.dropdownDivider} />
                <Link href="/profile" className={styles.dropdownItem} onClick={() => setDropdownOpen(false)}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>
                  Profile
                </Link>
                <Link href="/dashboard" className={styles.dropdownItem} onClick={() => setDropdownOpen(false)}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
                  My trips
                </Link>
                <div className={styles.dropdownDivider} />
                <button className={`${styles.dropdownItem} ${styles.dropdownLogout}`} onClick={handleLogout}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
