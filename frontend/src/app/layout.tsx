import type { Metadata } from "next";
import { Toaster } from "react-hot-toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Travel Planner — Less planning. More being there.",
  description:
    "Chat with an AI agent to plan your perfect trip — personalized itineraries, hotels, restaurants, and more. Powered by real place data.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body suppressHydrationWarning>
        {children}
        <Toaster
          position="bottom-right"
          toastOptions={{
            duration: 4000,
            style: { fontFamily: "Inter, sans-serif", fontSize: "0.875rem" },
            success: { iconTheme: { primary: "#1B4332", secondary: "#fff" } },
          }}
        />
      </body>
    </html>
  );
}
