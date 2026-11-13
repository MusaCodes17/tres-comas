import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../services/api.js";

// All React Query hooks live in this file.

/** Backend liveness. Resolves to the parsed /health payload. */
export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: api.health });
}

/** Session probe. A 401 is an answer, not a failure to retry. */
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: api.me,
    retry: false,
    staleTime: 60_000,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: ["login"],
    mutationFn: (password) => api.login(password),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.logout,
    onSettled: () => {
      qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
      qc.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

export function useAccounts() {
  return useQuery({ queryKey: ["accounts"], queryFn: api.listAccounts });
}

export function useCreateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body) => api.createAccount(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });
}

export function useUpdateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }) => api.updateAccount(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });
}

export function useSecurities() {
  return useQuery({ queryKey: ["securities"], queryFn: api.listSecurities });
}

export function useCreateSecurity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body) => api.createSecurity(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["securities"] }),
  });
}

export function useTransactions(accountId) {
  return useQuery({
    queryKey: ["transactions", accountId],
    queryFn: () => api.listTransactions(accountId),
  });
}

export function usePositions(accountId, { includeClosed = false } = {}) {
  return useQuery({
    queryKey: ["positions", accountId, includeClosed],
    queryFn: () => api.listPositions(accountId, { includeClosed }),
  });
}

function useLedgerInvalidation(accountId) {
  const qc = useQueryClient();
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ["transactions", accountId] }),
      qc.invalidateQueries({ queryKey: ["positions", accountId] }),
    ]);
}

export function useCreateTransaction(accountId) {
  const invalidate = useLedgerInvalidation(accountId);
  return useMutation({
    mutationFn: (body) => api.createTransaction(accountId, body),
    onSuccess: invalidate,
  });
}

export function useVoidTransaction(accountId) {
  const invalidate = useLedgerInvalidation(accountId);
  return useMutation({
    mutationFn: (id) => api.voidTransaction(id),
    onSuccess: invalidate,
  });
}

export function useReplaceTransaction(accountId) {
  const invalidate = useLedgerInvalidation(accountId);
  return useMutation({
    mutationFn: ({ id, body }) => api.replaceTransaction(id, body),
    onSuccess: invalidate,
  });
}
