import type { Metadata } from "next";
import { Inter, Raleway } from "next/font/google";

import { AppHeader } from "@/components/brand/app-header";

import { Providers } from "./providers";
import "./globals.css";

// Runs synchronously while <head> parses, so the first paint already has the right
// theme. (In this Next version a beforeInteractive <Script> is queued, not inlined.)
const THEME_INIT_SCRIPT = `
(function () {
  try {
    var stored = localStorage.getItem("forgeflow-theme");
    var theme = stored || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", theme);
  } catch (e) {}
})();
`;

const raleway = Raleway({ variable: "--font-raleway", subsets: ["latin"], weight: ["600", "700", "800"] });
const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });

export const metadata: Metadata = {
  title: { default: "ForgeFlow", template: "%s · ForgeFlow" },
  description: "Turn a business brief into approved, traceable requirements.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${raleway.variable} ${inter.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="flex min-h-full flex-col">
        <Providers>
          <div className="flex min-h-screen flex-col">
            <AppHeader />
            {children}
          </div>
        </Providers>
      </body>
    </html>
  );
}
