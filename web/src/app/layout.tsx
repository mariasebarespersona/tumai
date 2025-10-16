import './globals.css'
import React from 'react'
import type { Metadata } from 'next'
import Image from 'next/image'

export const metadata: Metadata = {
  title: 'RAMA country living AI assistant',
  description: 'Chat with your countryside AI helper 🌿 🐝 🌾',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen country-gradient">
        <header className="sticky top-0 z-10 border-b border-[color:var(--c-green-200)] bg-white/70 backdrop-blur-md">
          <div className="mx-auto flex max-w-5xl items-center justify-between gap-6 px-4 py-4">
            <div className="flex items-center gap-4">
              {/* Logo space */}
              <div className="relative h-[4.5rem] w-[4.5rem] overflow-hidden rounded-md ring-1 ring-[color:var(--c-green-300)]">
                <Image alt="RAMA" src="/rama-logo.png" fill className="object-contain p-1" />
              </div>
              <div className="leading-tight">
                <div className="text-3xl font-semibold tracking-tight text-[color:var(--c-green-800)]">RAMA</div>
                <div className="text-base text-[color:var(--c-green-700)] flex items-center gap-1"><span>🌿</span><span>Country Living</span></div>
              </div>
            </div>
            <button className="rounded-full px-4 py-2 text-white text-sm shadow bg-[color:var(--c-green-600)] hover:bg-[color:var(--c-green-700)]">
              ✨ Asistente IA
            </button>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-4">
          {children}
        </main>
      </body>
    </html>
  )
}
