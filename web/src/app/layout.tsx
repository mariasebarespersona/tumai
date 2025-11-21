import './globals.css'
import React from 'react'
import type { Metadata } from 'next'
import Image from 'next/image'
import { Inter, Lora } from 'next/font/google'

const inter = Inter({ 
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
})

const lora = Lora({
  subsets: ['latin'],
  variable: '--font-lora',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'RAMA Country Living',
  description: 'Your intelligent countryside property assistant.',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${lora.variable}`}>
      <body className="min-h-screen bg-[color:var(--bg-app)] font-sans text-[color:var(--text-primary)] selection:bg-[color:var(--c-green-100)] selection:text-[color:var(--c-green-900)]">
        
        {/* Modern Header - Clean & Professional */}
        <header className="sticky top-0 z-50 w-full border-b border-[color:var(--border-subtle)] bg-[color:var(--bg-surface-glass)] backdrop-blur-md transition-all duration-300">
          <div className="mx-auto flex h-16 max-w-[1600px] items-center justify-between px-6">
            
            {/* Brand Identity */}
            <div className="flex items-center gap-3 group cursor-pointer">
              <div className="relative h-8 w-8 overflow-hidden transition-transform duration-500 group-hover:rotate-12">
                 {/* Using emoji as fallback logo if image fails, or keep image if preferred. Keeping image for consistency. */}
                <Image 
                  alt="RAMA" 
                  src="/rama-logo.png" 
                  fill 
                  className="object-contain" 
                  sizes="32px"
                />
              </div>
              <div className="flex flex-col justify-center">
                <h1 className="font-serif text-xl font-bold leading-none tracking-tight text-[color:var(--text-primary)]">
                  RAMA
                </h1>
                <span className="text-[10px] font-medium uppercase tracking-widest text-[color:var(--text-secondary)] opacity-80 group-hover:opacity-100 transition-opacity">
                  Country Living
                </span>
              </div>
            </div>

            {/* Status Indicator / Assistant Label */}
            <div className="flex items-center gap-4">
               <div className="flex items-center gap-2 rounded-full border border-[color:var(--border-subtle)] bg-white/50 px-3 py-1 text-xs font-medium text-[color:var(--text-secondary)] shadow-sm backdrop-blur-sm">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75"></span>
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500"></span>
                </span>
                AI Assistant Active
              </div>
            </div>
            
          </div>
        </header>

        {/* Main Workspace - Full Width for Tools */}
        <main className="mx-auto max-w-[1600px] px-4 py-6 md:px-6">
          {children}
        </main>

        <footer className="mt-auto py-6 text-center">
          <p className="font-serif text-xs italic text-[color:var(--text-tertiary)]">
            Managed with care by RAMA AI
          </p>
        </footer>
      </body>
    </html>
  )
}
