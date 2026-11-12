import { Suspense } from "react";
import TripChat from "@/components/TripChat";

export default function ExistingChatPage() {
  return (
    <Suspense fallback={<p>Loading conversation…</p>}>
      <TripChat />
    </Suspense>
  );
}
