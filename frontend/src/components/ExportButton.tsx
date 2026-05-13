import { api } from "../api";

export default function ExportButton() {
  return (
    <a
      href={api.exportCsvUrl()}
      download="prospects.csv"
      className="rounded bg-(--paper-tint) px-3 py-1 text-xs text-(--ink) hover:bg-(--rule)"
    >
      Exportera CSV
    </a>
  );
}
