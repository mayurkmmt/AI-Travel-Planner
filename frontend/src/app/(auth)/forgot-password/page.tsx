"use client";
import Link from "next/link";
import { useState } from "react";
import { auth } from "@/lib/api";
import styles from "../login/page.module.css";

function errorMessage(error: unknown, fallback: string) {
  const response = (error as { response?: { data?: { detail?: string } } }).response;
  return response?.data?.detail || fallback;
}

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault(); setError(""); setLoading(true);
    try { await auth.forgotPassword(email); setSent(true); }
    catch (err: unknown) { setError(errorMessage(err, "Could not send the reset link. Please try again.")); }
    finally { setLoading(false); }
  }

  return <div className={styles.page}><div className={styles.hero}><div className={styles.heroOverlay}/><div className={styles.heroContent}><div className={styles.heroLogo}><span>✦</span><span>AI Travel Planner</span></div><div className={styles.heroText}><h1 className="font-display">Find your way back.</h1><p>Reset your password and get back to planning the journey ahead.</p></div><p className={styles.heroCaption}>📍 Somewhere worth going</p></div></div>
    <div className={styles.formPanel}><div className={styles.formHeader}><Link href="/" className={styles.logo}>AI Travel Planner</Link><Link href="/login" className="btn btn-ghost btn-sm">Back to sign in</Link></div>
      <div className={styles.formBody}><div className={styles.formIntro}><span className={styles.eyebrow}>ACCOUNT RECOVERY</span><h2>Forgot your password?</h2><p className="text-muted">Enter your email and we’ll send you a secure reset link.</p></div>
        {sent ? <><div className={styles.successBox}>If an account exists for <strong>{email}</strong>, you’ll receive a reset link shortly. Check your spam folder if it doesn’t arrive.</div><p className={styles.signupLink}><Link href="/login">← Back to sign in</Link></p></> : <><form onSubmit={handleSubmit} className={styles.form}>{error && <div className={styles.errorBox}>{error}</div>}<div className="input-group"><label className="input-label" htmlFor="email">Email address</label><input id="email" className="input" type="email" placeholder="you@example.com" value={email} onChange={e => setEmail(e.target.value)} required /></div><button className="btn btn-primary btn-lg" style={{width:"100%"}} disabled={loading}>{loading ? <><span className="spinner"/>Sending...</> : "Send reset link"}</button></form><p className={styles.signupLink}>Remembered your password? <Link href="/login">Sign in →</Link></p></>}</div>
    </div></div>;
}
