import type { Metadata, Viewport } from "next"
import { Geist, Geist_Mono } from "next/font/google"

import { BagDrawer } from "@/components/bag-drawer"
import { EvolusWidget } from "@/components/evolus-widget"
import { SiteNav } from "@/components/site-nav"
import "./globals.css"

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
})

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
})

export const metadata: Metadata = {
  title: {
    default: "Before You Buy",
    template: "%s · Before You Buy",
  },
  description: "Check a piece fits your room before you buy it.",
  applicationName: "Before You Buy",
}

export const viewport: Viewport = {
  themeColor: "#1c1917",
  colorScheme: "dark light",
}

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" suppressHydrationWarning className={`dark ${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-background text-foreground">
        <SiteNav />
        <main className="flex-1">{children}</main>
        <BagDrawer />
        <EvolusWidget />
      </body>
    </html>
  )
}
