"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navbar from "@/components/Navbar";
import { trips as tripsApi, chat } from "@/lib/api";
import styles from "./page.module.css";

const SUGGESTED = [
  "I want to visit Rajasthan",
  "A relaxed food-focused trip",
  "Mid-November with my wife",
];

interface Trip {
  id: number;
  title: string;
  status: string;
  budget?: number;
  days?: number;
  thumbnail_url?: string;
  destinations: { city?: string; state?: string }[];
}

type TripFilter = "created" | "drafts" | "other" | "all";

const STATUS_LABELS: Record<string, string> = {
  created: "Created",
  creating: "Creating",
  draft: "Draft",
  done: "Done",
  generating: "Creating",
  failed: "Paused",
  collecting: "Draft",
  confirming: "Almost ready",
};

const TRIP_IMAGES = [
  "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=700&q=80",
  "https://images.unsplash.com/photo-1500375592092-40eb2168fd21?w=700&q=80",
  "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=700&q=80",
  "https://images.unsplash.com/photo-1518509562904-e7ef99cdcc86?w=700&q=80",
];
const PAGE_SIZE = 10;

function tripImage(trip: Trip, index: number) {
  if (trip.thumbnail_url) return trip.thumbnail_url;
  const destination = `${trip.title} ${trip.destinations.map((item) => `${item.city || ""} ${item.state || ""}`).join(" ")}`.toLowerCase();
  if (/beach|goa|island|coast|sea/.test(destination)) return TRIP_IMAGES[1];
  if (/hill|mountain|manali|shimla|kashmir|ladakh|ooty|coorg/.test(destination)) return TRIP_IMAGES[2];
  if (/udaipur|jaipur|rajasthan|agra|varanasi/.test(destination)) return TRIP_IMAGES[0];
  return TRIP_IMAGES[index % TRIP_IMAGES.length];
}

function TrashIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />
    </svg>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [myTrips, setMyTrips] = useState<Trip[]>([]);
  const [loading, setLoading] = useState(true);
  const [chatInput, setChatInput] = useState("");
  const [starting, setStarting] = useState(false);
  const [user, setUser] = useState<{ full_name?: string }>({});
  const [error, setError] = useState("");
  const [deletingTripId, setDeletingTripId] = useState<number | null>(null);
  const [pendingDelete, setPendingDelete] = useState<Trip | null>(null);
  // const [duplicatingTripId, setDuplicatingTripId] = useState<number | null>(null);
  const [tripFilter, setTripFilter] = useState<TripFilter>("all");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalTrips, setTotalTrips] = useState(0);
  const [tripCounts, setTripCounts] = useState({ all: 0, created: 0, drafts: 0, other: 0 });
  const [pageCount, setPageCount] = useState(1);

  useEffect(() => {
    document.title = "My Trips — AI Travel Planner";
  }, []);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      try {
        setUser(JSON.parse(localStorage.getItem("user") || "{}"));
      } catch {
        setUser({});
      }
      if (!localStorage.getItem("token")) {
        router.replace("/login");
        return;
      }
      setLoading(true);
      tripsApi.list(currentPage, PAGE_SIZE, tripFilter)
        .then((response) => {
          setMyTrips(response.data.items);
          setTotalTrips(response.data.counts.all);
          setTripCounts(response.data.counts);
          setPageCount(response.data.total_pages);
        })
        .catch(() => setError("We couldn’t load your trips. Please refresh and try again."))
        .finally(() => setLoading(false));
    });
    return () => window.cancelAnimationFrame(frame);
  }, [router, currentPage, tripFilter]);

  async function startConversation(message: string) {
    const trimmedMessage = message.trim();
    if (!trimmedMessage || starting) return;
    setStarting(true);
    setError("");
    try {
      const response = await chat.send(trimmedMessage);
      router.push(`/chat/${response.data.trip_id}`);
    } catch {
      setError("We couldn’t start your conversation. Please try again.");
      setStarting(false);
    }
  }

  async function deleteTrip(trip: Trip) {
    if (deletingTripId !== null) return;
    setPendingDelete(trip);
  }

  // async function duplicateTrip(trip: Trip) {
  //   if (duplicatingTripId !== null) return;
  //   setDuplicatingTripId(trip.id);
  //   try {
  //     await tripsApi.duplicate(trip.id);
  //     const res = await tripsApi.list(currentPage, PAGE_SIZE, tripFilter);
  //     setMyTrips(res.data.items);
  //     setTotalTrips(res.data.counts.all);
  //     setTripCounts(res.data.counts);
  //     setPageCount(res.data.total_pages);
  //   } catch {
  //     setError("Could not duplicate trip. Please try again.");
  //   } finally {
  //     setDuplicatingTripId(null);
  //   }
  // }

  async function confirmDelete() {
    if (!pendingDelete || deletingTripId !== null) return;
    const trip = pendingDelete;
    setDeletingTripId(trip.id);
    setError("");
    try {
      await tripsApi.delete(trip.id);
      const response = await tripsApi.list(currentPage, PAGE_SIZE, tripFilter);
      const targetPage = Math.min(currentPage, response.data.total_pages);
      const refreshed = targetPage === currentPage
        ? response
        : await tripsApi.list(targetPage, PAGE_SIZE, tripFilter);
      setCurrentPage(targetPage);
      setMyTrips(refreshed.data.items);
      setTotalTrips(refreshed.data.counts.all);
      setTripCounts(refreshed.data.counts);
      setPageCount(refreshed.data.total_pages);
      setPendingDelete(null);
    } catch {
      setError("We couldn’t delete that trip. Please try again.");
    } finally {
      setDeletingTripId(null);
    }
  }

  function renderTripSection(title: string, sectionTrips: Trip[], emptyMessage: string, totalCount: number) {
    return (
      <section className={styles.tripGroup}>
        <div className={styles.groupHeader}>
          <h3>{title}</h3>
          <span>{totalCount}</span>
        </div>
        {sectionTrips.length === 0 ? (
          <div className={styles.groupEmpty}>{emptyMessage}</div>
        ) : (
          <div className={styles.tripsGrid}>
            {sectionTrips.map((trip, index) => {
              const destination = trip.destinations.map((item) => item.city || item.state).filter(Boolean).join(" → ");
              const isCreated = trip.status === "created" || trip.status === "done";
              const statusClass = styles[`status_${trip.status}`] || styles.status_default;
              return (
                <article key={trip.id} className={styles.tripCard}>
                  <Link href={isCreated ? `/trips/${trip.id}` : `/chat/${trip.id}`} className={styles.tripCardLink}>
                    <div className={styles.tripCardImage} style={{ backgroundImage: `url("${tripImage(trip, index)}")` }}>
                      <span className={`${styles.statusBadge} ${statusClass}`}>{STATUS_LABELS[trip.status] || trip.status}</span>
                    </div>
                    <div className={styles.tripCardBody}>
                      <h4>{trip.title}</h4>
                      <p className={styles.tripDescription}>
                        {destination || "Your trip is taking shape"}
                        {trip.days ? ` · ${trip.days} days` : ""}
                      </p>
                      <p className={styles.tripBudget}>
                        {trip.budget ? `₹${trip.budget.toLocaleString("en-IN")} · Estimated total` : trip.status === "failed" ? "Plan paused · Resume when you’re ready" : "Personalized around your ideas"}
                      </p>
                      <div className={styles.tripCardFooter}>
                        <span>{isCreated ? "Open itinerary →" : "Resume conversation →"}</span>
                        <button
                          type="button"
                          className={styles.deleteButton}
                          onClick={(e) => { e.preventDefault(); deleteTrip(trip); }}
                          disabled={deletingTripId === trip.id}
                          aria-label={`Delete ${trip.title}`}
                          title="Delete trip"
                        >
                          {deletingTripId === trip.id ? <span className={styles.deleteSpinner} /> : <TrashIcon />}
                        </button>
                      </div>
                    </div>
                  </Link>
                  {/* <button
                    type="button"
                    className={styles.deleteButton}
                    onClick={() => duplicateTrip(trip)}
                    disabled={duplicatingTripId === trip.id}
                    aria-label={`Duplicate ${trip.title}`}
                    title="Duplicate trip"
                    style={{ bottom: 48 }}
                  >
                    {duplicatingTripId === trip.id ? <span className={styles.deleteSpinner} /> : <span style={{ fontSize: 14 }}>⧉</span>}
                  </button> */}
                </article>
              );
            })}
          </div>
        )}
      </section>
    );
  }

  const firstName = user.full_name?.split(" ")[0] || "there";

  return (
    <>
      <Navbar />
      <main className={styles.main}>
        <div className={`container ${styles.content}`}>
          <section className={styles.heroSection}>
            <div className={styles.heroHeading}>
              <div>
                <p className={styles.journalLabel}>YOUR TRAVEL JOURNAL</p>
                <h1 className="font-display">Where will your next chapter take you?</h1>
                <p className={styles.welcome}>Welcome back, {firstName}. A good trip starts with a little curiosity.</p>
              </div>
              <Link href="/chat" className={`btn btn-primary ${styles.newConversation}`}>+ New conversation</Link>
            </div>

            <div className={styles.heroFeature}>
              <div className={styles.chatCard}>
                <p className={styles.chatLabel}>START A CONVERSATION</p>
                <h2>Tell us about your trip in your own words.</h2>
                <p className={styles.chatSub}>No forms, no dropdowns — just a conversation that builds your trip one follow-up at a time.</p>
                <form
                  onSubmit={(event) => { event.preventDefault(); startConversation(chatInput); }}
                  className={styles.chatForm}
                >
                  <input
                    className={`input ${styles.chatInput}`}
                    placeholder="Type your next thought..."
                    value={chatInput}
                    onChange={(event) => setChatInput(event.target.value)}
                    aria-label="Describe your trip"
                    disabled={starting}
                  />
                  <button className="btn btn-primary" type="submit" disabled={starting || !chatInput.trim()}>
                    {starting ? <span className="spinner" /> : <>✈&nbsp; Start conversation</>}
                  </button>
                </form>
                <div className={styles.suggestions}>
                  {SUGGESTED.map((suggestion) => (
                    <button
                      key={suggestion}
                      className={styles.suggestionChip}
                      onClick={() => startConversation(suggestion)}
                      disabled={starting}
                    >
                      {suggestion}
                    </button>
                  ))}
                </div>
                {error && <p className={styles.errorMessage} role="alert">{error}</p>}
              </div>
              <div className={styles.heroImage} role="img" aria-label="Jaipur city and Hawa Mahal" />
            </div>
          </section>

          <section className={styles.tripsSection}>
            <div className={styles.tripsHeader}>
              <div className={styles.tripsTitle}>
                <h2>My trips</h2>
                {!loading && <span className={styles.savedCount}>{totalTrips} saved</span>}
              </div>
              <span className={styles.updatedLabel}>{totalTrips > 0 ? `${totalTrips} trips · Last updated recently` : ""}</span>
            </div>

            {loading ? (
              <div className={styles.tripsGrid} aria-label="Loading trips">
                {[0, 1, 2, 3].map((index) => <div key={index} className={styles.skeleton} />)}
              </div>
            ) : totalTrips === 0 ? (
              <div className={styles.emptyState}>
                <span aria-hidden="true">✈</span>
                <p>Your travel journal is ready. Start a conversation to plan your first trip.</p>
              </div>
            ) : (
              <>
                <div className={styles.filterBar} role="tablist" aria-label="Filter trips by status">
                  {([
                    ["all", "All trips", tripCounts.all],
                    ["created", "Created", tripCounts.created],
                    ["drafts", "Drafts", tripCounts.drafts],
                    ["other", "Other statuses", tripCounts.other],
                  ] as [TripFilter, string, number][]).map(([value, label, count]) => (
                    <button
                      key={value}
                      type="button"
                      role="tab"
                      aria-selected={tripFilter === value}
                      className={`${styles.filterButton} ${tripFilter === value ? styles.filterButtonActive : ""}`}
                      onClick={() => { setTripFilter(value); setCurrentPage(1); }}
                    >
                      {label} <span>{count}</span>
                    </button>
                  ))}
                </div>
                {tripFilter === "all" ? (
                  <>{renderTripSection("All trips", myTrips, "No trips saved yet.", tripCounts.all)}</>
                ) : (
                  renderTripSection(
                    tripFilter === "created" ? "Created trips" : tripFilter === "drafts" ? "Drafts" : "Other statuses",
                    myTrips,
                    tripFilter === "created" ? "Your completed itineraries will appear here." : tripFilter === "drafts" ? "Draft conversations will appear here." : "Trips being created or paused will appear here.",
                    tripFilter === "created" ? tripCounts.created : tripFilter === "drafts" ? tripCounts.drafts : tripCounts.other,
                  )
                )}
                {pageCount > 1 && (
                  <nav className={styles.pagination} aria-label="Trip pages">
                    <button type="button" onClick={() => setCurrentPage((page) => Math.max(1, page - 1))} disabled={currentPage === 1}>← Previous</button>
                    {Array.from({ length: pageCount }, (_, index) => index + 1).map((page) => (
                      <button key={page} type="button" className={currentPage === page ? styles.pageActive : ""} onClick={() => setCurrentPage(page)} aria-current={currentPage === page ? "page" : undefined}>{page}</button>
                    ))}
                    <button type="button" onClick={() => setCurrentPage((page) => Math.min(pageCount, page + 1))} disabled={currentPage === pageCount}>Next →</button>
                  </nav>
                )}
              </>
            )}
            {error && !loading && <p className={styles.errorMessage} role="alert">{error}</p>}

            <div className={styles.notSureRow}>
              <div className={styles.notSureCard}>
                <div className={styles.notSureIcon} aria-hidden="true">◎</div>
                <div>
                  <h3>Not sure where to go?</h3>
                  <p>Start with your budget and interests. I’ll suggest 1–3 destinations that fit.</p>
                  <button
                    className={styles.suggestLink}
                    onClick={() => startConversation("I’m not sure where to go. Can you suggest a few destinations based on my budget and interests?")}
                    disabled={starting}
                  >
                    Suggest destinations for me →
                  </button>
                </div>
              </div>
              <div className={styles.tipCard}>
                <p className={styles.tipLabel}>TRIP MENU · A LITTLE STRUCTURE</p>
                <p>Every plan is a draft you can shape. Pick up a conversation, or start somewhere new.</p>
                <Link href="/chat">Start a new conversation →</Link>
              </div>
            </div>
          </section>

          <p className={styles.disclaimer}>
            Planning guides, places, routes, costs and ideas included here are not live or verified by vendors. Check current details with official providers before booking. No booking or payment happens here.
          </p>
        </div>

        {pendingDelete && (
          <div className={styles.modalBackdrop} role="presentation" onMouseDown={() => deletingTripId === null && setPendingDelete(null)}>
            <div
              className={styles.confirmModal}
              role="dialog"
              aria-modal="true"
              aria-labelledby="delete-trip-title"
              onMouseDown={(event) => event.stopPropagation()}
            >
              <h2 id="delete-trip-title">Delete this trip?</h2>
              <p>“{pendingDelete.title}” will be permanently deleted along with its itinerary and conversation.</p>
              <div className={styles.modalActions}>
                <button type="button" className={styles.cancelButton} onClick={() => setPendingDelete(null)} disabled={deletingTripId !== null}>Cancel</button>
                <button type="button" className={styles.confirmDeleteButton} onClick={confirmDelete} disabled={deletingTripId !== null}>
                  {deletingTripId !== null ? "Deleting…" : "Delete trip"}
                </button>
              </div>
            </div>
          </div>
        )}

        <footer className={styles.footer}>
          <div className={`container ${styles.footerInner}`}>
            <span>AI Travel Planner · A little structure. A lot to discover.</span>
            <div><a href="#">Privacy</a><a href="#">Help</a><a href="#">Estimates, not guarantees</a></div>
          </div>
        </footer>
      </main>
    </>
  );
}
