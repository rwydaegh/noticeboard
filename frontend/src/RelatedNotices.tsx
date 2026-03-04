import { useState } from "react";
import { demo, request } from "./api";
import type { Notice } from "./types";

export default function RelatedNotices({
  notice,
  onOpen,
}: {
  notice: Notice;
  onOpen: (notice: Notice) => void;
}) {
  const [items, setItems] = useState<Notice[]>([]),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [loaded, setLoaded] = useState(false);
  if (demo) return null;
  return (
    <section>
      <h3>Similar notices</h3>
      <button
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          setMessage("");
          try {
            const result = await request<{
              items: Notice[];
              warnings: string[];
            }>("/notices/" + notice.id + "/related");
            setItems(result.items);
            setMessage(result.warnings.join(" "));
            setLoaded(true);
          } catch (e) {
            setMessage(e instanceof Error ? e.message : String(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        {busy ? "Loading…" : loaded ? "Refresh" : "Find similar"}
      </button>
      {message && <p className="caveat">{message}</p>}
      {items.map((item) => (
        <button
          className="related-notice"
          key={item.id}
          onClick={() => onOpen(item)}
        >
          {item.title}
          <span>
            {item.buyer}, {item.country}
          </span>
        </button>
      ))}
    </section>
  );
}
