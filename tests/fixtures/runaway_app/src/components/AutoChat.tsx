import { useEffect, useState } from "react";

export function AutoChat() {
  const [reply, setReply] = useState("");

  // BILL001: missing dependency array + network call inside useEffect
  useEffect(() => {
    fetch("/api/generate", { method: "POST" })
      .then((r) => r.text())
      .then(setReply);
  });

  // BILL002: aggressive sub-second polling timer
  setInterval(() => {
    fetch("/api/ping");
  }, 250);

  return <div>{reply}</div>;
}
