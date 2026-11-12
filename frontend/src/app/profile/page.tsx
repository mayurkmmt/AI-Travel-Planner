"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";

export default function ProfilePage() {
  const router = useRouter();
  const [user, setUser] = useState<{ full_name?: string; email?: string }>({});

  useEffect(() => {
    document.title = "Profile — AI Travel Planner";
    if (!localStorage.getItem("token")) { router.replace("/login"); return; }
    try {
      setUser(JSON.parse(localStorage.getItem("user") || "{}"));
    } catch { setUser({}); }
  }, [router]);

  const initials = (user.full_name || "U")
    .split(" ")
    .map((n: string) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  function handleLogout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    router.push("/login");
  }

  return (
    <>
      <Navbar />
      <main style={{ minHeight: "calc(100vh - 60px)" }}>
        <div style={{ background: "linear-gradient(135deg, #f0fff4 0%, #e8eee5 100%)", borderBottom: "1px solid var(--border)", padding: "52px var(--page-gutter) 48px" }}>
          <div className="container">
            <p style={{ fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.12em", color: "var(--green-700)", marginBottom: 10 }}>ACCOUNT</p>
            <h1 className="font-display" style={{ marginBottom: 6, color: "var(--green-900)" }}>Your profile</h1>
            <p className="text-muted" style={{ fontSize: "1rem" }}>Manage your account details.</p>
          </div>
        </div>

        <div className="container" style={{ padding: "36px var(--page-gutter) 40px" }}>
          <div style={{ maxWidth: 520 }}>

            {/* Avatar + name */}
            <div className="card" style={{ padding: "28px 28px", marginBottom: 16, display: "flex", alignItems: "center", gap: 20 }}>
              <div style={{ width: 64, height: 64, borderRadius: "50%", background: "var(--green-800)", color: "#fff", fontSize: "1.4rem", fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                {initials}
              </div>
              <div>
                <p style={{ fontWeight: 600, fontSize: "1.1rem", marginBottom: 2 }}>{user.full_name || "—"}</p>
                <p style={{ fontSize: "0.875rem", color: "var(--text-muted)" }}>{user.email || "—"}</p>
              </div>
            </div>

            {/* Details */}
            <div className="card" style={{ padding: "0", marginBottom: 16, overflow: "hidden" }}>
              <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: 500 }}>FULL NAME</span>
                <span style={{ fontSize: "0.9rem" }}>{user.full_name || "—"}</span>
              </div>
              <div style={{ padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: "0.8rem", color: "var(--text-muted)", fontWeight: 500 }}>EMAIL</span>
                <span style={{ fontSize: "0.9rem" }}>{user.email || "—"}</span>
              </div>
            </div>

            {/* Sign out */}
            <button
              onClick={handleLogout}
              style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 18px", borderRadius: "var(--r-md)", border: "1px solid var(--red)", background: "var(--red-bg)", color: "var(--red)", fontSize: "0.875rem", fontWeight: 500, cursor: "pointer" }}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
              Sign out
            </button>
          </div>
        </div>
      </main>
    </>
  );
}
