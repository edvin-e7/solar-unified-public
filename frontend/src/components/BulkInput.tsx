import { useRef, useState } from "react";
import { api } from "../api";

interface Props {
  onAdded: () => void;
}

export default function BulkInput({ onAdded }: Props) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function submit() {
    if (!text.trim()) return;
    setBusy(true);
    setResult(null);
    try {
      const res = await api.bulkImportCsv(text);
      setResult(`${res.created} tillagda, ${res.skipped} överhoppade`);
      setText("");
      onAdded();
      setTimeout(() => {
        setOpen(false);
        setResult(null);
      }, 1500);
    } catch (e) {
      setResult(`Fel: ${e instanceof Error ? e.message : "okänt"}`);
    } finally {
      setBusy(false);
    }
  }

  async function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const content = await file.text();
    setText(content);
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="rounded bg-(--paper-tint) px-3 py-1 text-xs text-(--ink) hover:bg-(--rule)"
      >
        + Lägg till adresser
      </button>
    );
  }

  return (
    <div className="flex items-start gap-2">
      <div className="flex flex-col gap-1">
        <textarea
          autoFocus
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="En adress per rad, eller CSV med header (address, owner_name, owner_phone, notes)…"
          className="h-20 w-80 rounded bg-(--paper-tint) p-2 text-xs font-mono text-(--ink) placeholder:text-(--ink-60)"
        />
        {result && (
          <span
            className={`text-xs ${result.startsWith("Fel") ? "text-(--barn)" : "text-(--forest)"}`}
          >
            {result}
          </span>
        )}
      </div>
      <div className="flex flex-col gap-1">
        <button
          disabled={busy}
          onClick={submit}
          className="rounded bg-(--amber)/20 px-3 py-1 text-xs text-(--amber) disabled:opacity-50"
        >
          {busy ? "…" : "Spara"}
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".csv,.txt"
          onChange={onFileChange}
          className="hidden"
        />
        <button
          onClick={() => fileRef.current?.click()}
          className="rounded bg-(--paper-tint) px-3 py-1 text-xs text-(--ink) hover:bg-(--rule)"
        >
          CSV-fil
        </button>
        <button
          onClick={() => {
            setOpen(false);
            setResult(null);
            setText("");
          }}
          className="rounded bg-(--paper-tint) px-3 py-1 text-xs text-(--ink) hover:bg-(--rule)"
        >
          Avbryt
        </button>
      </div>
    </div>
  );
}
