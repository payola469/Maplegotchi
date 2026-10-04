// Page layout only: header, section navigation and the grid areas the existing
// components are placed into. It shows no backend values of its own; every slot
// is rendered exactly once (one room, one interaction bar).
//
// Navigation is a plain list of in-page links. On wide screens it is a sidebar;
// on phones the same element is a bottom bar (CSS only, styles.css). The current
// section is highlighted from the scroll position: presentation only, local to
// this component, and absent where the browser APIs are missing.

import type { ComponentChildren } from "preact";
import { useCallback, useEffect, useRef, useState } from "preact/hooks";

export interface AppShellProps {
  header: ComponentChildren;
  banners: ComponentChildren;
  room: ComponentChildren;
  status: ComponentChildren;
  interactions: ComponentChildren;
  journal: ComponentChildren;
  activity: ComponentChildren;
  system: ComponentChildren;
}

type SectionId = "room" | "status" | "journal" | "activity" | "system";

const SECTIONS: readonly { id: SectionId; label: string }[] = [
  { id: "room", label: "Room" },
  { id: "status", label: "Status" },
  { id: "journal", label: "Journal" },
  { id: "activity", label: "Activity" },
  { id: "system", label: "System" },
];

// Simple stroke icons (decorative; the label is the accessible name).
const ICON_PATHS: Readonly<Record<SectionId, string>> = {
  room: "M4 11.5 12 5l8 6.5V20a1 1 0 0 1-1 1h-4.5v-5.5h-5V21H5a1 1 0 0 1-1-1z",
  status: "M12 20.5s-7.5-4.6-7.5-10A4.3 4.3 0 0 1 12 7.6a4.3 4.3 0 0 1 7.5 2.9c0 5.4-7.5 10-7.5 10z",
  journal: "M6 4h10a2 2 0 0 1 2 2v14H8a2 2 0 0 1-2-2zM6 18a2 2 0 0 1 2-2h10M10 8h5M10 11h4",
  activity: "M12 7v5l3 2M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z",
  system: "M5 5h14v6H5zM5 13h14v6H5zM8 8h.01M8 16h.01",
};

function NavIcon({ id }: { id: SectionId }) {
  return (
    <svg class="sidenav__icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d={ICON_PATHS[id]} />
    </svg>
  );
}

/**
 * The section whose top has passed a line a third of the way down the viewport.
 * `preferred` (the last link clicked) wins ties between side-by-side areas and,
 * at the end of the page, as long as it is still on screen.
 */
function sectionInView(preferred: SectionId | null): SectionId {
  const line = window.innerHeight / 3;
  const rect = (id: SectionId) => document.getElementById(id)?.getBoundingClientRect();
  const doc = document.documentElement;
  if (window.scrollY > 0 && window.innerHeight + window.scrollY >= doc.scrollHeight - 2) {
    const p = preferred ? rect(preferred) : undefined;
    if (preferred && p && p.bottom > 0 && p.top < window.innerHeight) return preferred;
    return SECTIONS[SECTIONS.length - 1]?.id ?? "room";
  }
  let current: SectionId = "room";
  let currentTop = -Infinity;
  for (const { id } of SECTIONS) {
    const top = rect(id)?.top;
    if (top === undefined || top > line) continue;
    // Ties (areas side by side) keep the earlier section unless the other was clicked.
    if (top > currentTop || (top === currentTop && id === preferred)) {
      current = id;
      currentTop = top;
    }
  }
  return current;
}

function useCurrentSection(): [SectionId, (id: SectionId) => void] {
  const [current, setCurrent] = useState<SectionId>("room");
  const preferred = useRef<SectionId | null>(null);
  const select = useCallback((id: SectionId) => {
    preferred.current = id;
    setCurrent(id);
  }, []);
  useEffect(() => {
    if (typeof window === "undefined" || typeof window.requestAnimationFrame !== "function") return undefined;
    let frame: number | null = null;
    const onScroll = () => {
      if (frame !== null) return;
      frame = window.requestAnimationFrame(() => {
        frame = null;
        setCurrent(sectionInView(preferred.current));
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    onScroll();
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame !== null) window.cancelAnimationFrame(frame);
    };
  }, []);
  return [current, select];
}

export function AppShell(props: AppShellProps) {
  const [current, setCurrent] = useCurrentSection();
  const area = (id: SectionId, children: ComponentChildren) => (
    <div class={`area area--${id}`} id={id}>
      {children}
    </div>
  );
  return (
    <div class="app shell">
      {props.header}
      {props.banners}
      <div class="shell__body">
        <nav class="sidenav" aria-label="Sections">
          <ul class="sidenav__list">
            {SECTIONS.map((s) => (
              <li key={s.id}>
                <a
                  class="sidenav__link"
                  href={`#${s.id}`}
                  aria-current={current === s.id ? "location" : undefined}
                  onClick={() => setCurrent(s.id)}
                >
                  <NavIcon id={s.id} />
                  <span class="sidenav__label">{s.label}</span>
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <main class="layout">
          {area("room", props.room)}
          {area("status", props.status)}
          <div class="area area--interactions">{props.interactions}</div>
          {area("journal", props.journal)}
          {area("activity", props.activity)}
          {area("system", props.system)}
        </main>
      </div>
    </div>
  );
}
