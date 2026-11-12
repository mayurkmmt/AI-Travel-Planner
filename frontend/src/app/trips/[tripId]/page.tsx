"use client";
import { Suspense, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import toast from "react-hot-toast";
import Navbar from "@/components/Navbar";
import { trips as tripsApi } from "@/lib/api";
import type { Trip, ItineraryDay, Hotel, Restaurant, BudgetBreakdown, WeatherSnapshot, PackingList } from "@/lib/types";
import styles from "./page.module.css";

type Tab = "itinerary" | "stays" | "budget" | "essentials";

interface EditForm {
  budget: string;
  days: string;
  travelers_adults: string;
  travel_style: string;
  pace: string;
  transport_mode: string;
  special_requests: string;
}

function TripWorkspaceContent() {
  const params = useParams();
  const router = useRouter();
  const tripId = Number(params.tripId);
  const [tab, setTab] = useState<Tab>("itinerary");
  const [trip, setTrip] = useState<Trip | null>(null);
  const [itinerary, setItinerary] = useState<{ days: ItineraryDay[] } | null>(null);
  const [hotels, setHotels] = useState<{ hotels: Hotel[] } | null>(null);
  const [restaurants, setRestaurants] = useState<{ restaurants: Restaurant[] } | null>(null);
  const [budget, setBudget] = useState<{ budget_breakdown: BudgetBreakdown } | null>(null);
  const [packing, setPacking] = useState<{ packing_list: PackingList } | null>(null);
  const [weather, setWeather] = useState<WeatherSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedDay, setSelectedDay] = useState<number | null>(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editForm, setEditForm] = useState<EditForm>({
    budget: "", days: "", travelers_adults: "", travel_style: "", pace: "", transport_mode: "", special_requests: "",
  });
  const [regenerating, setRegenerating] = useState(false);

  async function fetchAllData() {
    return Promise.allSettled([
      tripsApi.get(tripId), tripsApi.itinerary(tripId), tripsApi.hotels(tripId),
      tripsApi.restaurants(tripId), tripsApi.budget(tripId), tripsApi.packingList(tripId), tripsApi.weather(tripId),
    ]).then(([t, it, h, r, b, pl, w]) => {
      if (t.status !== "fulfilled") { setTrip(null); return; }
      const tripData = t.value.data as Trip;
      setTrip(tripData);
      document.title = `${tripData.title} — AI Travel Planner`;
      setEditForm({
        budget: tripData.budget ? String(tripData.budget) : "",
        days: tripData.days ? String(tripData.days) : "",
        travelers_adults: tripData.travelers_adults ? String(tripData.travelers_adults) : "",
        travel_style: tripData.travel_style || "",
        pace: tripData.pace || "",
        transport_mode: (tripData.transport_modes || [])[0] || "",
        special_requests: tripData.special_requests || "",
      });
      if (it.status === "fulfilled") setItinerary(it.value.data);
      if (h.status === "fulfilled") setHotels(h.value.data);
      if (r.status === "fulfilled") setRestaurants(r.value.data);
      if (b.status === "fulfilled") setBudget(b.value.data);
      if (pl.status === "fulfilled") setPacking(pl.value.data);
      if (w.status === "fulfilled") setWeather(w.value.data?.weather || []);
    });
  }

  useEffect(() => {
    if (!localStorage.getItem("token")) { router.push("/login"); return; }
    fetchAllData().finally(() => setLoading(false));
  }, [tripId, router]);

  async function handleShare() {
    try {
      const res = await tripsApi.share(tripId);
      const url = `${window.location.origin}/shared/${res.data.token}`;
      await navigator.clipboard.writeText(url);
      toast.success("Share link copied to clipboard!");
    } catch {
      toast.error("Could not generate share link. Please try again.");
    }
  }

  async function handleRegenerate() {
    setRegenerating(true);
    try {
      const p: Record<string, unknown> = {};
      if (editForm.budget) p.budget = Number(editForm.budget);
      if (editForm.days) p.days = Number(editForm.days);
      if (editForm.travelers_adults) p.travelers_adults = Number(editForm.travelers_adults);
      if (editForm.travel_style) p.travel_style = editForm.travel_style;
      if (editForm.pace) p.pace = editForm.pace;
      if (editForm.transport_mode) p.transport_mode = editForm.transport_mode;
      if (editForm.special_requests) p.special_requests = editForm.special_requests;
      await tripsApi.regenerate(tripId, p);
      setShowEditModal(false);
      toast("Rebuilding your plan — this takes 20–40 seconds…", { icon: "⏳", duration: 40000 });
      const poll = window.setInterval(async () => {
        try {
          const { data } = await tripsApi.status(tripId);
          if (data.status === "created" || data.status === "done") {
            window.clearInterval(poll);
            toast.dismiss();
            await fetchAllData();
            toast.success("Your plan has been updated!");
            setRegenerating(false);
          } else if (data.status === "failed") {
            window.clearInterval(poll);
            toast.dismiss();
            toast.error("Plan regeneration failed. Please try again.");
            setRegenerating(false);
          }
        } catch { /* keep polling */ }
      }, 4000);
    } catch {
      toast.error("Could not start regeneration. Please try again.");
      setRegenerating(false);
    }
  }

  function handleDayClick(event: React.MouseEvent<HTMLAnchorElement>, dayNumber: number) {
    event.preventDefault();
    setSelectedDay(dayNumber);
    const target = document.getElementById(`day-${dayNumber}`);
    const header = document.getElementById("trip-header");
    if (!target) return;
    const headerBottom = header?.getBoundingClientRect().bottom || 0;
    const targetTop = target.getBoundingClientRect().top + window.scrollY - headerBottom - 16;
    window.history.replaceState(null, "", `#day-${dayNumber}`);
    window.scrollTo({ top: Math.max(0, targetTop), behavior: "smooth" });
  }

  if (loading) return (
    <>
      <Navbar />
      <div style={{ padding: "32px var(--page-gutter)" }}>
        <div className={styles.skeletonTitle} />
        <div className={styles.skeletonMeta} />
        {[1, 2, 3].map((i) => <div key={i} className={styles.skeletonCard} />)}
      </div>
    </>
  );
  if (!trip) return <><Navbar /><p style={{ padding: 48 }}>Trip not found.</p></>;

  const destinations = (trip.destinations || []).map((d) => d.city || d.state).filter(Boolean).join(" → ");
  const days = itinerary?.days || [];
  const hotelList = hotels?.hotels || [];
  const restaurantList = restaurants?.restaurants || [];
  const bd = budget?.budget_breakdown;
  const packingItems: PackingList = packing?.packing_list || {};
  const budgetPercent = bd ? Math.round((bd.total_estimate / (trip.budget || 1)) * 100) : 0;
  const bdColor = bd?.status === "comfortable" ? "var(--green-500)" : bd?.status === "tight" ? "var(--amber)" : "var(--red)";

  return (
    <>
      <Navbar />
      <main className={styles.main}>
        {/* HEADER */}
        <div id="trip-header" className={styles.tripHeader}>
          <div className={`container ${styles.pageContainer}`}>
            <Link href="/dashboard" style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "0.85rem", color: "var(--text-sub)", padding: "12px 0", marginBottom: 4 }}>
              ← My trips
            </Link>
            <div className={styles.tripHeaderInner}>
              <div>
                <p className={styles.breadcrumb}>
                  <Link href="/dashboard">My trips</Link> · {destinations || trip.title}
                </p>
                <h1 className={`font-display ${styles.tripTitle}`}>{trip.title}</h1>
                <div className={styles.tripMeta}>
                  <span>{destinations}</span>
                  {trip.days && <span>· {trip.days} days</span>}
                  {trip.travelers_adults && <span>· {trip.travelers_adults} adult{trip.travelers_adults > 1 ? "s" : ""}</span>}
                  {trip.travel_style && <span className="badge badge-muted">{trip.travel_style}</span>}
                </div>
              </div>
              <div className={styles.tripActions}>
                <button className="btn btn-primary btn-sm" onClick={() => setShowEditModal(true)}>✎ Edit plan</button>
                <button className="btn btn-ghost btn-sm" onClick={handleShare}>↗ Share trip</button>
              </div>
            </div>
            {bd && (
              <div className={styles.budgetBanner}>
                <span className="badge" style={{ background: bd.status === "comfortable" ? "var(--green-100)" : bd.status === "tight" ? "var(--amber-bg)" : "var(--red-bg)", color: bdColor }}>
                  {bd.status === "comfortable" ? "✓ Comfortable" : bd.status === "tight" ? "⚠ Tight" : "✗ Unrealistic"} · {budgetPercent}% of budget
                </span>
                <span className={styles.budgetEst}>₹{bd.total_estimate?.toLocaleString("en-IN")} est.</span>
                {weather.length > 0 && <span className="text-sm text-muted">🌤 {weather[0]?.condition} · {weather[0]?.advice}</span>}
              </div>
            )}
            <div className={styles.tabs}>
              {(["itinerary", "stays", "budget", "essentials"] as Tab[]).map((t) => (
                <button key={t} className={`${styles.tab} ${tab === t ? styles.active : ""}`} onClick={() => setTab(t)}>
                  {t === "itinerary" ? "Itinerary" : t === "stays" ? "Stays & dining" : t === "budget" ? "Budget & transport" : "Travel essentials"}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className={`container ${styles.pageContainer}`}>
          <div className={styles.content}>
            {/* ITINERARY */}
            {tab === "itinerary" && (
              <div className={styles.itineraryGrid}>
                <div className={styles.dayNav}>
                  {days.map((d) => (
                    <a key={d.day_number} href={`#day-${d.day_number}`}
                      className={`${styles.dayNavItem} ${selectedDay === d.day_number ? styles.dayNavItemSelected : ""}`}
                      onClick={(e) => handleDayClick(e, d.day_number)}>
                      <span className={styles.dayNum}>Day {d.day_number}</span>
                      <span className="text-xs text-muted">{d.city}</span>
                    </a>
                  ))}
                </div>
                <div className={styles.itineraryDays}>
                  {days.map((day) => (
                    <section key={day.day_number} id={`day-${day.day_number}`} className={`card ${styles.dayCard} animate-fade`}>
                      <div className={styles.dayCardHeader}>
                        <div>
                          <span className={styles.dayLabel}>Day {day.day_number} / {day.theme || day.city}</span>
                          <p className="text-sm text-muted">{day.summary}</p>
                        </div>
                        <span className="badge badge-muted">{day.activities?.length || 0} stops</span>
                      </div>
                      {(day.activities || []).map((act, i) => (
                        <div key={i} className={styles.activity}>
                          <div className={styles.activityTime}>
                            <span className={styles.timeDot} style={{ background: act.time_slot === "morning" ? "#f6ad55" : act.time_slot === "afternoon" ? "#63b3ed" : "#b794f4" }} />
                            <span className="text-xs text-muted">{act.start_time || act.time_slot}</span>
                          </div>
                          <div className={styles.activityBody}>
                            <div className={styles.activityHeader}>
                              <strong>{act.place_name}</strong>
                              {act.cost_estimate > 0 && <span className="text-sm text-muted">₹{act.cost_estimate.toLocaleString("en-IN")}</span>}
                            </div>
                            <p className="text-sm text-muted">{act.description}</p>
                            {act.tips && <p className={styles.tip}>💡 {act.tips}</p>}
                            {act.travel_minutes_to_next > 0 && <p className={styles.travelTime}>↕ {act.travel_minutes_to_next} min to next stop</p>}
                          </div>
                        </div>
                      ))}
                    </section>
                  ))}
                </div>
              </div>
            )}

            {/* STAYS */}
            {tab === "stays" && (
              <div className={styles.staysSection}>
                <div>
                  <div className={styles.sectionHeading}>
                    <div><p className={styles.sidebarLabel}>GOOD PLACES TO PAUSE</p><h2>Stays</h2></div>
                    <span className="badge badge-muted">{hotelList.length} options</span>
                  </div>
                  <div className={styles.staysGrid}>
                    {hotelList.length === 0 ? <p className="text-muted">No accommodation data yet.</p> : hotelList.map((h, i) => (
                      <div key={i} className={`card ${styles.hotelCard} animate-fade`}>
                        <div className={styles.hotelImage} />
                        <div className={styles.hotelBody}>
                          <h3>{h.place_name}</h3>
                          <p className="text-sm text-muted">{h.city} · {h.nights} night{h.nights > 1 ? "s" : ""}</p>
                          <div className={styles.hotelMeta}>
                            {h.cost_per_night && <span className={styles.price}>₹{h.cost_per_night?.toLocaleString("en-IN")}/night</span>}
                            {h.place_type && <span className="badge badge-muted">{h.place_type}</span>}
                          </div>
                          {h.notes && <p className="text-sm text-muted">{h.notes}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                <div className={styles.diningSection}>
                  <div className={styles.sectionHeading}><div><p className={styles.sidebarLabel}>LOCAL TABLE</p><h2>Dining suggestions</h2></div><span className="badge badge-muted">{restaurantList.length} picks</span></div>
                  <div className={styles.diningGrid}>
                    {restaurantList.length === 0 ? <p className="text-muted">No dining data yet.</p> : restaurantList.map((r, i) => (
                      <article key={i} className={`card ${styles.diningCard}`}>
                        <div><span className={styles.mealLabel}>{r.meal_type || "meal"}</span><h3>{r.place_name}</h3><p className="text-sm text-muted">{r.city}{r.cuisine ? ` · ${r.cuisine}` : ""}{r.day_number ? ` · Day ${r.day_number}` : ""}</p></div>
                        {r.cost_estimate > 0 && <strong>₹{r.cost_estimate.toLocaleString("en-IN")}</strong>}
                        {r.notes && <p className="text-sm text-muted">{r.notes}</p>}
                      </article>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* BUDGET */}
            {tab === "budget" && (
              <div className={styles.budgetSection}>
                {bd ? (
                  <>
                    <div className={styles.budgetStats}>
                      {[
                        { label: "Total budget", value: `₹${trip.budget?.toLocaleString("en-IN")}` },
                        { label: "Estimated cost", value: `₹${bd.total_estimate?.toLocaleString("en-IN")}` },
                        { label: "Remaining buffer", value: `₹${((trip.budget ?? 0) - bd.total_estimate).toLocaleString("en-IN")}` },
                        { label: "Est. per person", value: `₹${Math.round(bd.total_estimate / (trip.travelers_adults || 1)).toLocaleString("en-IN")}` },
                      ].map((s) => (
                        <div key={s.label} className={`card ${styles.statCard}`}>
                          <p className="text-xs text-muted">{s.label}</p>
                          <p className={styles.statValue}>{s.value}</p>
                        </div>
                      ))}
                    </div>
                    <div className={`card ${styles.budgetCard}`}>
                      <h3>Where the budget goes</h3>
                      <div className={styles.budgetBar}>
                        {(["stay", "food", "transport", "activities", "buffer"] as (keyof BudgetBreakdown)[]).map((key, idx) => {
                          const colors = ["#1B4332", "#38a169", "#276749", "#68d391", "#c6f6d5"];
                          const val = typeof bd[key] === "number" ? (bd[key] as number) : 0;
                          return <div key={key} style={{ flex: val || 0, background: colors[idx], height: "100%" }} title={key} />;
                        })}
                      </div>
                      <table className={styles.budgetTable}>
                        <thead><tr><th>Category</th><th>Amount</th></tr></thead>
                        <tbody>
                          {(["stay", "food", "transport", "activities", "buffer"] as (keyof BudgetBreakdown)[]).map((k) => (
                            <tr key={k}><td style={{ textTransform: "capitalize" }}>{k}</td><td>₹{(bd[k] as number)?.toLocaleString("en-IN")}</td></tr>
                          ))}
                          <tr className={styles.totalRow}><td><strong>Total estimate</strong></td><td><strong>₹{bd.total_estimate?.toLocaleString("en-IN")}</strong></td></tr>
                        </tbody>
                      </table>
                    </div>
                  </>
                ) : <p className="text-muted">Budget breakdown not available yet.</p>}
              </div>
            )}

            {/* ESSENTIALS */}
            {tab === "essentials" && (
              <div className={styles.essentialsGrid}>
                {Object.entries(packingItems).map(([category, items]) => (
                  <div key={category} className={`card ${styles.packCard} animate-fade`}>
                    <h3 style={{ textTransform: "capitalize", marginBottom: 12 }}>{category}</h3>
                    <ul className={styles.packList}>
                      {(items as string[]).map((item, i) => (
                        <li key={i} className={styles.packItem}><span className={styles.packCheck}>□</span>{item}</li>
                      ))}
                    </ul>
                  </div>
                ))}
                {Object.keys(packingItems).length === 0 && <p className="text-muted">Packing list not available yet.</p>}
              </div>
            )}

            {/* SIDEBAR */}
            <aside className={styles.chatSidebar}>
              {weather.length > 0 && (
                <div className={`card ${styles.weatherCard}`}>
                  <h4 style={{ marginBottom: 12 }}>Weather</h4>
                  {weather.map((w, i) => (
                    <div key={i} className={styles.weatherRow}>
                      <strong className="text-sm">{w.city}</strong>
                      <span className="text-sm text-muted">{w.temp_min}–{w.temp_max}°C · {w.condition}</span>
                    </div>
                  ))}
                </div>
              )}
            </aside>
          </div>
        </div>
      </main>

      {/* EDIT MODAL */}
      {showEditModal && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
          <div className="card" style={{ width: "100%", maxWidth: 480, padding: 32, position: "relative", maxHeight: "90vh", overflowY: "auto" }}>
            <button onClick={() => setShowEditModal(false)} style={{ position: "absolute", top: 16, right: 16, background: "none", border: "none", fontSize: 20, cursor: "pointer", color: "var(--text-muted)" }}>✕</button>
            <h2 style={{ marginBottom: 4 }}>Edit trip plan</h2>
            <p className="text-sm text-muted" style={{ marginBottom: 24 }}>Change any detail and regenerate — AI will rebuild the full plan to match.</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <span className="text-xs text-muted">BUDGET (₹)</span>
                  <input className="input" type="number" value={editForm.budget} onChange={e => setEditForm(f => ({ ...f, budget: e.target.value }))} placeholder="e.g. 50000" />
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <span className="text-xs text-muted">DAYS</span>
                  <input className="input" type="number" value={editForm.days} onChange={e => setEditForm(f => ({ ...f, days: e.target.value }))} placeholder="e.g. 5" />
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <span className="text-xs text-muted">ADULTS</span>
                  <input className="input" type="number" value={editForm.travelers_adults} onChange={e => setEditForm(f => ({ ...f, travelers_adults: e.target.value }))} placeholder="e.g. 2" />
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <span className="text-xs text-muted">TRAVEL STYLE</span>
                  <select className="input" value={editForm.travel_style} onChange={e => setEditForm(f => ({ ...f, travel_style: e.target.value }))}>
                    <option value="">Keep current</option>
                    <option value="budget">Budget</option>
                    <option value="mid_range">Mid-range</option>
                    <option value="luxury">Luxury</option>
                  </select>
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <span className="text-xs text-muted">PACE</span>
                  <select className="input" value={editForm.pace} onChange={e => setEditForm(f => ({ ...f, pace: e.target.value }))}>
                    <option value="">Keep current</option>
                    <option value="relaxed">Relaxed</option>
                    <option value="moderate">Moderate</option>
                    <option value="packed">Packed</option>
                  </select>
                </label>
                <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                  <span className="text-xs text-muted">TRANSPORT</span>
                  <select className="input" value={editForm.transport_mode} onChange={e => setEditForm(f => ({ ...f, transport_mode: e.target.value }))}>
                    <option value="">Keep current</option>
                    <option value="flight">Flight</option>
                    <option value="train">Train</option>
                    <option value="bus">Bus</option>
                    <option value="car">Car</option>
                  </select>
                </label>
              </div>
              <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                <span className="text-xs text-muted">SPECIAL REQUESTS</span>
                <input className="input" value={editForm.special_requests} onChange={e => setEditForm(f => ({ ...f, special_requests: e.target.value }))} placeholder="e.g. avoid crowded places, include a beach day" />
              </label>
            </div>
            <div style={{ display: "flex", gap: 12, marginTop: 24 }}>
              <button className="btn btn-primary" style={{ flex: 1 }} onClick={handleRegenerate} disabled={regenerating}>
                {regenerating ? <><span className="spinner" style={{ marginRight: 8 }} />Regenerating…</> : "Regenerate full plan"}
              </button>
              <button className="btn btn-ghost" onClick={() => setShowEditModal(false)} disabled={regenerating}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default function TripWorkspacePage() {
  return (
    <Suspense fallback={<div style={{ padding: 48, textAlign: "center" }}><span className="spinner" /></div>}>
      <TripWorkspaceContent />
    </Suspense>
  );
}
