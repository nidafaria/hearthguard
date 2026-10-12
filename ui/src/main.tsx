import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import Inbox from "./Inbox";
import "./style.css";

// The local inbox lives at #/inbox; everything else is the read-only results page.
function Root() {
  const [hash, setHash] = React.useState(window.location.hash);
  React.useEffect(() => {
    const on = () => setHash(window.location.hash);
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return hash.startsWith("#/inbox") ? <Inbox hash={hash} /> : <App />;
}

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>,
);
