import { useEffect, useRef, useState } from "react";

export function ChatPanel({ orgId }: { orgId: string }) {
  const [status, setStatus] = useState("idle");
  const containerRef = useRef<HTMLDivElement>(null);

  // Bounded effect with explicit dependency array
  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/chat?org=${encodeURIComponent(orgId)}`, {
      signal: controller.signal,
    })
      .then((res) => setStatus(res.ok ? "ready" : "error"))
      .catch(() => setStatus("cancelled"));
    return () => controller.abort();
  }, [orgId]);

  // Reasonable 5-second health check interval
  useEffect(() => {
    const id = setInterval(() => {
      fetch("/api/health", { signal: AbortSignal.timeout(2000) }).catch(() => {});
    }, 5000);
    return () => clearInterval(id);
  }, []);

  // Pure DOM effect without network calls needs no special spend controls
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.dataset.mounted = "true";
    }
  });

  return <div ref={containerRef}>{status}</div>;
}
