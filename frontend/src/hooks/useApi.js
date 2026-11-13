import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api.js";

// All React Query hooks live in this file.

/** Backend liveness. Resolves to the parsed /health payload. */
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: api.health,
  });
}
