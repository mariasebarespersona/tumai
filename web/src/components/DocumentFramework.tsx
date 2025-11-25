import React from 'react'

interface Document {
  document_group: string
  document_subgroup: string
  document_name: string
  storage_key?: string
  document_kind?: string
  placeholder?: boolean
  due_date?: string
  metadata?: any
}

interface DocumentFrameworkProps {
  uploaded: Document[]
  pending: Document[]
}

// Helper components
const StatusBadge = ({ uploaded, total }: { uploaded: number, total: number }) => {
  const pct = total > 0 ? Math.round((uploaded / total) * 100) : 0
  const color = pct === 100 ? 'bg-green-100 text-green-800' : pct > 0 ? 'bg-yellow-100 text-yellow-800' : 'bg-gray-100 text-gray-500'
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${color}`}>
      {uploaded}/{total} ({pct}%)
    </span>
  )
}

const DocItem = ({ doc, isUploaded }: { doc: Document, isUploaded: boolean }) => (
  <div className={`group flex items-center gap-2 p-1.5 rounded border border-transparent hover:border-[color:var(--stone-200)] hover:bg-white transition-all ${isUploaded ? 'opacity-100' : 'opacity-70'}`}>
    <div className={`w-5 h-5 flex items-center justify-center rounded-full text-[10px] ${isUploaded ? 'bg-[color:var(--forest-100)] text-[color:var(--forest-700)]' : 'bg-gray-100 text-gray-400'}`}>
      {isUploaded ? '✓' : '•'}
    </div>
    <div className="flex-1 min-w-0">
      <div className={`text-xs truncate ${isUploaded ? 'text-gray-900 font-medium' : 'text-gray-500'}`}>
        {doc.document_name}
      </div>
    </div>
    {doc.document_kind === 'factura' && (
        <span className="text-[10px] bg-amber-50 text-amber-600 px-1 rounded border border-amber-100">Factura</span>
    )}
  </div>
)

const SectionCard = ({ title, docs, colorTheme, icon, active = true, badge }: { title: string, docs: Document[], colorTheme: 'green' | 'blue' | 'purple', icon: string, active?: boolean, badge?: React.ReactNode }) => {
    const uploadedCount = docs.filter(d => d.storage_key).length
    
    const themeClasses = {
        green: {
            border: 'border-[color:var(--forest-200)]',
            header: 'bg-[color:var(--forest-50)] text-[color:var(--forest-900)]',
            iconBg: 'bg-white',
            activeRing: 'ring-[color:var(--forest-100)]'
        },
        blue: {
            border: 'border-blue-200',
            header: 'bg-blue-50 text-blue-900',
            iconBg: 'bg-white',
            activeRing: 'ring-blue-100'
        },
        purple: {
            border: 'border-purple-200',
            header: 'bg-purple-50 text-purple-900',
            iconBg: 'bg-white',
            activeRing: 'ring-purple-100'
        }
    }[colorTheme]

    return (
        <div className={`relative rounded-xl border ${themeClasses.border} bg-white shadow-sm transition-all duration-300 ${active ? 'opacity-100 shadow-md' : 'opacity-40 grayscale-[0.5] scale-95'}`}>
            <div className={`flex items-center justify-between p-3 rounded-t-xl border-b ${themeClasses.border} ${themeClasses.header}`}>
                <div className="flex items-center gap-2 font-bold text-sm">
                    <span className={`w-6 h-6 flex items-center justify-center rounded shadow-sm ${themeClasses.iconBg}`}>{icon}</span>
                    {title}
                    {badge && <span className="ml-2">{badge}</span>}
                </div>
                <StatusBadge uploaded={uploadedCount} total={docs.length} />
            </div>
            <div className="p-2 space-y-0.5 max-h-[300px] overflow-y-auto scrollbar-thin">
                {docs.length > 0 ? (
                    docs.map((doc, i) => <DocItem key={i} doc={doc} isUploaded={!!doc.storage_key} />)
                ) : (
                    <div className="p-4 text-center text-xs text-gray-400 italic">Sin documentos</div>
                )}
            </div>
        </div>
    )
}

const ArrowDown = () => (
    <div className="flex justify-center py-2">
        <div className="h-6 w-0.5 bg-gray-300"></div>
        <div className="absolute mt-5 w-2 h-2 border-r border-b border-gray-300 rotate-45 transform"></div>
    </div>
)

const Connector = ({ type }: { type: 'fork' | 'straight' }) => {
    if (type === 'straight') return <ArrowDown />
    
    return (
        <div className="relative h-8 w-full flex justify-center mb-2">
            <div className="absolute top-0 h-4 w-0.5 bg-gray-300"></div>
            <div className="absolute top-4 w-[50%] h-4 border-t-2 border-l-2 border-r-2 border-gray-300 rounded-t-xl"></div>
        </div>
    )
}

export const DocumentFramework = ({ uploaded, pending }: DocumentFrameworkProps) => {
  console.log('[DEBUG] DocumentFramework rendering with:', { uploaded: uploaded.length, pending: pending.length })
  const allDocs = [...uploaded, ...pending]

  // --- Grouping Logic ---
  const groups = {
    COMPRA: allDocs.filter(d => d.document_group === 'COMPRA'),
    
    // R2B Groups (subgroup names must match migration SQL exactly)
    R2B_DISENO: allDocs.filter(d => d.document_group === 'R2B' && d.document_subgroup === 'Diseño'),
    R2B_VENTA: allDocs.filter(d => d.document_group === 'R2B' && d.document_subgroup === 'Venta'),
    R2B_PM: allDocs.filter(d => d.document_group === 'R2B' && d.document_subgroup === 'Venta + PM'),
    
    // Promocion Groups
    PROMO_OBRA: allDocs.filter(d => d.document_group === 'Promoción' && d.document_subgroup === 'Obra'),
    PROMO_VENTA: allDocs.filter(d => d.document_group === 'Promoción' && d.document_subgroup === 'Venta'),
  }

  // --- Auto-detection of Strategy ---
  // Check activity in branches to determine what to highlight
  const hasActivity = (docs: Document[]) => docs.some(d => !!d.storage_key)
  
  const r2bActive = hasActivity(groups.R2B_DISENO) || hasActivity(groups.R2B_VENTA) || hasActivity(groups.R2B_PM)
  const promoActive = hasActivity(groups.PROMO_OBRA) || hasActivity(groups.PROMO_VENTA)
  
  // Logic: If R2B has activity, highlight it. If Promo has activity, highlight it. If neither, both active (pending decision).
  const showR2B = r2bActive || (!r2bActive && !promoActive)
  const showPromo = promoActive || (!r2bActive && !promoActive)

  return (
    <div className="w-full max-w-5xl mx-auto font-sans p-2 bg-gray-50/50 rounded-xl">
      
      {/* LEVEL 1: COMPRA (Always Active & Mandatory) */}
      <div className="max-w-2xl mx-auto mb-2">
        <div className="mb-3 text-center">
          <span className="inline-block px-4 py-1.5 bg-[color:var(--forest-700)] text-white text-xs font-bold rounded-full uppercase tracking-wider shadow-md">
            ✅ Fase Obligatoria para TODAS las propiedades
          </span>
        </div>
        <SectionCard 
            title="1. COMPRA" 
            docs={groups.COMPRA} 
            colorTheme="green" 
            icon="🏡"
            badge={
              <span className="px-2 py-0.5 bg-[color:var(--forest-700)] text-white text-[10px] font-bold rounded uppercase">
                Obligatorio
              </span>
            }
        />
      </div>

      {/* Decision Fork */}
      <div className="my-4 text-center">
        <div className="inline-block px-4 py-2 bg-gradient-to-r from-blue-100 to-purple-100 border-2 border-dashed border-gray-300 rounded-lg">
          <p className="text-xs font-bold text-gray-700 uppercase tracking-wider">⚡ Decisión: Elige UNA estrategia</p>
          <p className="text-[10px] text-gray-500 mt-1">R2B (Reformar y vender) o Promoción (Obra nueva)</p>
        </div>
      </div>
      <Connector type="fork" />
      
      {/* LEVEL 2: BRANCHES */}
      <div className="grid grid-cols-2 gap-4 relative">
          
          {/* BRANCH A: R2B */}
          <div className={`transition-all duration-500 ${!showR2B ? 'opacity-30 blur-[1px]' : ''}`}>
              <div className="text-center mb-2">
                <span className="inline-block px-3 py-1 bg-blue-100 text-blue-800 text-xs font-bold rounded-full uppercase tracking-wider shadow-sm border border-blue-200">
                    {showR2B && !promoActive ? '✅ ' : ''}Opción A: R2B
                </span>
              </div>
              
              <div className="space-y-4">
                  {/* Step 1: Diseño */}
                  <SectionCard 
                      title="1. Diseño + Facturas" 
                      docs={groups.R2B_DISENO} 
                      colorTheme="blue" 
                      icon="📐"
                      active={showR2B}
                  />
                  
                  {showR2B && <Connector type="straight" />}

                  {/* Step 2: Sub-decision */}
                  <div className={`space-y-4 ${!showR2B ? 'hidden' : ''}`}>
                     <div className="bg-blue-50/80 border border-blue-200 rounded-lg p-2 text-center">
                        <p className="text-[10px] font-bold text-blue-600 uppercase tracking-widest">Decisión: Venta vs PM</p>
                     </div>

                     <div className="grid grid-cols-1 gap-3">
                        <SectionCard 
                            title="2.1 Venta Simple" 
                            docs={groups.R2B_VENTA} 
                            colorTheme="blue" 
                            icon="💰"
                            active={showR2B}
                        />
                        <SectionCard 
                            title="2.2 Venta + PM" 
                            docs={groups.R2B_PM} 
                            colorTheme="blue" 
                            icon="🏗️"
                            active={showR2B}
                        />
                     </div>
                  </div>
              </div>
          </div>

          {/* BRANCH B: PROMOCIÓN */}
          <div className={`transition-all duration-500 ${!showPromo ? 'opacity-30 blur-[1px]' : ''}`}>
              <div className="text-center mb-2">
                <span className="inline-block px-3 py-1 bg-purple-100 text-purple-800 text-xs font-bold rounded-full uppercase tracking-wider shadow-sm border border-purple-200">
                    {promoActive && !r2bActive ? '✅ ' : ''}Opción B: Promoción
                </span>
              </div>

              <div className="space-y-4">
                 <SectionCard 
                      title="1. Obra Nueva" 
                      docs={groups.PROMO_OBRA} 
                      colorTheme="purple" 
                      icon="🚧"
                      active={showPromo}
                  />
                  
                  {showPromo && <Connector type="straight" />}
                  
                  <SectionCard 
                      title="2. Venta Promoción" 
                      docs={groups.PROMO_VENTA} 
                      colorTheme="purple" 
                      icon="🤝"
                      active={showPromo}
                  />
              </div>
          </div>

      </div>
      
      <div className="mt-8 text-center">
        <p className="text-xs text-gray-400 flex items-center justify-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[color:var(--forest-500)]"></span>
            Ruta activa determinada automáticamente por los documentos subidos
        </p>
      </div>
    </div>
  )
}
