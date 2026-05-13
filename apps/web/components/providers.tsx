"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { AuthProvider } from "@/components/auth-provider";
import { CookieConsent } from "@/components/cookie-consent";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false,
            staleTime: 60_000
          }
        }
      }),
  );

  return (
    <AuthProvider>
      <QueryClientProvider client={queryClient}>
        {children}
        <CookieConsent />
      </QueryClientProvider>
    </AuthProvider>
  );
}
