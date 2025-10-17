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
      <body className="min-h-screen">
        <header className="sticky top-0 z-10 glass-strong nature-shadow-lg">
          <div className="mx-auto flex max-w-5xl items-center justify-between gap-6 px-6 py-5">
            <div className="flex items-center gap-4">
              {/* Logo space */}
              <div className="relative h-[5rem] w-[5rem] overflow-hidden rounded-2xl ring-2 ring-[color:var(--c-green-300)] nature-shadow transition-transform hover:scale-105">
                <Image alt="RAMA" src="/rama-logo.png" fill className="object-contain p-2" />
              </div>
              <div className="leading-tight">
                <div className="text-4xl font-bold tracking-tight bg-gradient-to-r from-[color:var(--c-green-700)] to-[color:var(--c-green-600)] bg-clip-text text-transparent">
                  RAMA
                </div>
                <div className="text-base text-[color:var(--c-green-700)] flex items-center gap-2 font-medium">
                  <span className="text-lg">🌾</span>
                  <span>Country Living</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button className="rounded-2xl px-5 py-2.5 text-white text-sm font-semibold nature-shadow-lg transition-all hover:scale-105 bg-gradient-to-r from-[color:var(--c-green-600)] to-[color:var(--c-green-700)] hover:from-[color:var(--c-green-700)] hover:to-[color:var(--c-green-800)] shine-effect">
                ✨ Asistente IA
              </button>
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-6 py-6 country-pattern">
          {children}
        </main>
        <footer className="mt-12 pb-8 text-center text-sm text-[color:var(--c-green-700)] opacity-70">
          <div className="flex items-center justify-center gap-2">
            <span>🏡</span>
            <span>Hecho con cariño para el campo</span>
            <span>🌿</span>
          </div>
        </footer>
      </body>
    </html>
  )
}
