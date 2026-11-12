"use client";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import TripChat from "@/components/TripChat";

function NewChatInner() {
  const searchParams = useSearchParams();
  // Key changes whenever ?q= changes, forcing a full remount with clean state
  const q = searchParams.get("q") || "";
  return <TripChat key={`new-chat-${q}`} />;
}

export default function NewChatPage() {
  return (
    <Suspense fallback={<p>Loading chat…</p>}>
      <NewChatInner />
    </Suspense>
  );
}
