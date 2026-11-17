import { useEffect } from "react";
import { Empty } from "./components";
import { useRoute } from "./hooks";
import { Shell } from "./Shell";
import { StoreProvider } from "./store";
import { ActorsView } from "./views/ActorsView";
import { EvidenceView } from "./views/EvidenceView";
import { ExplorerView } from "./views/ExplorerView";
import { GraphView } from "./views/GraphView";
import { IncidentsView } from "./views/IncidentsView";
import { ItemView } from "./views/ItemView";
import { LexView } from "./views/LexView";
import { LogView } from "./views/LogView";
import { MoneyView } from "./views/MoneyView";
import { SourcesView } from "./views/SourcesView";

const num = (v: string | undefined) => (v && /^\d+$/.test(v) ? Number(v) : null);

function Routes() {
  const { parts, query } = useRoute();
  const [view = "log", arg] = parts;

  // A new section starts at its top; selection changes inside a section keep their place.
  useEffect(() => {
    document.getElementById("main")?.scrollTo(0, 0);
  }, [view, view === "item" ? arg : null]);

  let active = view;
  let body;
  switch (view) {
    case "incidents":
      body = <IncidentsView selectedId={num(arg)} />;
      break;
    case "actors":
      body = <ActorsView selectedId={num(arg)} />;
      break;
    case "graph":
      body = <GraphView focus={query.get("focus")} depthParam={Number(query.get("depth") || 2)} />;
      break;
    case "money":
      body = <MoneyView selectedId={arg ?? null} />;
      break;
    case "explorer":
      body = <ExplorerView q={query.get("q") ?? ""} source={query.get("source") ?? ""} />;
      break;
    case "item": {
      active = "explorer";
      const id = num(arg);
      body = id === null ? <Empty title="No such record">Open a post from the Explorer or the message log.</Empty> : <ItemView key={id} id={id} />;
      break;
    }
    case "evidence":
      body = <EvidenceView />;
      break;
    case "sources":
      body = <SourcesView />;
      break;
    case "lex":
      body = <LexView />;
      break;
    default:
      active = "log";
      body = <LogView selectedId={num(arg)} />;
  }
  return <Shell active={active}>{body}</Shell>;
}

export function App() {
  return (
    <StoreProvider>
      <Routes />
    </StoreProvider>
  );
}
