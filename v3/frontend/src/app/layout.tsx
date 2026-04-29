import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Regrow — Circular Economy OS',
  description: 'Waste Textile Management & ESG Dashboard',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body>{children}</body>
    </html>
  )
}
