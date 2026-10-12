import { render } from "preact";
import { mountLegacy } from "./ui/legacy";
import "./styles.css";

const root = document.getElementById("app");
if (root && import.meta.env.DEV) {
  // Compile-time boundary: production cannot load the switcher or fixture modules.
  void import("./dev/RoomSwitcher")
    .then(({ RoomSwitcher }) => render(<RoomSwitcher mountLegacy={mountLegacy} />, root))
    .catch(() => mountLegacy(root));
} else if (root) {
  mountLegacy(root);
}
