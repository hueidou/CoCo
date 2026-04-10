import { useEffect } from "react";
import { useSiteConfig } from "@/config-context";
import { CocoChannels } from "./components/Channels";
import { CocoClientVoices } from "./components/ClientVoices";
import { CocoContributors } from "./components/Contributors";
import { CocoFAQ } from "./components/FAQ";
import { CocoFinalCTA } from "./components/FinalCTA";
import { CocoHero } from "./components/Hero";
import { CocoQuickStart } from "./components/QuickStart";
import { CocoWhatYouCanDo } from "./components/WhatYouCanDo";
import { CocoWorksForYou } from "./components/WorksForYou";
import { CocoWhy } from "./components/WhyCoco";

export default function Home() {
  const config = useSiteConfig();
  const docsBase = (config.docsPath ?? "/docs/").replace(/\/$/, "") || "/docs";

  // Config load delays first paint; the browser scrolls to #id before the
  // target exists. Re-apply hash scroll after the home sections mount.
  useEffect(() => {
    const raw = window.location.hash.slice(1);
    if (!raw) return;
    let id: string;
    try {
      id = decodeURIComponent(raw);
    } catch {
      id = raw;
    }
    const scroll = () => {
      document.getElementById(id)?.scrollIntoView({
        behavior: "auto",
        block: "start",
      });
    };
    requestAnimationFrame(() => {
      requestAnimationFrame(scroll);
    });
  }, []);

  return (
    <main className="min-h-screen bg-(--bg) text-(--text)">
      <CocoHero />
      <CocoQuickStart docsBase={docsBase} />
      <CocoChannels />
      <CocoWhy />
      <CocoWhatYouCanDo />
      <CocoWorksForYou />
      <CocoClientVoices />
      <CocoFAQ />
      <CocoContributors />
      <CocoFinalCTA />
    </main>
  );
}
