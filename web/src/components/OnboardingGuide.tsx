'use client'

import { useState } from 'react'

const GUIDES = [
  {
    id: 'basics',
    icon: '🏡',
    title: 'Primeros Pasos',
    steps: [
      { text: 'Crea una nueva propiedad llamada "Villa Demo" en Madrid', label: 'Crear Propiedad' },
      { text: '¿Qué propiedades tengo activas?', label: 'Listar Propiedades' },
      { text: 'Cambia a la propiedad "Villa Demo"', label: 'Cambiar Propiedad' },
    ]
  },
  {
    id: 'docs',
    icon: '📄',
    title: 'Documentos',
    steps: [
      { text: 'Muéstrame la lista de documentos requeridos', label: 'Ver Schema' },
      { text: '¿Qué documentos me faltan para completar la Compra?', label: 'Consultar Pendientes' },
      { text: 'Analiza el último documento subido y dime quiénes firman', label: 'Analizar Doc' },
    ]
  },
  {
    id: 'numbers',
    icon: '📊',
    title: 'Números',
    steps: [
      { text: 'Quiero trabajar en la plantilla de números R2B', label: 'Abrir Excel' },
      { text: 'Pon 350000 en el precio de compra (C5)', label: 'Editar Celda' },
      { text: 'Mándame un resumen de rentabilidad por email', label: 'Enviar Reporte' },
    ]
  }
]

export function OnboardingGuide({ onSelectPhrase }: { onSelectPhrase: (text: string) => void }) {
  const [isOpen, setIsOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('basics')

  if (!isOpen) {
    return (
      <button 
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[color:var(--forest-900)] text-white px-4 py-3 rounded-full shadow-lg hover:bg-[color:var(--forest-800)] transition-all transform hover:scale-105 hover:-translate-y-1 duration-200"
      >
        <span className="text-xl">🎓</span>
        <span className="font-serif font-medium">Guía Demo</span>
      </button>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-end sm:pr-6 pointer-events-none">
      {/* Backdrop simple */}
      <div className="absolute inset-0 pointer-events-auto bg-black/20 backdrop-blur-[2px] transition-opacity" onClick={() => setIsOpen(false)} />
      
      {/* Main Card */}
      <div className="pointer-events-auto w-full sm:w-[400px] bg-white/95 backdrop-blur-md rounded-t-2xl sm:rounded-2xl shadow-2xl border border-[color:var(--border-subtle)] overflow-hidden flex flex-col max-h-[80vh] animate-in slide-in-from-bottom-10 fade-in duration-300">
        
        {/* Header */}
        <div className="bg-[color:var(--forest-50)] p-4 border-b border-[color:var(--border-subtle)] flex justify-between items-center">
          <div>
            <h3 className="font-serif font-bold text-[color:var(--forest-900)] text-lg">Tour RAMA</h3>
            <p className="text-xs text-[color:var(--text-secondary)]">Guía interactiva para la demo</p>
          </div>
          <button onClick={() => setIsOpen(false)} className="p-2 hover:bg-[color:var(--stone-200)] text-[color:var(--text-tertiary)] hover:text-[color:var(--text-primary)] rounded-full transition-colors">✕</button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-[color:var(--border-subtle)] bg-white">
          {GUIDES.map(g => (
            <button
              key={g.id}
              onClick={() => setActiveTab(g.id)}
              className={`flex-1 py-3 text-sm font-medium transition-colors border-b-2 ${
                activeTab === g.id 
                  ? 'border-[color:var(--forest-500)] text-[color:var(--forest-900)] bg-[color:var(--forest-50)]' 
                  : 'border-transparent text-[color:var(--text-tertiary)] hover:text-[color:var(--text-primary)] hover:bg-[color:var(--stone-50)]'
              }`}
            >
              <span className="mr-1">{g.icon}</span> {g.title}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="p-4 overflow-y-auto bg-[color:var(--stone-50)] flex-1">
          <div className="space-y-3">
            {GUIDES.find(g => g.id === activeTab)?.steps.map((step, i) => (
              <button
                key={i}
                onClick={() => {
                  onSelectPhrase(step.text)
                  // Keep open to allow multiple actions or close? Let's keep open for now.
                }}
                className="w-full text-left group relative bg-white p-3 rounded-xl border border-[color:var(--border-subtle)] shadow-sm hover:shadow-md hover:border-[color:var(--forest-300)] transition-all active:scale-[0.98]"
              >
                <div className="text-xs font-bold text-[color:var(--forest-600)] uppercase tracking-wider mb-1">
                  {step.label}
                </div>
                <div className="text-sm text-[color:var(--text-primary)] font-medium group-hover:text-[color:var(--forest-900)]">
                  "{step.text}"
                </div>
                <div className="absolute right-3 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity text-[color:var(--forest-500)]">
                  ✨
                </div>
              </button>
            ))}
          </div>
          
          {/* Pro Tip */}
          <div className="mt-6 p-3 bg-amber-50 border border-amber-100 rounded-lg text-xs text-amber-800 flex gap-2 items-start">
            <span className="mt-0.5">💡</span>
            <span>Tip: Puedes arrastrar archivos PDF o Excel directamente al chat en cualquier momento.</span>
          </div>
        </div>
      </div>
    </div>
  )
}


