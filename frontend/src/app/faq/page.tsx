"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import Navbar from "@/components/Navbar";

const FAQS = [
  { q: "Can I plan trips outside India?", a: "Currently we're optimised for Indian destinations. International trip planning is coming soon." },
  { q: "How accurate are the destination suggestions?", a: "Suggestions are based on your stated interests, budget, and travel dates. They're a starting point — you can always ask us to refine or swap destinations." },
  { q: "Are the prices accurate?", a: "All cost estimates are AI-generated approximations based on typical ranges. Always verify prices with official providers before booking." },
  { q: "Does it book hotels or flights?", a: "No — we're a planning tool, not a booking platform. We suggest options; you book directly with providers." },
  { q: "How do I share my trip?", a: "Click the Share trip button on your trip page. It copies a read-only link that anyone can view without logging in." },
  { q: "Is it free to use?", a: "Yes — creating an account and planning trips is completely free. No credit card required, no hidden charges." },
  { q: "Can I edit the plan after it's generated?", a: "Yes. Use the Edit Plan button on your trip page to change budget, days, style, or pace and regenerate. You can also make small edits through the chat." },
];

export default function FAQPage() {
  useEffect(() => { document.title = "FAQ — AI Travel Planner"; }, []);
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  return (
    <>
      <Navbar />
      <main style={{ minHeight: "calc(100vh - 60px)" }}>

        {/* Hero */}
        <div style={{ background: "linear-gradient(135deg, #f0fff4 0%, #e8eee5 100%)", borderBottom: "1px solid var(--border)", padding: "52px var(--page-gutter) 48px" }}>
          <div className="container">
            <p style={{ fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.12em", color: "var(--green-700)", marginBottom: 10 }}>SUPPORT · FAQ</p>
            <h1 className="font-display" style={{ marginBottom: 14, color: "var(--green-900)" }}>Frequently asked questions</h1>
            <p className="text-muted" style={{ fontSize: "1rem", lineHeight: 1.7, maxWidth: 520 }}>
              Everything you need to know about AI Travel Planner.
            </p>
          </div>
        </div>

        {/* FAQ list */}
        <div className="container" style={{ padding: "36px var(--page-gutter) 40px" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, maxWidth: 760, marginBottom: 40 }}>
            {FAQS.map((faq, i) => {
              const isOpen = openIndex === i;
              return (
                <div key={i} className="card" style={{ padding: 0, overflow: "hidden" }}>
                  <button
                    onClick={() => setOpenIndex(isOpen ? null : i)}
                    style={{ width: "100%", padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", background: isOpen ? "var(--green-50)" : "none", border: "none", cursor: "pointer", textAlign: "left", fontWeight: 500, fontSize: "0.9rem", color: "var(--text)", gap: 12, transition: "background 200ms" }}
                  >
                    {faq.q}
                    <span style={{ width: 24, height: 24, borderRadius: "50%", background: isOpen ? "var(--green-800)" : "var(--bg-muted)", color: isOpen ? "#fff" : "var(--text-muted)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1rem", flexShrink: 0, transition: "all 200ms" }}>
                      {isOpen ? "−" : "+"}
                    </span>
                  </button>
                  {isOpen && (
                    <p style={{ padding: "12px 20px 16px", fontSize: "0.875rem", color: "var(--text-sub)", lineHeight: 1.7, borderTop: "1px solid var(--border)", margin: 0 }}>{faq.a}</p>
                  )}
                </div>
              );
            })}
          </div>

          {/* CTA */}
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
