import { useEffect, useState, useRef } from "react";
import { api, type JournalEntry } from "../api";

export function AgentThoughtStream() {
  const [entries, setEntries] = useState<JournalEntry[]>([]);
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  async function fetchStream() {
    try {
      setBusy(true);
      const res = await api.journalTail(10);
      setEntries(res.entries);
    } catch (e) {
      console.error("ThoughtStream error:", e);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    fetchStream();
    const timer = setInterval(fetchStream, 5000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [entries]);

  return (
    <div 
      className="bg-(--paper) border border-(--rule) rounded-xl overflow-hidden shadow-sm"
      style={{ height: '400px', display: 'flex', flexDirection: 'column' }}
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-(--rule) bg-(--paper-tint)">
        <div className="flex items-center gap-2">
          <div className={`w-1.5 h-1.5 rounded-full ${busy ? 'bg-(--amber) animate-pulse' : 'bg-(--forest)'}`} />
          <h3 className="caps text-[10px] text-(--ink-60) font-bold tracking-widest">Agent Tankeflöde // Systempuls</h3>
        </div>
        <div className="text-[9px] text-(--ink-40) font-mono">
          {new Date().toLocaleTimeString('sv-SE')}
        </div>
      </div>
      
      <div 
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 font-mono text-[11px] leading-relaxed space-y-3 custom-scrollbar"
      >
        {entries.length === 0 ? (
          <div className="text-(--ink-40) italic">Väntar på agentaktivitet...</div>
        ) : (
          entries.map((entry, i) => (
            <div key={i} className="animate-in fade-in slide-in-from-left-1 duration-300">
              <div className="flex items-baseline gap-2 mb-0.5">
                <span className="text-(--ink-40) shrink-0">[{new Date(entry.ts).toLocaleTimeString('sv-SE')}]</span>
                <span className={`px-1 rounded-[2px] ${
                  entry.outcome === 'passed' ? 'bg-(--forest)/10 text-(--forest)' :
                  entry.outcome === 'failed' ? 'bg-(--barn)/10 text-(--barn)' : 'bg-(--stone)/10 text-(--stone)'
                }`}>
                  {entry.phase.toUpperCase()}
                </span>
              </div>
              <div className="text-(--ink-80) pl-4 border-l border-(--rule) ml-2 mt-1">
                {entry.lesson}
              </div>
            </div>
          ))
        )}
      </div>
      
      <div className="px-4 py-2 bg-(--paper-tint) border-t border-(--rule) flex items-center justify-between">
        <div className="text-[9px] text-(--ink-60) caps">Status: Autonom // CoVe Aktiv</div>
        <button 
          onClick={fetchStream}
          className="text-[9px] text-(--ink-40) hover:text-(--ink) transition-colors caps"
        >
          Tvinga uppdatering
        </button>
      </div>
    </div>
  );
}
