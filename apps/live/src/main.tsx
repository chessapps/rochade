import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import { App } from "./App";
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "./index.css";

const client = new QueryClient({
  defaultOptions: {
    queries: {
      // The API says its answers are good for 15 seconds; agree with it.
      staleTime: 15_000,
      retry: 1,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={client}>
      <BrowserRouter basename="/live">
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
