import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { Session } from "../../lib/api/types";
import { changePassword, fetchSession, signIn, signOut } from "./api";

export const sessionKey = ["session"] as const;

export function useSession() {
  return useQuery({ queryKey: sessionKey, queryFn: fetchSession, staleTime: 60_000 });
}

/** The signed-in session; only valid under <RequireSession>. */
export function useRequiredSession(): Session {
  const { data } = useSession();
  if (!data) throw new Error("useRequiredSession used outside <RequireSession>");
  return data;
}

export function useSignIn() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      signIn(email, password),
    onSuccess: (session) => queryClient.setQueryData(sessionKey, session),
  });
}

export function useSignOut() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: signOut,
    onSettled: () => {
      queryClient.clear();
      queryClient.setQueryData(sessionKey, null);
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: ({ current, next }: { current: string; next: string }) =>
      changePassword(current, next),
  });
}
