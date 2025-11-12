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

// Helper to convert hex color to RGB for opacity
function hexToRgba(hex: string, alpha: number = 1): string {
  if (!hex || !hex.startsWith('#')) return ''
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
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
        address: cell.address || `${colLabel(startCol + cIdx)}${startRow + rIdx}`
      }
    }
    // Legacy format: just a value
    const addr = `${colLabel(startCol + cIdx)}${startRow + rIdx}`
    return {
      value: cell ?? '',
      format: {},
      address: addr
    }
  }
  
  return (
    <div className="w-full overflow-auto bg-white" style={{ border: '1px solid #d1d5db' }}>
      <table className="table-auto text-sm border-collapse w-full" style={{ borderSpacing: 0 }}>
        <thead>
          <tr>
            <th className="p-1 w-8 text-[11px] font-semibold border border-gray-300 bg-gray-50" style={{ borderWidth: '1px' }}></th>
            {data[0] && data[0].map((cell, cIdx) => {
              const cellData = getCellData(cell, 0, cIdx)
              const format = cellData.format || {}
              const bgColor = format.bg_color || '#f9fafb'
              const fontColor = format.font_color || '#111827'
              const isBold = format.bold || false
              
              return (
                <th 
                  key={cIdx} 
                  className="p-1 text-[11px] border border-gray-300"
                  style={{
                    borderWidth: '1px',
                    backgroundColor: bgColor,
                    color: fontColor,
                    fontWeight: isBold ? 'bold' : 'normal',
                    minWidth: '80px'
                  }}
                >
                  {cellData.value || colLabel(startCol + cIdx)}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rIdx) => {
            const firstCell = getCellData(row[0], rIdx, 0)
            const firstFormat = firstCell.format || {}
            const firstBgColor = firstFormat.bg_color || '#f9fafb'
            const firstFontColor = firstFormat.font_color || '#111827'
            const firstBold = firstFormat.bold || false
            
            return (
              <tr key={rIdx}>
                <td 
                  className="p-1 text-[11px] border border-gray-300 font-semibold"
                  style={{
                    borderWidth: '1px',
                    backgroundColor: firstBgColor,
                    color: firstFontColor,
                    fontWeight: firstBold ? 'bold' : 'normal',
                    minWidth: '120px'
                  }}
                >
                  {firstCell.value || (startRow + rIdx)}
                </td>
                {row.map((cell, cIdx) => {
                  const cellData = getCellData(cell, rIdx, cIdx)
                  const format = cellData.format || {}
                  const bgColor = format.bg_color || '#ffffff'
                  const fontColor = format.font_color || '#000000'
                  const isBold = format.bold || false
                  const isSel = selected === cellData.address
                  
                  return (
                    <td
                      key={cIdx}
                      onClick={() => onCellClick?.(cellData.address)}
                      className="p-1.5 border border-gray-300 cursor-pointer relative"
                      style={{
                        borderWidth: '1px',
                        backgroundColor: isSel ? '#dbeafe' : bgColor,
                        color: fontColor,
                        fontWeight: isBold ? 'bold' : 'normal',
                        fontSize: '13px',
                        minWidth: '80px',
                        position: 'relative'
                      }}
                    >
                      {showAddresses && (
                        <div className="absolute top-0 right-0 text-[9px] text-gray-400 font-mono opacity-50 px-1">
                          {cellData.address}
                        </div>
                      )}
                      <div className={showAddresses ? 'mt-3' : ''}>
                        {cellData.value || ''}
                      </div>
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


