import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import { App } from "./App";
import { ToastProvider } from "./components/Toast";
import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "./index.css";

const client = new QueryClient({
  defaultOptions: {
    queries: {
      // A venue network drops packets; one failed poll is not an outage.
      retry: 1,
      staleTime: 2_000,
      refetchOnWindowFocus: true,
    },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={client}>
      <BrowserRouter basename="/admin">
        <ToastProvider>
          <App />
        </ToastProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
