import { QueryClient } from "@tanstack/react-query";

// One shared client. Portfolio numbers are derived server-side, so a short
// staleTime is enough; a single retry keeps a down backend from hanging the UI.
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});
