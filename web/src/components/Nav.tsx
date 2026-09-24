"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { GITHUB_URL } from "@/lib/content";

import { IconGithub, IconMenu, IconX } from "./icons";
import { OpenChatButton } from "./OpenChat";

const LINKS = [
  { href: "/", label: "What it does" },
  { href: "/#sources", label: "NEPRA sources" },
  { href: "/accuracy", label: "Accuracy" },
];

export function Nav() {
  const path = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <header className="nav">
      <div className="wrap nav-inner">
        <Link href="/" className="brand" aria-label="Rehnuma home" onClick={() => setOpen(false)}>
          <Image src="/logo-mark.png" alt="رہنما" width={64} height={34} priority />
          <span>Rehnuma</span>
        </Link>
        <nav className="nav-links" aria-label="Main">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className={path === l.href ? "active" : undefined}>
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="nav-actions">
          <a className="btn btn-light btn-sm" href={GITHUB_URL} target="_blank" rel="noreferrer">
            <IconGithub size={16} /> GitHub
          </a>
          <OpenChatButton className="btn btn-primary btn-sm">Try it free</OpenChatButton>
        </div>
        <button
          className="nav-toggle"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          {open ? <IconX /> : <IconMenu />}
        </button>
      </div>
      <div className={`nav-drawer${open ? " open" : ""}`}>
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} onClick={() => setOpen(false)}>
            {l.label}
          </Link>
        ))}
        <a href={GITHUB_URL} target="_blank" rel="noreferrer">
          GitHub
        </a>
      </div>
    </header>
  );
}
