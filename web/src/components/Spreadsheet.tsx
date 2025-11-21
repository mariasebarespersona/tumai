"use client"

import React from 'react'

type Props = {
  data: any[][]
  addressRange?: string
  selected?: string | null
  onCellClick?: (addr: string) => void
  showAddresses?: boolean
}

function colLabel(idx: number) {
  let s = ''
  let i = idx
  while (i >= 0) {
    s = String.fromCharCode(65 + (i % 26)) + s
    i = Math.floor(i / 26) - 1
  }
  return s
}

export default function Spreadsheet({ data = [[]], addressRange = 'A1', selected = null, onCellClick, showAddresses = false }: Props) {
  // parse start address
  const match = String(addressRange || 'A1').split(':')[0].match(/^([A-Za-z]+)(\d+)$/)
  const startCol = match ? match[1].toUpperCase().split('').reduce((acc,ch)=>acc*26+(ch.charCodeAt(0)-64),0)-1 : 0
  const startRow = match ? parseInt(match[2],10) : 1
  
  // Check if data contains cell objects with format, or just values
  const hasCellObjects = data.length > 0 && data[0].length > 0 && typeof data[0][0] === 'object' && data[0][0] !== null && 'value' in data[0][0]
  
  // Extract cell value and format
  const getCellData = (cell: any, rIdx: number, cIdx: number) => {
    if (hasCellObjects && cell && typeof cell === 'object' && 'value' in cell) {
      return {
        value: cell.value ?? '',
        format: cell.format || {},
        address: cell.address || `${colLabel(startCol + cIdx)}${startRow + rIdx}`,
        is_user_input: cell.is_user_input || false
      }
    }
    // Legacy format: just a value
    const addr = `${colLabel(startCol + cIdx)}${startRow + rIdx}`
    return {
      value: cell ?? '',
      format: {},
      address: addr,
      is_user_input: false
    }
  }
  
  return (
    <div className="w-full h-full overflow-auto bg-white select-none">
      <table className="table-fixed text-sm border-separate w-full" style={{ borderSpacing: 0 }}>
        <thead>
          <tr>
            <th className="sticky top-0 left-0 z-20 w-10 bg-[color:var(--stone-50)] border-b border-r border-[color:var(--border-subtle)] p-2 shadow-sm"></th>
            {data[0] && data[0].map((cell, cIdx) => {
              const cellData = getCellData(cell, 0, cIdx)
              
              return (
                <th 
                  key={cIdx} 
                  className="sticky top-0 z-10 p-2 text-xs font-serif font-medium text-[color:var(--text-secondary)] border-b border-r border-[color:var(--border-subtle)] bg-[color:var(--stone-50)] min-w-[100px]"
                >
                  {colLabel(startCol + cIdx)}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rIdx) => {
            return (
              <tr key={rIdx}>
                <td 
                  className="sticky left-0 z-10 p-2 text-xs font-medium text-center text-[color:var(--text-tertiary)] border-b border-r border-[color:var(--border-subtle)] bg-[color:var(--stone-50)]"
                >
                  {startRow + rIdx}
                </td>
                {row.map((cell, cIdx) => {
                  const cellData = getCellData(cell, rIdx, cIdx)
                  const format = cellData.format || {}
                  // Map Excel colors to our palette if needed, or keep raw
                  const bgColor = format.bg_color || '#ffffff'
                  const fontColor = format.font_color || 'var(--text-primary)'
                  const isBold = format.bold || false
                  const isSel = selected === cellData.address
                  
                  // Special styling for user input cells (yellow in excel)
                  // If it's a user input cell and no specific bg color is set, give it a subtle hint
                  const isUserInput = cellData.is_user_input
                  const effectiveBg = isSel ? 'var(--forest-50)' : (isUserInput && bgColor === '#ffffff' ? '#fffbeb' : bgColor) // #fffbeb is amber-50
                  
                  return (
                    <td
                      key={cIdx}
                      onClick={() => onCellClick?.(cellData.address)}
                      className={`
                        relative p-0 border-b border-r border-[color:var(--border-subtle)] cursor-cell transition-colors duration-75
                        ${isSel ? 'ring-2 ring-inset ring-[color:var(--forest-700)] z-10' : ''}
                        ${isUserInput && !isSel ? 'hover:bg-amber-100' : 'hover:bg-[color:var(--stone-50)]'}
                      `}
                      style={{
                        backgroundColor: effectiveBg,
                        color: fontColor,
                        fontWeight: isBold ? '600' : '400',
                        minWidth: '100px',
                        height: '32px'
                      }}
                    >
                      <div className="w-full h-full px-2 flex items-center justify-end overflow-hidden truncate">
                        {cellData.value || ''}
                      </div>
                      
                      {/* User input indicator corner */}
                      {isUserInput && (
                        <div className="absolute top-0 right-0 w-0 h-0 border-t-[6px] border-r-[6px] border-t-amber-400 border-r-transparent transform rotate-90" />
                      )}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
