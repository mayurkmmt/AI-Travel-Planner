"use client";
import Link from "next/link";
import { useEffect } from "react";
import Navbar from "@/components/Navbar";

const STEPS = [
  { num: "01", title: "Tell us about your trip", desc: "Just type naturally — destination, budget, dates, who's coming. No forms, no dropdowns. We ask one follow-up at a time.", icon: "💬" },
  { num: "02", title: "AI builds your full plan", desc: "In 20–40 seconds, we generate a day-by-day itinerary, hotel suggestions, dining picks, budget breakdown, and packing list.", icon: "🗺️" },
  { num: "03", title: "Edit anything, anytime", desc: "Change your budget, swap a hotel, add an activity, or adjust the pace — just tell us what you want and we'll update the plan.", icon: "✏️" },
  { num: "04", title: "Share your trip", desc: "Generate a read-only share link and send it to travel companions or family. No account needed to view.", icon: "🔗" },
];


export default function HowItWorksPage() {
  useEffect(() => { document.title = "How It Works — AI Travel Planner"; }, []);

  return (
    <>
      <Navbar />
      <main style={{ minHeight: "calc(100vh - 60px)" }}>
        <div style={{ background: "linear-gradient(135deg, #f0fff4 0%, #e8eee5 100%)", borderBottom: "1px solid var(--border)", padding: "52px var(--page-gutter) 48px" }}>
          <div className="container">
            <p style={{ fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.12em", color: "var(--green-700)", marginBottom: 10 }}>HOW IT WORKS</p>
            <h1 className="font-display" style={{ marginBottom: 14, color: "var(--green-900)" }}>Less planning. More being there.</h1>
            <p className="text-muted" style={{ fontSize: "1rem", lineHeight: 1.7, maxWidth: 520 }}>AI Travel Planner turns a simple conversation into a complete, personalised trip plan — itinerary, stays, dining, budget, and packing list included.</p>
          </div>
        </div>

        <div className="container" style={{ padding: "36px var(--page-gutter) 40px" }}>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 24, marginBottom: 48 }}>
            {STEPS.map((step) => (
              <div key={step.num} className="card" style={{ padding: 28 }}>
                <div style={{ fontSize: "2rem", marginBottom: 12 }}>{step.icon}</div>
                <p style={{ fontSize: "0.7rem", fontWeight: 700, letterSpacing: "0.1em", color: "var(--green-800)", marginBottom: 6 }}>STEP {step.num}</p>
                <h3 style={{ marginBottom: 8 }}>{step.title}</h3>
                <p className="text-sm text-muted">{step.desc}</p>
              </div>
            ))}
          </div>

          <div className="card" style={{ padding: "28px 36px", background: "var(--green-50)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 24, flexWrap: "wrap" }}>
            <div>
              <h3 style={{ marginBottom: 4 }}>Ready to plan your trip?</h3>
              <p className="text-muted">It takes less than a minute to get started. No credit card, no forms.</p>
            </div>
            <Link href="/chat" className="btn btn-primary" style={{ flexShrink: 0 }}>Start a conversation →</Link>
          </div>
        </div>
      </main>
    </>
  );
}
