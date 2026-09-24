import "@fontsource-variable/inter";
import "@fontsource-variable/source-serif-4";
import "@fontsource/noto-nastaliq-urdu/arabic-400.css";
import "./globals.css";
import "./chat.css";

import type { Metadata } from "next";

import { ChatWidget } from "@/components/ChatWidget";
import { Footer } from "@/components/Footer";
import { Nav } from "@/components/Nav";

export const metadata: Metadata = {
  title: {
    default: "Rehnuma · رہنما — your electricity bill, checked and explained",
    template: "%s · Rehnuma",
  },
  description:
    "An AI copilot for Pakistani electricity bills: audits every calculation, explains the bill in Urdu or English, and answers NEPRA rule questions with citations to the official documents.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>
        <Nav />
        <main>{children}</main>
        <Footer />
        <ChatWidget />
      </body>
    </html>
  );
}
