import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

// One shared client. Portfolio numbers are derived server-side, so a short
// staleTime is enough; a single retry keeps a down backend from hanging the UI.
//
// A 401 from anything except the auth probe itself means the session is gone:
// refetch ["me"] so App falls back to the Login page. A failed login attempt is
// a mutation keyed ["login"] and is handled by the form, not here.
function handleUnauthorized(error, isAuthCall) {
  if (error && error.status === 401 && !isAuthCall) {
    queryClient.invalidateQueries({ queryKey: ["me"] });
  }
}

export const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => handleUnauthorized(error, query.queryKey[0] === "me"),
  }),
  mutationCache: new MutationCache({
    onError: (error, _vars, _ctx, mutation) =>
      handleUnauthorized(error, mutation.options.mutationKey?.[0] === "login"),
  }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (count, error) => !(error && error.status >= 400 && error.status < 500) && count < 1,
    },
  },
});
