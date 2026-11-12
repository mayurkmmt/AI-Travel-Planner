"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import api, { auth } from "@/lib/api";
import styles from "./page.module.css";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      const res = await auth.login(email, password);
      localStorage.setItem("token", res.data.access_token);
      localStorage.setItem("user", JSON.stringify(res.data.user));
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Invalid email or password");
    } finally { setLoading(false); }
  }

  return (
    <div className={styles.page}>
      {/* Left Panel — hero image */}
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
            <h1 className="font-display">Less planning.<br />More being there.</h1>
            <p>Thoughtful journeys, built around real places, your interests and a budget you can feel good about.</p>
          </div>
          <p className={styles.heroCaption}>
            📍 Lake Palace, Jaipur — Rajasthan
          </p>
        </div>
      </div>

      {/* Right Panel — form */}
      <div className={styles.formPanel}>
        <div className={styles.formHeader}>
          <Link href="/" className={styles.logo}>
            <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
              <rect width="32" height="32" rx="8" fill="#1B4332" />
              <path d="M16 6L26 26H6L16 6Z" fill="white" />
            </svg>
            <span>AI Travel Planner</span>
          </Link>
          <Link href="/register" className="btn btn-ghost btn-sm">Need a trip? Sign up</Link>
        </div>

        <div className={styles.formBody}>
          <div className={styles.formIntro}>
            <span className={styles.eyebrow}>A NEW CHAPTER STARTS HERE</span>
            <h2>Welcome back.</h2>
            <p className="text-muted">Sign in to pick up your plans, or start dreaming up your next adventure.</p>
          </div>

          {error && <div className={styles.errorBox}>{error}</div>}

          <form onSubmit={handleSubmit} className={styles.form}>
            <div className="input-group">
              <label className="input-label" htmlFor="email">Email address</label>
              <input id="email" className="input" type="email" placeholder="you@example.com"
                value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
            <div className="input-group">
              <div className={styles.passwordHeader}>
                <label className="input-label" htmlFor="password">Password</label>
                <Link href="/forgot-password" className={styles.forgot}>Forgot password?</Link>
              </div>
              <input id="password" className="input" type="password" placeholder="Enter your password"
                value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>

            <button className="btn btn-primary btn-lg" style={{ width: "100%" }} disabled={loading} type="submit">
              {loading ? <><span className="spinner" />Signing in...</> : "→ Sign in"}
            </button>
          </form>
    
          <p className={styles.signupLink}>
            New to AI Travel Planner? <Link href="/register">Create an account →</Link>
          </p>

          <p className={styles.disclaimer}>
            By continuing, you agree to our <a href="#">Terms</a> and <a href="#">Privacy Policy</a>.
            AI-generated plans. Prices shown are not live or guaranteed.
          </p>
        </div>
      </div>
    </div>
  );
}
