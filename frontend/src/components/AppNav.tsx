import { useLocation, useNavigate } from "react-router-dom";
import { Sidebar, type NavItem } from "./ui/Sidebar";

const ITEMS: NavItem[] = [
  { id: "dashboard", label: "Dashboard", icon: "layout-dashboard" },
  { id: "prospekt", label: "Affärsmöjligheter", icon: "users" },
  { id: "sok", label: "Prospektering", icon: "search" },
  { id: "detektion", label: "Takanalys", icon: "scan-eye" },
  { id: "panelagare", label: "Panelägare", icon: "sun" },
  { id: "karta", label: "Marknadskarta", icon: "map" },
  { id: "agenter", label: "Agentstatus", icon: "bot" },
  { id: "berikning", label: "Beslutsunderlag", icon: "sparkles" },
  { id: "installningar", label: "System", icon: "settings" },
];

const PATH_BY_ID: Record<string, string> = {
  dashboard: "/",
  prospekt: "/prospekt",
  sok: "/sok",
  detektion: "/detektion",
  panelagare: "/panelagare",
  karta: "/karta",
  agenter: "/agenter",
  berikning: "/berikning",
  installningar: "/installningar",
};

function idFromPath(pathname: string): string {
  if (pathname === "/" || pathname === "") return "dashboard";
  const seg = pathname.replace(/^\//, "").split("/")[0];
  return seg in PATH_BY_ID ? seg : "dashboard";
}

export function AppNav() {
  const location = useLocation();
  const navigate = useNavigate();
  const activeId = idFromPath(location.pathname);

  return (
    <Sidebar
      items={ITEMS}
      activeId={activeId}
      onSelect={(id) => {
        const path = PATH_BY_ID[id];
        if (path) navigate(path);
      }}
      user={{ name: "Edvin Pierre", email: "edvin.pierre03@gmail.com", initials: "EP" }}
    />
  );
}
