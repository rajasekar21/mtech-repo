"use client";

import "./globals.css";
import { Inter } from "next/font/google";
import { ThemeProvider } from "next-themes";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { useState } from "react";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <html lang="en" suppressHydrationWarning className={inter.variable}>
      <head>
        <title>API Intelligence Platform</title>
        <meta name="description" content="Enterprise AI-Powered API Intelligence Platform — Discovery, Analysis, Governance" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body className="bg-background text-foreground antialiased font-sans">
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem={false}
          disableTransitionOnChange
        >
          <QueryClientProvider client={queryClient}>
            {children}
            <Toaster
              position="bottom-right"
              theme="dark"
              toastOptions={{
                classNames: {
                  toast:
                    "bg-slate-900 border border-slate-700 text-slate-100 shadow-xl",
                  title: "text-slate-100 font-medium",
                  description: "text-slate-400",
                  actionButton:
                    "bg-indigo-600 text-white hover:bg-indigo-500",
                  cancelButton:
                    "bg-slate-800 text-slate-300 hover:bg-slate-700",
                  error: "border-red-500/50",
                  success: "border-emerald-500/50",
                  warning: "border-amber-500/50",
                  info: "border-indigo-500/50",
                },
              }}
            />
          </QueryClientProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
