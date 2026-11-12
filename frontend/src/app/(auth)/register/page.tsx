"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { auth } from "@/lib/api";
import styles from "../login/page.module.css";

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({ full_name: "", email: "", password: "", confirm: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function set(k: string, v: string) { setForm((f) => ({ ...f, [k]: v })); }

  function passwordStrength(pw: string): { label: string; color: string; width: string } {
    if (!pw) return { label: "", color: "transparent", width: "0%" };
    let score = 0;
    if (pw.length >= 8) score++;
    if (pw.length >= 12) score++;
    if (/[A-Z]/.test(pw)) score++;
    if (/[0-9]/.test(pw)) score++;
    if (/[^A-Za-z0-9]/.test(pw)) score++;
    if (score <= 1) return { label: "Weak", color: "var(--red)", width: "25%" };
    if (score <= 3) return { label: "Medium", color: "var(--amber)", width: "60%" };
    return { label: "Strong", color: "var(--green-500)", width: "100%" };
  }

  const strength = passwordStrength(form.password);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (form.password !== form.confirm) { setError("Passwords do not match"); return; }
    if (form.password.length < 8) { setError("Password must be at least 8 characters"); return; }
    setLoading(true);
    try {
      const res = await auth.register({ email: form.email, full_name: form.full_name, password: form.password });
      localStorage.setItem("token", res.data.access_token);
      localStorage.setItem("user", JSON.stringify(res.data.user));
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Registration failed. Please try again.");
    } finally { setLoading(false); }
  }

  return (
    <div className={styles.page}>
      {/* Left hero */}
      <div className={styles.hero}>
        <div className={styles.heroOverlay} />
        <div className={styles.heroContent}>
          <div className={styles.heroLogo}>
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <rect width="32" height="32" rx="8" fill="rgba(255,255,255,0.15)" />
              <path d="M16 6L26 26H6L16 6Z" fill="white" fillOpacity=".9" />
            </svg>
            <span>AI Travel Planner</span>
          </div>
          <div className={styles.heroText}>
            <h1 className="font-display">Your next adventure starts here.</h1>
            <p>Create your free account and let AI build you a personalised trip — real places, real budgets, zero hassle.</p>
          </div>
          <p className={styles.heroCaption}>📍 Mehrangarh Fort, Jodhpur — Rajasthan</p>
        </div>
      </div>

      {/* Right form */}
      <div className={styles.formPanel}>
        <div className={styles.formHeader}>
          <Link href="/" className={styles.logo}>
            <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
              <rect width="32" height="32" rx="8" fill="#1B4332" />
              <path d="M16 6L26 26H6L16 6Z" fill="white" />
            </svg>
            <span>AI Travel Planner</span>
          </Link>
          <Link href="/login" className="btn btn-ghost btn-sm">Already have an account?</Link>
        </div>

        <div className={styles.formBody}>
          <div className={styles.formIntro}>
            <span className={styles.eyebrow}>JOIN FOR FREE</span>
            <h2>Create your account.</h2>
            <p className="text-muted">No credit card required. Start planning in seconds.</p>
          </div>

          {error && <div className={styles.errorBox}>{error}</div>}

          <form onSubmit={handleSubmit} className={styles.form}>
            <div className="input-group">
              <label className="input-label" htmlFor="name">Full name</label>
              <input id="name" className="input" type="text" placeholder="Arjun Sharma"
                value={form.full_name} onChange={(e) => set("full_name", e.target.value)} required />
            </div>
            <div className="input-group">
              <label className="input-label" htmlFor="email">Email address</label>
              <input id="email" className="input" type="email" placeholder="you@example.com"
                value={form.email} onChange={(e) => set("email", e.target.value)} required />
            </div>
            <div className="input-group">
              <label className="input-label" htmlFor="password">Password</label>
              <input id="password" className="input" type="password" placeholder="At least 8 characters"
                value={form.password} onChange={(e) => set("password", e.target.value)} required minLength={8} />
              {form.password && (
                <div style={{ marginTop: 6 }}>
                  <div style={{ height: 4, borderRadius: 4, background: "var(--bg-muted)", overflow: "hidden" }}>
                    <div style={{ height: "100%", width: strength.width, background: strength.color, borderRadius: 4, transition: "width 0.3s, background 0.3s" }} />
                  </div>
                  <span style={{ fontSize: "0.75rem", color: strength.color, marginTop: 3, display: "block" }}>{strength.label}</span>
                </div>
              )}
            </div>
            <div className="input-group">
              <label className="input-label" htmlFor="confirm">Confirm password</label>
              <input id="confirm" className="input" type="password" placeholder="Repeat your password"
                value={form.confirm} onChange={(e) => set("confirm", e.target.value)} required />
            </div>
            <button className="btn btn-primary btn-lg" style={{ width: "100%" }} disabled={loading} type="submit">
              {loading ? <><span className="spinner" />Creating account...</> : "→ Create account"}
            </button>
          </form>

          <p className={styles.signupLink}>
            Already have an account? <Link href="/login">Sign in →</Link>
          </p>
          <p className={styles.disclaimer}>
            By creating an account you agree to our <a href="#">Terms</a> and <a href="#">Privacy Policy</a>.
            AI-generated plans. Prices shown are estimates, not live quotes.
          </p>
        </div>
      </div>
    </div>
  );
}
