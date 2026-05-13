import { useEffect, useRef, useMemo } from "react";
import maplibregl, { Map as MLMap, Marker } from "maplibre-gl";
import type { Prospect } from "../api";

interface Props {
  prospects: Prospect[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

const STYLE = "https://tiles.openfreemap.org/styles/liberty";
const SWEDEN_CENTER: [number, number] = [18.0686, 59.3293];

function getThemeColor(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const val = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return val || fallback;
}

export default function MapView({ prospects, selectedId, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MLMap | null>(null);
  const markersRef = useRef<Map<number, Marker>>(new Map());

  // Resolve colors once per render and memoize to prevent useEffect churn
  const colors = useMemo(() => ({
    new: getThemeColor("--stone", "#8a8780"),
    interested: getThemeColor("--forest", "#2b4f3c"),
    callback: getThemeColor("--amber", "#d06e29"),
    rejected: getThemeColor("--barn", "#a23434"),
    selected: getThemeColor("--amber", "#d06e29"),
  }), []);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    mapRef.current = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE,
      center: SWEDEN_CENTER,
      zoom: 5,
    });
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const existing = markersRef.current;
    const nextIds = new Set<number>();

    for (const p of prospects) {
      if (!p.id || p.lat == null || p.lng == null) continue;
      nextIds.add(p.id);
      const isSelected = p.id === selectedId;
      const color = isSelected
        ? colors.selected
        : (colors as any)[p.status ?? "new"] ?? colors.new;
      
      let marker = existing.get(p.id);
      if (!marker) {
        marker = new maplibregl.Marker({ color }).setLngLat([p.lng, p.lat]).addTo(map);
        marker.getElement().addEventListener("click", () => p.id && onSelect(p.id));
        existing.set(p.id, marker);
      } else {
        // Update color by recreating if needed (MapLibre Marker color is immutable)
        const currentMarkerColor = (marker as any)._color;
        if (currentMarkerColor !== color) {
          marker.remove();
          marker = new maplibregl.Marker({ color }).setLngLat([p.lng, p.lat]).addTo(map);
          marker.getElement().addEventListener("click", () => p.id && onSelect(p.id));
          existing.set(p.id, marker);
        } else {
          marker.setLngLat([p.lng, p.lat]);
        }
      }
    }

    for (const [id, marker] of existing) {
      if (!nextIds.has(id)) {
        marker.remove();
        existing.delete(id);
      }
    }
  }, [prospects, selectedId, onSelect, colors]);

  return <div ref={containerRef} className="h-full w-full" />;
}
