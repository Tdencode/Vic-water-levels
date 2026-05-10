"use client";

import { ThemeProvider } from "next-themes";

// Wraps the tree so any client component can call useTheme(). Using
// attribute="class" pairs with the @variant dark rule in globals.css.
// disableTransitionOnChange avoids a one-frame flash of the wrong colour
// when toggling.
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      {children}
    </ThemeProvider>
  );
}
