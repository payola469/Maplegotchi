// Phase 0 placeholder. Shows no Maple state: the UI must only ever display real
// backend state (CLAUDE.md §3.9), and there is no backend state yet.
export const SCAFFOLD_NOTICE = "Maplegotchi scaffold. Maple is not running yet.";

export function App() {
  return <main>{SCAFFOLD_NOTICE}</main>;
}
