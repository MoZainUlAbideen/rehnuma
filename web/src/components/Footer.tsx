import Link from "next/link";

import { GITHUB_URL } from "@/lib/content";

export function Footer() {
  return (
    <footer className="footer">
      <div className="wrap">
        <div>
          <strong style={{ color: "var(--navy)" }}>Rehnuma</strong> · رہنما — an open-source
          copilot for Pakistani electricity bills. Not legal advice; always confirm with your
          DISCO or NEPRA.
        </div>
        <div className="footer-links">
          <Link href="/">What it does</Link>
          <Link href="/accuracy">Accuracy</Link>
          <a href={GITHUB_URL} target="_blank" rel="noreferrer">
            GitHub
          </a>
        </div>
      </div>
    </footer>
  );
}
