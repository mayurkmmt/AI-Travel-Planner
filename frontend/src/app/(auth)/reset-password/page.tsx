"use client";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense } from "react";
import { useState } from "react";
import { auth } from "@/lib/api";
import styles from "../login/page.module.css";

function ResetPasswordForm() {
  const params = useSearchParams(); const router = useRouter();
  const token = params.get("token") || "";
  const [password, setPassword] = useState(""); const [confirm, setConfirm] = useState("");
  const [error, setError] = useState(""); const [loading, setLoading] = useState(false); const [done, setDone] = useState(false);
  async function handleSubmit(e: React.FormEvent) { e.preventDefault(); setError(""); if (password.length < 8) return setError("Password must be at least 8 characters"); if (password !== confirm) return setError("Passwords do not match"); setLoading(true); try { await auth.resetPassword(token, password); setDone(true); setTimeout(() => router.push("/login"), 1500); } catch (err: unknown) { const response = (err as { response?: { data?: { detail?: string } } }).response; setError(response?.data?.detail || "This reset link is invalid or has expired."); } finally { setLoading(false); } }
  return <div className={styles.page}><div className={styles.formPanel} style={{width:"100%"}}><div className={styles.formHeader}><Link href="/" className={styles.logo}>AI Travel Planner</Link><Link href="/login" className="btn btn-ghost btn-sm">Back to sign in</Link></div><div className={styles.formBody}><div className={styles.formIntro}><span className={styles.eyebrow}>ACCOUNT RECOVERY</span><h2>Choose a new password.</h2><p className="text-muted">Use at least 8 characters to keep your account secure.</p></div>{done ? <div className={styles.successBox}>Your password has been reset. Redirecting to sign in...</div> : !token ? <div className={styles.errorBox}>This reset link is missing or invalid.</div> : <form onSubmit={handleSubmit} className={styles.form}>{error && <div className={styles.errorBox}>{error}</div>}<div className="input-group"><label className="input-label" htmlFor="password">New password</label><input id="password" className="input" type="password" minLength={8} value={password} onChange={e => setPassword(e.target.value)} required /></div><div className="input-group"><label className="input-label" htmlFor="confirm">Confirm new password</label><input id="confirm" className="input" type="password" value={confirm} onChange={e => setConfirm(e.target.value)} required /></div><button className="btn btn-primary btn-lg" style={{width:"100%"}} disabled={loading}>{loading ? <><span className="spinner"/>Resetting...</> : "Reset password"}</button></form>}</div></div></div>;
}

export default function ResetPasswordPage() {
  return <Suspense fallback={null}><ResetPasswordForm /></Suspense>;
}
