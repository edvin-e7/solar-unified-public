import { lazy, Suspense, type ComponentType } from "react";
import { createBrowserRouter } from "react-router-dom";
import AppShell from "./AppShell";

const Dashboard = lazy(() => import("./pages/Dashboard"));
const Prospects = lazy(() => import("./pages/Prospects"));
const Search = lazy(() => import("./pages/Search"));
const Detection = lazy(() => import("./pages/Detection"));
const MapPage = lazy(() => import("./pages/Map"));
const Agents = lazy(() => import("./pages/Agents"));
const Enrichment = lazy(() => import("./pages/Enrichment"));
const Panels = lazy(() => import("./pages/Panels"));
const Settings = lazy(() => import("./pages/Settings"));

function Loading() {
  return (
    <div className="flex h-full w-full items-center justify-center p-10 caps text-(--ink-60)">
      Laddar…
    </div>
  );
}

const wrap = (El: ComponentType) => (
  <Suspense fallback={<Loading />}>
    <El />
  </Suspense>
);

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: wrap(Dashboard) },
      { path: "prospekt", element: wrap(Prospects) },
      { path: "sok", element: wrap(Search) },
      { path: "detektion", element: wrap(Detection) },
      { path: "karta", element: wrap(MapPage) },
      { path: "agenter", element: wrap(Agents) },
      { path: "berikning", element: wrap(Enrichment) },
      { path: "panelagare", element: wrap(Panels) },
      { path: "installningar", element: wrap(Settings) },
    ],
  },
]);
