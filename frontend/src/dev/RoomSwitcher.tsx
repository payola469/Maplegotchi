import { render } from "preact";
import { useEffect, useRef, useState } from "preact/hooks";
import { fixturePreviewEnabled } from "../world-room/gate";
import "./coexistence.css";

export type MountLegacy = (host: HTMLElement) => () => void;
export type LoadFixture = () => Promise<(host: HTMLElement, onLegacy: () => void) => () => void>;
const loadFixture: LoadFixture = async () => {
  const { WorldPreview } = await import("../world-room/Preview");
  return (host, onLegacy) => {
    render(<WorldPreview onReturnLegacy={onLegacy} />, host);
    return () => render(null, host);
  };
};

/** Development entry only. No preview import or fixture subscription before activation. */
export function RoomSwitcher({ mountLegacy, loadPreview = loadFixture, development = import.meta.env.DEV, search = window.location.search }: {
  mountLegacy: MountLegacy;
  loadPreview?: LoadFixture;
  development?: boolean;
  search?: string;
}) {
  const [requested, setRequested] = useState(() => fixturePreviewEnabled(development, search));
  const enabled = development && requested;
  const host = useRef<HTMLDivElement>(null);
  const selector = useRef<HTMLSelectElement>(null);
  const [error, setError] = useState(false);
  const selectLegacy = useRef<() => void>(() => undefined);
  selectLegacy.current = () => {
    const url = new URL(window.location.href);
    url.searchParams.delete("room");
    window.history.replaceState(null, "", url);
    setRequested(false);
    selector.current?.focus();
  };
  useEffect(() => {
    const onPop = () => setRequested(fixturePreviewEnabled(development, window.location.search));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [development]);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    let cancelled = false;
    let dispose: (() => void) | undefined;
    setError(false);
    if (!enabled) dispose = mountLegacy(element);
    else void loadPreview().then((mount) => {
      if (!cancelled) dispose = mount(element, () => selectLegacy.current());
    }).catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; dispose?.(); };
  }, [enabled, mountLegacy, loadPreview]);
  return <>
    {development && <nav aria-label="Development Room view" class="room-switcher">
      <label>Development Room view <select ref={selector} value={enabled ? "fixture" : "legacy"} onChange={(event) => {
        const fixture = event.currentTarget.value === "fixture";
        const url = new URL(window.location.href);
        url.searchParams.delete("room");
        if (fixture) url.searchParams.set("room", "fixture");
        window.history.replaceState(null, "", url);
        setRequested(fixture);
      }}><option value="legacy">Legacy Room</option><option value="fixture">New Room — FIXTURE / DEMO</option></select></label>
    </nav>}
    {error && <p role="alert">Fixture preview unavailable. Select Legacy Room to return.</p>}
    <div ref={host} />
  </>;
}
