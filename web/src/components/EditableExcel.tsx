'use client'

import { useState, useEffect, useCallback } from 'react'

interface NumberItem {
  group_name: string
  item_key: string
  item_label: string
  is_percent: boolean
  amount: number | null
  updated_at?: string
}

interface EditableExcelProps {
  propertyId: string
  template: string
}

export default function EditableExcel({ propertyId, template }: EditableExcelProps) {
  const [items, setItems] = useState<NumberItem[]>([])
  const [loading, setLoading] = useState(true)
  const [editingCell, setEditingCell] = useState<{key: string, value: string} | null>(null)

  const fetchNumbers = useCallback(async () => {
    if (!propertyId) {
      console.log('[EditableExcel] No propertyId provided')
      setLoading(false)
      return
    }
    try {
      console.log('[EditableExcel] Fetching numbers for property:', propertyId, 'template:', template)
      const url = `/api/numbers?property_id=${encodeURIComponent(propertyId)}${template ? `&template_key=${encodeURIComponent(template)}` : ''}`
      console.log('[EditableExcel] Fetching from URL:', url)
      const response = await fetch(url)
      console.log('[EditableExcel] Response status:', response.status, 'ok:', response.ok)
      if (response.ok) {
        const data = await response.json()
        console.log('[EditableExcel] Received data:', data, 'length:', Array.isArray(data) ? data.length : 'not an array')
        const itemsArray = Array.isArray(data) ? data : []
        console.log('[EditableExcel] Setting items:', itemsArray.length, 'items')
        setItems(itemsArray)
        setLoading(false)
      } else {
        const errorText = await response.text()
        console.error('[EditableExcel] Error fetching numbers:', response.status, errorText)
        setLoading(false)
      }
    } catch (error) {
      console.error('[EditableExcel] Error fetching numbers:', error)
      setLoading(false)
    }
  }, [propertyId, template])

  useEffect(() => {
    fetchNumbers()
    // Poll for updates every 2 seconds
    const interval = setInterval(fetchNumbers, 2000)
    return () => clearInterval(interval)
  }, [fetchNumbers])

  const updateValue = async (itemKey: string, value: number | null) => {
    if (!propertyId) return
    try {
      // Find the item to get its label for better command
      const item = items.find(i => i.item_key === itemKey)
      const command = item ? `pon ${item.item_label} a ${value || 0}` : `pon ${itemKey} a ${value || 0}`
      
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          text: command,
          session_id: 'web-ui',
          property_id: propertyId,
        }),
      })
      if (response.ok) {
        // Wait a bit for the backend to process, then refresh
        setTimeout(() => {
          fetchNumbers()
        }, 500)
      }
    } catch (error) {
      console.error('Error updating value:', error)
    }
  }

  const handleCellClick = (item: NumberItem) => {
    setEditingCell({ key: item.item_key, value: item.amount?.toString() || '' })
  }

  const handleCellBlur = async (item: NumberItem) => {
    if (editingCell && editingCell.key === item.item_key) {
      const newValue = editingCell.value ? parseFloat(editingCell.value.replace(',', '.')) : null
      if (newValue !== item.amount) {
        await updateValue(item.item_key, newValue)
      }
      setEditingCell(null)
    }
  }

  const handleCellChange = (value: string) => {
    if (editingCell) {
      setEditingCell({ ...editingCell, value })
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-[color:var(--c-green-700)]">Cargando valores...</div>
      </div>
    )
  }

  // Si no hay items Y no está cargando, mostrar mensaje de error
  // Pero si hay items aunque sean NULL, mostrar la tabla (los items pueden tener amount: null)
  if (items.length === 0 && !loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8">
        <div className="text-4xl mb-4">📊</div>
        <div className="text-[color:var(--c-green-700)] font-semibold mb-2">No hay valores aún</div>
        <div className="text-sm text-[color:var(--c-green-600)] text-center">
          Usa el chat para agregar valores. Por ejemplo: "pon precio venta a 200000"
        </div>
      </div>
    )
  }
  
  // Si hay items (incluso con amount: null), mostrar la tabla
  // Esto es importante porque la estructura de la plantilla siempre tiene items, aunque los valores sean NULL

  // Group items by group_name
  const grouped = items.reduce((acc, item) => {
    const group = item.group_name || 'Otros'
    if (!acc[group]) acc[group] = []
    acc[group].push(item)
    return acc
  }, {} as Record<string, NumberItem[]>)

  return (
    <div className="h-full overflow-auto p-4">
      {Object.entries(grouped).map(([groupName, groupItems]) => (
        <div key={groupName} className="mb-6">
          <h3 className="text-lg font-bold text-[color:var(--c-green-800)] mb-3">{groupName}</h3>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse bg-white rounded-lg shadow-sm">
              <thead>
                <tr className="bg-[color:var(--c-green-100)]">
                  <th className="px-4 py-2 text-left border border-[color:var(--c-green-300)] text-[color:var(--c-green-800)] font-semibold">Concepto</th>
                  <th className="px-4 py-2 text-right border border-[color:var(--c-green-300)] text-[color:var(--c-green-800)] font-semibold">Importe (€)</th>
                  <th className="px-4 py-2 text-right border border-[color:var(--c-green-300)] text-[color:var(--c-green-800)] font-semibold">IVA (%)</th>
                </tr>
              </thead>
              <tbody>
                {groupItems.map((item) => (
                  <tr key={item.item_key} className="hover:bg-[color:var(--c-green-50)] transition-colors">
                    <td className="px-4 py-2 border border-[color:var(--c-green-300)] text-[color:var(--c-green-800)] font-medium">
                      {item.item_label}
                    </td>
                    <td className="px-4 py-2 border border-[color:var(--c-green-300)] text-right">
                      {editingCell?.key === item.item_key ? (
                        <input
                          type="text"
                          value={editingCell.value}
                          onChange={(e) => handleCellChange(e.target.value)}
                          onBlur={() => handleCellBlur(item)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              handleCellBlur(item)
                            }
                          }}
                          className="w-full px-2 py-1 text-right border-2 border-[color:var(--c-green-500)] rounded focus:outline-none focus:ring-2 focus:ring-[color:var(--c-green-500)]"
                          autoFocus
                        />
                      ) : (
                        <div
                          onClick={() => handleCellClick(item)}
                          className="cursor-pointer hover:bg-[color:var(--c-green-100)] px-2 py-1 rounded"
                        >
                          {item.amount !== null ? item.amount.toLocaleString('es-ES', { minimumFractionDigits: 0, maximumFractionDigits: 0 }) : '-'}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-2 border border-[color:var(--c-green-300)] text-right text-[color:var(--c-green-700)]">
                      {item.is_percent ? (item.amount !== null ? `${item.amount}%` : '-') : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  )
}

