import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { Session } from "../../lib/api/types";
import { fetchSession, signIn, signOut } from "./api";

/** The one cache key for "who is signed in". Everything that needs the session shares it. */
export const sessionKey = ["session"] as const;

/** The current session: `Session` when signed in, `null` when signed out, `undefined` while loading. */
export function useSession() {
  return useQuery({ queryKey: sessionKey, queryFn: fetchSession, staleTime: 60_000 });
}

/** The signed-in session; only valid under <RequireSession>. */
export function useRequiredSession(): Session {
  const { data } = useSession();
  if (!data) throw new Error("useRequiredSession used outside <RequireSession>");
  return data;
}

/** The sign-in action. Call `signIn.mutate({ email, password })`. */
export function useSignIn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      signIn(email, password),
    // Store the new session in the shared cache so the rest of the app sees it immediately.
    onSuccess: (session) => queryClient.setQueryData(sessionKey, session),
  });
}

/** The sign-out action. Call `signOut.mutate()`. */
export function useSignOut() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => signOut(),
    onSettled: () => {
      queryClient.clear();
      queryClient.setQueryData(sessionKey, null);
    },
  });
}
