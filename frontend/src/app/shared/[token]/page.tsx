"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { shared as sharedApi } from "@/lib/api";

export default function SharedTripPage() {
  const params = useParams();
  const token = params.token as string;
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    sharedApi.get(token)
      .then((res) => setData(res.data))
      .catch(() => setError("This link is invalid or has expired."))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <span className="spinner" />
    </div>
  );

  if (error || !data) return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16, padding: 32 }}>
      <h2>Link not found</h2>
      <p className="text-muted">{error}</p>
      <Link href="/" className="btn btn-primary">Plan your own trip →</Link>
    </div>
  );

  const { trip, itinerary, budget_breakdown: bd, hotels, weather } = data;
  const destinations = (trip.destinations || []).map((d: any) => d.city || d.state).filter(Boolean).join(" → ");

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)" }}>
      {/* Header */}
      <header style={{ background: "var(--bg-card)", borderBottom: "1px solid var(--border)", padding: "16px var(--page-gutter)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Link href="/" style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 600 }}>
          <svg width="24" height="24" viewBox="0 0 32 32" fill="none">
            <rect width="32" height="32" rx="8" fill="#1B4332" />
            <path d="M16 6L26 26H6L16 6Z" fill="white" />
          </svg>
          AI Travel Planner
        </Link>
        <span className="badge badge-muted">Read-only shared view</span>
      </header>

      <main style={{ maxWidth: 800, margin: "0 auto", padding: "32px var(--page-gutter)" }}>
        {/* Trip title */}
        <div style={{ marginBottom: 32 }}>
          <h1 className="font-display" style={{ fontSize: "clamp(1.5rem,4vw,2.2rem)", marginBottom: 8 }}>{trip.title}</h1>
          <p className="text-muted">{destinations}{trip.days ? ` · ${trip.days} days` : ""}{trip.travelers_adults ? ` · ${trip.travelers_adults} adult${trip.travelers_adults > 1 ? "s" : ""}` : ""}</p>
          {bd && (
            <p style={{ marginTop: 8, fontWeight: 600 }}>₹{bd.total_estimate?.toLocaleString("en-IN")} estimated · <span style={{ color: bd.status === "comfortable" ? "var(--green-500)" : bd.status === "tight" ? "var(--amber)" : "var(--red)" }}>{bd.status}</span></p>
          )}
        </div>

        {/* Itinerary */}
        {itinerary?.length > 0 && (
          <section style={{ marginBottom: 40 }}>
            <h2 style={{ marginBottom: 16 }}>Itinerary</h2>
            {itinerary.map((day: any) => (
              <div key={day.day_number} className="card" style={{ padding: 20, marginBottom: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
                  <div>
                    <strong>Day {day.day_number} — {day.theme || day.city}</strong>
                    <p className="text-sm text-muted">{day.summary}</p>
                  </div>
                  <span className="badge badge-muted">{day.activities?.length || 0} stops</span>
                </div>
                {(day.activities || []).map((act: any, i: number) => (
                  <div key={i} style={{ display: "flex", gap: 12, padding: "10px 0", borderTop: "1px solid var(--border)" }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: act.time_slot === "morning" ? "#f6ad55" : act.time_slot === "afternoon" ? "#63b3ed" : "#b794f4", flexShrink: 0, marginTop: 6 }} />
                    <div>
                      <strong className="text-sm">{act.place_name}</strong>
                      {act.cost_estimate > 0 && <span className="text-sm text-muted"> · ₹{act.cost_estimate?.toLocaleString("en-IN")}</span>}
                      <p className="text-sm text-muted">{act.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </section>
        )}

        {/* Hotels */}
        {hotels?.length > 0 && (
          <section style={{ marginBottom: 40 }}>
            <h2 style={{ marginBottom: 16 }}>Stays</h2>
            <div style={{ display: "grid", gap: 12 }}>
              {hotels.map((h: any, i: number) => (
                <div key={i} className="card" style={{ padding: 16, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <strong>{h.place_name}</strong>
                    <p className="text-sm text-muted">{h.city} · {h.nights} night{h.nights > 1 ? "s" : ""}</p>
                  </div>
                  {h.cost_per_night && <span style={{ fontWeight: 600, color: "var(--green-800)" }}>₹{h.cost_per_night?.toLocaleString("en-IN")}/night</span>}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Weather */}
        {weather?.length > 0 && (
          <section style={{ marginBottom: 40 }}>
            <h2 style={{ marginBottom: 16 }}>Weather</h2>
            <div className="card" style={{ padding: 16 }}>
              {weather.map((w: any, i: number) => (
                <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: i < weather.length - 1 ? "1px solid var(--border)" : "none" }}>
                  <strong className="text-sm">{w.city}</strong>
                  <span className="text-sm text-muted">{w.temp_min}–{w.temp_max}°C · {w.condition}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Disclaimer */}
        <p className="text-sm text-muted" style={{ marginBottom: 32 }}>{data.note}</p>

        {/* CTA */}
        <div className="card" style={{ padding: 28, textAlign: "center", background: "var(--green-50)" }}>
          <h3 style={{ marginBottom: 8 }}>Want to plan your own trip?</h3>
          <p className="text-muted" style={{ marginBottom: 16 }}>AI Travel Planner builds personalised itineraries through a simple conversation.</p>
          <Link href="/" className="btn btn-primary">Start planning for free →</Link>
        </div>
      </main>
    </div>
  );
}
