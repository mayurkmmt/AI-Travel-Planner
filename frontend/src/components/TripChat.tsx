"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import Navbar from "@/components/Navbar";
import { chat as chatApi, trips as tripsApi } from "@/lib/api";
import styles from "./TripChat.module.css";

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  message_type: string;
}

interface ChatReply {
  agent_reply: Message;
  trip_id: number;
  slot_state: Record<string, unknown>;
  status: string;
}

const DIET_OPTIONS = ["Vegetarian", "Vegan", "Any"];

const GREETING: Message = {
  id: 0,
  role: "assistant",
  content: "Hi! Where would you like to go? You can name a country, state, or city.",
  message_type: "text",
};

function formatValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join(", ");
  if (typeof value === "object" && value !== null) {
    return Object.values(value as Record<string, unknown>).map(String).join(", ");
  }
  return String(value);
}

function formatBudget(value: unknown): string {
  const amount = Number(value);
  return Number.isFinite(amount)
    ? `₹${amount.toLocaleString("en-IN")}`
    : formatValue(value);
}

function isValidDestination(value: unknown): boolean {
  if (typeof value !== "string" || !value.trim()) return false;
  const normalized = value.trim().toLowerCase().replace(/\s+/g, " ");
  return !/^(?:hi|hello|hey|greetings|i want to plan.*|plan a trip.*|help me plan.*|travel planner.*|(?:p\s*=\s*)?my trip)$/.test(normalized);
}

export default function TripChat() {
  const params = useParams();
  const router = useRouter();
  const tripIdFromRoute = params?.tripId ? Number(params.tripId) : undefined;
  const [messages, setMessages] = useState<Message[]>(tripIdFromRoute ? [] : [GREETING]);
  const [input, setInput] = useState("");
  const autoSentRef = useRef(false);
  const [sending, setSending] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(Boolean(tripIdFromRoute));
  const [status, setStatus] = useState("draft");
  const [slotState, setSlotState] = useState<Record<string, unknown>>({});
  const [firstName, setFirstName] = useState("there");
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [currentTripId, setCurrentTripId] = useState<number | undefined>(tripIdFromRoute);
  const hasLoadedInitialHistory = useRef(false);

  const searchParams = useSearchParams();
  const autoQuery = searchParams.get("q") || "";

  // Auto-send the ?q= param as the first message once auth is confirmed
  useEffect(() => {
    if (tripIdFromRoute || autoSentRef.current || !autoQuery) return;
    if (!localStorage.getItem("token")) return;
    autoSentRef.current = true;
    const t = window.setTimeout(() => {
      sendMessage(autoQuery);
    }, 300);
    return () => window.clearTimeout(t);
  // sendMessage is stable within a render cycle; autoQuery won't change
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoQuery, tripIdFromRoute]);

  useEffect(() => {
    if (!localStorage.getItem("token")) {
      router.replace("/login");
      return;
    }

    const frame = window.requestAnimationFrame(() => {
      try {
        const user = JSON.parse(localStorage.getItem("user") || "{}");
        setFirstName(user.full_name?.trim().split(/\s+/)[0] || "there");
      } catch {
        setFirstName("there");
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [router]);

  useEffect(() => {
    if (!localStorage.getItem("token") || !tripIdFromRoute || hasLoadedInitialHistory.current) return;

    chatApi.history(tripIdFromRoute).then(({ data }) => {
      setMessages(data.messages || []);
      setStatus(data.trip_status || "draft");
      setSlotState(data.slot_state || {});
      setError("");
    }).catch(() => {
      setError("We couldn’t load this conversation. Please refresh and try again.");
    }).finally(() => setLoadingHistory(false));
    hasLoadedInitialHistory.current = true;
  }, [tripIdFromRoute]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending]);

  // Generation runs in the worker after the confirmation response. Keep the
  // conversation in sync with the persisted trip instead of waiting forever
  // on the immediate "creating" response.
  useEffect(() => {
    const tripId = currentTripId || tripIdFromRoute;
    if (!tripId || (status !== "creating" && status !== "generating")) return;

    let attempts = 0;
    const poll = window.setInterval(async () => {
      attempts += 1;
      try {
        // Generation status does not require the full trip payload. Polling
        // the full endpoint repeatedly caused unnecessary DB work while the
        // worker was still preparing the plan.
        const { data } = await tripsApi.status(tripId);
        const nextStatus = data.status as string;
        setStatus((currentStatus) => currentStatus === nextStatus ? currentStatus : nextStatus);
        if (nextStatus === "created" || nextStatus === "done") {
          window.clearInterval(poll);
          window.setTimeout(() => router.push(`/trips/${tripId}`), 700);
        } else if (nextStatus === "failed") {
          window.clearInterval(poll);
          setError(data.error
            ? `We couldn’t finish creating this plan: ${data.error}`
            : "We couldn’t finish creating this plan. Your conversation is saved—please try generating it again.");
        }
      } catch {
        // Keep polling through transient API/network failures.
      }

      if (attempts >= 60) {
        window.clearInterval(poll);
        setError("This is taking longer than expected. Your draft is saved; please refresh in a moment.");
      }
    }, 5000);

    return () => window.clearInterval(poll);
  }, [currentTripId, tripIdFromRoute, status, router]);

  async function sendMessage(message = input) {
    const content = message.trim();
    if (!content || sending) return;
    if (status === "creating" || status === "generating") return;

    setInput("");
    setError("");
    setSending(true);
    setMessages((previous) => [
      ...previous,
      { id: Date.now(), role: "user", content, message_type: "text" },
    ]);

    try {
      const { data } = await chatApi.send(content, currentTripId);
      const reply = data as ChatReply;
      setCurrentTripId(reply.trip_id);
      hasLoadedInitialHistory.current = true;
      setStatus(reply.status);
      setSlotState(reply.slot_state || {});
      setMessages((previous) => [...previous, reply.agent_reply]);

      if (!tripIdFromRoute) {
        router.replace(`/chat/${reply.trip_id}`);
      }
      if (!tripIdFromRoute && (reply.status === "created" || reply.status === "done")) {
        window.setTimeout(() => router.push(`/trips/${reply.trip_id}`), 1500);
      }
    } catch (requestError) {
      setInput(content);
      setMessages((previous) => previous.slice(0, -1));
      const responseMessage = (
        requestError as { response?: { data?: { detail?: string } } }
      ).response?.data?.detail;
      setError(responseMessage || "Your message couldn’t be sent. Please try again.");
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }

  const slotEntries = Object.entries(slotState).filter(([, value]) =>
    value !== null && value !== undefined && value !== "",
  );
  const destination = isValidDestination(slotState.destination) ? slotState.destination : undefined;
  const hasValidDestination = Boolean(destination);
  const destinationText = destination ? formatValue(destination) : "";
  const destinationParts = destinationText.split(/\s*(?:→|,| and )\s*/i).filter(Boolean);
  const destinationRegion = [slotState.state, slotState.country].filter(Boolean).map(formatValue).join(", ");
  const adults = Number(slotState.travelers_adults || 1);
  const children = Number(slotState.travelers_children || 0);
  const party = `${adults} ${adults === 1 ? "adult" : "adults"}${children ? ` · ${children} ${children === 1 ? "child" : "children"}` : " · No children"}`;
  const travelDate = formatValue(slotState.start_date || slotState.start_month || "");
  const tripLength = slotState.days ? `${formatValue(slotState.days)} days` : "";
  const latestAssistantMessage = [...messages].reverse().find((message) => message.role === "assistant");
  const showDietOptions = (status === "draft" || status === "collecting") &&
    Boolean(latestAssistantMessage && /diet|vegetarian|vegan|food preference/i.test(latestAssistantMessage.content));
  const statusCopy = status === "created" || status === "done"
    ? ["Plan ready", "Opening your trip workspace…"]
    : status === "creating" || status === "generating"
      ? ["Creating your plan", "We’re preparing it now and will open it when it’s ready."]
      : status === "confirming"
        ? ["Ready to plan", "Confirm the details in the conversation."]
        : status === "failed"
          ? ["Planning paused", "Your conversation is saved."]
          : ["A few details to go", "We’ll build your trip together."];

  return (
    <>
      <Navbar />
      <main className={styles.main}>
        <div className={styles.pageContent}>
          <header className={styles.pageHeader}>
            <Link href={tripIdFromRoute ? `/trips/${tripIdFromRoute}` : "/dashboard"} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: "0.85rem", color: "var(--text-sub)", marginBottom: 16 }}>
              ← {tripIdFromRoute ? "Back to trip" : "My trips"}
            </Link>
            <p className={styles.eyebrow}>{tripIdFromRoute ? "EDIT YOUR TRIP / CONVERSATIONAL INPUT" : "CREATE A TRIP / CONVERSATIONAL INPUT"}</p>
            <h1 className="font-display">{tripIdFromRoute ? "Tell us what you’d like to change." : "Tell us about your trip in your own words."}</h1>
            <p>{tripIdFromRoute ? "Ask to change a day, activity, hotel, restaurant, budget, transport, or anything on your travel essentials list." : "We’ll ask one follow-up at a time. No forms, no dropdowns — just a conversation that builds your trip."}</p>
          </header>

          <div className={styles.layout}>
            <section className={styles.conversation}>
              <div className={styles.conversationHeader}>
                <div>
                  <p className={styles.sectionEyebrow}>TRIP PLANNING CONVERSATION</p>
                  <h2>{tripIdFromRoute ? `${firstName}, let’s refine your trip` : `${firstName}, let’s plan your next trip`}</h2>
                  <p>{tripIdFromRoute ? "Type an edit in plain language and I’ll save it to your trip." : "You can type freely. We’ll infer destinations, group size, and budget from what you say."}</p>
                </div>
                {currentTripId && status !== "created" && status !== "done" && (
                  <span className={styles.draftBadge}><span /> Draft saved</span>
                )}
              </div>

              <div className={styles.chatCard}>
                <div className={styles.messages} aria-live="polite" aria-label="Trip planning conversation">
                  {loadingHistory ? (
                    <div className={styles.loadingHistory}><span className="spinner" /> Loading your conversation…</div>
                  ) : messages.map((message, index) => (
                    <div
                      key={`${message.id}-${index}`}
                      className={`${styles.message} ${message.role === "user" ? styles.userMessage : styles.assistantMessage}`}
                    >
                      <span className={styles.speaker}>{message.role === "user" ? "YOU" : "ASSISTANT"}</span>
                      <p>{message.content}</p>
                    </div>
                  ))}
                  {sending && (
                    <div className={`${styles.message} ${styles.assistantMessage}`}>
                      <span className={styles.speaker}>ASSISTANT</span>
                      <div className={styles.typing} aria-label="Assistant is responding"><span /><span /><span /></div>
                    </div>
                  )}
                  <div ref={bottomRef} />
                </div>

                <div className={styles.composer}>
                  {showDietOptions && (
                    <div className={styles.quickReplies} aria-label="Dietary preference suggestions">
                      {DIET_OPTIONS.map((option) => (
                        <button key={option} type="button" onClick={() => sendMessage(option)} disabled={sending}>
                          {option}
                        </button>
                      ))}
                    </div>
                  )}
                  {(status === "creating" || status === "generating") && (
                    <div className={styles.generatingBar}>
                      <span className="spinner" />
                      <span>Putting your trip together — we’ll open the workspace as soon as it’s ready.</span>
                    </div>
                  )}
                  {error && <p className={styles.errorMessage} role="alert">{error}</p>}
                  <form onSubmit={(event) => { event.preventDefault(); sendMessage(); }} className={styles.inputRow}>
                    <input
                      ref={inputRef}
                      className={styles.chatInput}
                      placeholder="Type your next thought..."
                      value={input}
                      onChange={(event) => setInput(event.target.value)}
                      disabled={sending || status === "creating" || status === "generating" || loadingHistory}
                      aria-label="Your message"
                    />
                    <button type="submit" disabled={sending || !input.trim() || status === "creating" || status === "generating" || loadingHistory}>
                      {sending ? <span className="spinner" /> : "Send"}
                    </button>
                  </form>
                </div>
              </div>

              <div className={styles.suggestBanner}>
                <div>
                  <strong>Still deciding where to go?</strong>
                  <p>Tell me your budget and interests, and I’ll suggest 1–3 destinations.</p>
                </div>
                <button
                  type="button"
                  onClick={() => sendMessage("I’m not sure where to go. Please suggest a few destinations that fit my budget and interests.")}
                  disabled={sending || status === "generating"}
                >
                  Suggest destinations
                </button>
              </div>

              {(status === "confirming" || status === "failed") && (
                <div className={styles.confirmBanner}>
                  <div>
                    <strong>{status === "failed" ? "Your plan could not be created." : "Your trip details are ready."}</strong>
                    <p>{status === "failed" ? "The previous attempt failed. You can try again now." : "Review the conversation above, then generate your personalized plan."}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => sendMessage(status === "failed" ? "Please try generating my plan again." : "Yes, generate my plan.")}
                    disabled={sending}
                  >
                    {status === "failed" ? "Try again" : "Generate plan"}
                  </button>
                </div>
              )}
            </section>

            <aside className={styles.sidebar}>
              <section className={styles.detailsCard}>
                <p className={styles.sectionEyebrow}>EXTRACTED DETAILS</p>
                {!hasValidDestination || slotEntries.length === 0 ? (
                  <p className={styles.emptyDetails}>Your trip details will appear here as we chat.</p>
                ) : (
                  <>
                    {destinationText && (
                      <div className={styles.destination}>
                        <h3>{destinationParts.length > 1 ? destinationParts.join(" → ") : destinationText}</h3>
                        {destinationRegion && <p>{destinationRegion}</p>}
                      </div>
                    )}
                    {(travelDate || tripLength || slotState.travelers_adults !== undefined) && (
                      <p className={styles.metaLine}>
                        {[travelDate, tripLength].filter(Boolean).join(" · ")}
                        {travelDate || tripLength ? <br /> : null}
                        {party}
                      </p>
                    )}
                    {slotState.budget !== undefined && (
                      <div className={styles.budget}>
                        <strong>{formatBudget(slotState.budget)}</strong>
                        <span>{slotState.budget_scope === "per_person" ? "Budget per person" : "Total budget for the whole group"}</span>
                      </div>
                    )}
                    {slotState.starting_city ? (
                      <p className={styles.note}>Starting from {formatValue(slotState.starting_city)} is included in your estimate.</p>
                    ) : (
                      <p className={styles.note}>Starting city is not provided, so long-distance travel to/from home is excluded from this estimate.</p>
                    )}
                    {slotEntries.some(([key]) => ["travel_style", "interests", "pace", "diet"].includes(key)) && (
                      <div className={styles.preferences}>
                        {slotEntries.filter(([key]) => ["travel_style", "interests", "pace", "diet"].includes(key)).map(([key, value]) => (
                          <span key={key}>{formatValue(value)}</span>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </section>

              <div className={styles.statusCard}>
                <span className={`${styles.statusDot} ${status === "created" || status === "done" ? styles.dotDone : status === "creating" || status === "generating" ? styles.dotGenerating : status === "failed" ? styles.dotFailed : ""}`} />
                <div>
                  <strong>{statusCopy[0]}</strong>
                  <p>{statusCopy[1]}</p>
                </div>
              </div>
              <p className={styles.privacyNote}>Your draft is private. We use these details to plan your trip, never to book it.</p>
            </aside>
          </div>
        </div>
        <footer className={styles.footer}>
          <span>AI Travel Planner · A little structure. A lot to discover.</span>
          <span>Privacy&nbsp;&nbsp; Help&nbsp;&nbsp; Estimates, not guarantees</span>
        </footer>
      </main>
    </>
  );
}
