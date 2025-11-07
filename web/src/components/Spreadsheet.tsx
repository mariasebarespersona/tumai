"use client"

import React from 'react'

type Props = {
  data: any[][]
  addressRange?: string
  selected?: string | null
  onCellClick?: (addr: string) => void
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

export default function Spreadsheet({ data = [[]], addressRange = 'A1', selected = null, onCellClick }: Props) {
  // parse start address
  const match = String(addressRange || 'A1').split(':')[0].match(/^([A-Za-z]+)(\d+)$/)
  const startCol = match ? match[1].toUpperCase().split('').reduce((acc,ch)=>acc*26+(ch.charCodeAt(0)-64),0)-1 : 0
  const startRow = match ? parseInt(match[2],10) : 1

  return (
    <div className="w-full overflow-auto border rounded bg-white p-2">
      <table className="table-auto text-sm border-collapse w-full">
        <thead>
          <tr>
            <th className="p-1 w-8"></th>
            {data[0] && data[0].map((_, cIdx) => (
              <th key={cIdx} className="p-1 text-[12px] font-semibold border">{colLabel(startCol + cIdx)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rIdx) => (
            <tr key={rIdx}>
              <td className="p-1 text-[12px] font-semibold border">{startRow + rIdx}</td>
              {row.map((cell, cIdx) => {
                const addr = `${colLabel(startCol + cIdx)}${startRow + rIdx}`
                const isSel = selected === addr
                return (
                  <td key={cIdx} onClick={() => onCellClick?.(addr)} className={`p-2 border cursor-pointer ${isSel ? 'bg-[color:var(--c-green-100)]' : ''}`}>
                    <div className="text-xs text-[color:var(--c-green-700)] font-mono">{addr}</div>
                    <div className="mt-1">{cell ?? ''}</div>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}


