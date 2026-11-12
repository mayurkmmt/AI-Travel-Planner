"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Navbar from "@/components/Navbar";
import { chat } from "@/lib/api";

const DESTINATIONS = [
  { name: "Rajasthan", tagline: "Forts, palaces & desert sunsets", emoji: "🏰", query: "I want to visit Rajasthan" },
  { name: "Goa", tagline: "Beaches, seafood & colonial charm", emoji: "🏖️", query: "I want to visit Goa" },
  { name: "Kerala", tagline: "Backwaters, spices & hill stations", emoji: "🌴", query: "I want to visit Kerala" },
  { name: "Himachal Pradesh", tagline: "Mountains, valleys & adventure", emoji: "🏔️", query: "I want to visit Himachal Pradesh" },
  { name: "Ladakh", tagline: "High-altitude deserts & monasteries", emoji: "🗻", query: "I want to visit Ladakh" },
  { name: "Varanasi", tagline: "Ancient ghats & spiritual energy", emoji: "🪔", query: "I want to visit Varanasi" },
  { name: "Andaman Islands", tagline: "Crystal waters & coral reefs", emoji: "🐠", query: "I want to visit Andaman Islands" },
  { name: "Coorg", tagline: "Coffee estates & misty forests", emoji: "☕", query: "I want to visit Coorg" },
  { name: "Udaipur", tagline: "Lake city of romance & royalty", emoji: "🏯", query: "I want to visit Udaipur" },
];

export default function DiscoverPage() {
  useEffect(() => { document.title = "Discover Destinations — AI Travel Planner"; }, []);
  const router = useRouter();
  const [selecting, setSelecting] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function handleSelect(dest: typeof DESTINATIONS[0]) {
    if (selecting) return;
    if (!localStorage.getItem("token")) return;
    setSelecting(dest.name);
    setError("");
    try {
      const response = await chat.send(dest.query);
      router.push(`/chat/${response.data.trip_id}`);
    } catch {
      setError("Couldn't start the conversation. Please try again.");
      setSelecting(null);
    }
  }

  return (
    <>
      <Navbar />
      <main style={{ minHeight: "calc(100vh - 60px)" }}>
        <div style={{ background: "linear-gradient(135deg, #f0fff4 0%, #e8eee5 100%)", borderBottom: "1px solid var(--border)", padding: "52px var(--page-gutter) 48px" }}>
          <div className="container">
            <p style={{ fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.12em", color: "var(--green-700)", marginBottom: 10 }}>EXPLORE INDIA</p>
            <h1 className="font-display" style={{ marginBottom: 14, color: "var(--green-900)" }}>Discover destinations</h1>
            <p className="text-muted" style={{ fontSize: "1rem", lineHeight: 1.7, maxWidth: 520 }}>Not sure where to go? Pick a destination below and we'll start building your personalised trip.</p>
          </div>
        </div>

        <div className="container" style={{ padding: "36px var(--page-gutter) 40px" }}>
          {error && <p style={{ color: "var(--red)", fontSize: "0.875rem", marginBottom: 16 }}>{error}</p>}

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 20 }}>
            {DESTINATIONS.map((dest) => (
              <div
                key={dest.name}
                className="card"
                style={{ padding: 24, display: "flex", flexDirection: "column", gap: 12, opacity: selecting && selecting !== dest.name ? 0.45 : 1, transition: "opacity 200ms" }}
              >
                <div style={{ fontSize: "2rem" }}>{dest.emoji}</div>
                <div style={{ flex: 1 }}>
                  <h3 style={{ marginBottom: 4 }}>{dest.name}</h3>
                  <p className="text-sm text-muted">{dest.tagline}</p>
                </div>
                <button
                  onClick={() => handleSelect(dest)}
                  disabled={!!selecting}
                  className="btn btn-primary btn-sm"
                  style={{ marginTop: "auto" }}
                >
                  {selecting === dest.name
                    ? <><span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Starting…</>
                    : "Plan a trip →"}
                </button>
              </div>
            ))}
          </div>

          <div className="card" style={{ marginTop: 48, padding: "28px 36px", background: "var(--green-50)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 24, flexWrap: "wrap" }}>
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
