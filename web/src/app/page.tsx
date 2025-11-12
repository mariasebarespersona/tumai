'use client'

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { mcpExcel } from '@/lib/mcp/client'
import Spreadsheet from '@/components/Spreadsheet'
import type { DragEvent } from 'react'
// Removed EditableExcel import - using iframe instead

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
}

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [uploading, setUploading] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const [isRecording, setIsRecording] = useState(false)
  const [isProcessingVoice, setIsProcessingVoice] = useState(false)
  const [propertyId, setPropertyId] = useState<string | null>(null) // Track current property_id
  const [propertyName, setPropertyName] = useState<string | null>(null) // Track property name for display
  const [excelTemplate, setExcelTemplate] = useState<string | null>(null)
  const [toolLogs, setToolLogs] = useState<Array<{tool:string,args:any,ms:number,mode:string,result:any}>>([])
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const scrollRef = useRef<HTMLDivElement | null>(null)

  // Sync with backend on mount - send a ping to get current property_id
  useEffect(() => {
    const syncWithBackend = async () => {
      console.log('[SYNC] Starting sync with backend...')
      try {
        const form = new FormData()
        form.append('text', '') // Empty message to sync
        form.append('session_id', 'web-ui')
        
        const resp = await fetch('/api/chat', { method: 'POST', body: form })
        const data = await resp.json()
        console.log('[SYNC] Backend response:', data)
        
        // Backend will send back its current property_id and property_name
        if (data.property_id) {
          setPropertyId(data.property_id)
          console.log('[SYNC] Backend property_id:', data.property_id)
          
          if (data.property_name) {
            setPropertyName(data.property_name)
            console.log('[SYNC] Backend property_name:', data.property_name)
          }
        } else {
          // No property in backend - clear localStorage to avoid confusion
          console.log('[SYNC] No property in backend - clearing stored property')
          localStorage.removeItem('property_id')
          localStorage.removeItem('property_name')
          setPropertyId(null)
          setPropertyName(null)
        }
      } catch (e) {
        console.error('[SYNC] Failed to sync with backend:', e)
        // Fallback to localStorage
        const savedPropertyId = localStorage.getItem('property_id')
        const savedPropertyName = localStorage.getItem('property_name')
        if (savedPropertyId) setPropertyId(savedPropertyId)
        if (savedPropertyName) setPropertyName(savedPropertyName)
      }
    }
    
    syncWithBackend()
  }, [])

  // Save property to localStorage when it changes
  useEffect(() => {
    if (propertyId) {
      localStorage.setItem('property_id', propertyId)
    }
    if (propertyName) {
      localStorage.setItem('property_name', propertyName)
    }
  }, [propertyId, propertyName])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages.length])

  const onDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    const dropped = Array.from(e.dataTransfer.files || [])
    if (dropped.length) setFiles(prev => [...prev, ...dropped])
  }, [])

  

  async function writeCell(address: string, value: any) {
    if (!propertyId || !excelTemplate) {
      throw new Error('No propertyId or template selected')
    }
    try {
      // Write to Numbers Table (new system)
      const form = new FormData()
      form.append('property_id', propertyId)
      form.append('template_key', excelTemplate)
      form.append('cell_address', address)
      form.append('value', String(value))
      const resp = await fetch(`${BACKEND_URL}/api/numbers/set-cell-value`, {
        method: 'POST',
        body: form
      })
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}))
        throw new Error(data?.error || `Failed to write cell: ${resp.status}`)
      }
      // Reload table after write
      await loadAddresses()
    } catch (e) {
      console.error('[writeCell] error', e)
      throw e
    }
  }

  const onSend = useCallback(async () => {
    // Intercept direct cell commands when Excel panel is active
    if (excelTemplate) {
      try {
        const text = String(input || '')
        // Supported: "pon 1000 en D2", "pon D2 a 1000", "escribe 1000 en D2"
        const patterns = [
          /pon\s+([\d.,]+)\s+en\s+([A-Za-z]+\d+)/i,
          /pon\s+([A-Za-z]+\d+)\s+a\s+([\d.,]+)/i,
          /escribe\s+([\d.,]+)\s+en\s+([A-Za-z]+\d+)/i,
          /pon(?:\s+el)?\s*valor\s+([\d.,]+)\s+en\s+la\s*casilla\s+([A-Za-z]+\d+)/i,
        ]
        let addr: string | null = null
        let raw: string | null = null
        for (const rx of patterns) {
          const m = text.match(rx)
          if (m) {
            // m could be (value, addr) or (addr, value)
            const a = /[A-Za-z]+\d+/.test(m[1]) ? m[1] : m[2]
            const v = /[A-Za-z]+\d+/.test(m[1]) ? m[2] : m[1]
            addr = a.toUpperCase()
            raw = v
            break
          }
        }
        if (addr && raw) {
          const num = Number(raw.replace(',', '.'))
          const valueToWrite = isNaN(num) ? raw : num
          setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'user', content: input }])
          setInput('')
          try {
            await writeCell(addr, valueToWrite)
            setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: `✅ He escrito ${valueToWrite} en ${addr}` }])
          } catch (e) {
            setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: `❌ Error escribiendo ${addr}: ${String(e)}` }])
          }
          return
        }
      } catch (e) {
        console.error('cell command intercept error', e)
      }
    }

    if (!input.trim() && files.length === 0) return
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', content: input }
    setMessages(prev => [...prev, userMessage])
    setInput('')

    const form = new FormData()
    form.append('text', userMessage.content)
    form.append('session_id', 'web-ui')
    if (propertyId) form.append('property_id', propertyId)
    for (const f of files) form.append('files', f)
    setUploading(true)
    try {
      const resp = await fetch('/api/chat', { method: 'POST', body: form })
      if (!resp.ok) {
        const text = await resp.text().catch(() => '')
        throw new Error(`Request failed: ${resp.status} ${text.slice(0, 200)}`)
      }
      const contentType = resp.headers.get('content-type') || ''
      if (!contentType.includes('application/json')) {
        const text = await resp.text().catch(() => '')
        throw new Error(`Expected JSON but got ${contentType}. Response: ${text.slice(0, 200)}`)
      }
      const data = await resp.json()
      const answer = String(data?.answer ?? '')
      setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: answer }])
      // Post-process: if assistant confirms a write, perform it for real
      try {
        // ejemplos: "valor de 1000 ha sido establecido en la celda D2"
        const m = answer.match(/valor\s+de\s+([\d.,]+).*?celda\s+([A-Za-z]+\d+)/i)
        if (m) {
          const raw = m[1]
          const addr = m[2].toUpperCase()
          const num = Number(raw.replace(',', '.'))
          const valueToWrite = isNaN(num) ? raw : num
          await writeCell(addr, valueToWrite)
        }
      } catch {}

      // Detect numbers template confirmation → open Excel panel
      try {
        const patterns = [
          /✅?\s*Usaremos la plantilla de Números:\s*([^\.\n]+)/i,
          /Usaremos la plantilla de Números:\s*([^\.\n]+)/i,
          /establecido la plantilla de Números (?:como|:)\s*([^\.\n]+)/i,
          /plantilla de Números:\s*([^\.\n]+)/i,
        ]
        for (const pattern of patterns) {
          const m = answer.match(pattern)
          if (m && m[1]) { setExcelTemplate(m[1].trim()); break }
        }
      } catch {}
      
      if (data.property_id) {
        setPropertyId(data.property_id)
        if (data.property_name) setPropertyName(data.property_name)
        }
      setFiles([])
    } catch (e: any) {
      setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: `Error: ${e?.message || String(e)}` }])
    } finally {
      setUploading(false)
    }
  }, [input, files, propertyId])

  // Quick actions: Excel MCP tools
  const quickGetRange = useCallback(async () => {
    const t0 = Date.now()
    const result = await mcpExcel.getRange('A1:B10', undefined, propertyId || undefined)
    setToolLogs(prev => [{ tool: 'excel.get_range', args: { address: 'A1:B10' }, ms: result.ms || (Date.now()-t0), mode: result.mode, result }, ...prev])
    // Prepare human-friendly output
    let content = ''
    if (!result.ok) {
      content = `Leer rango A1:B10 → ERROR: ${result.error?.message || 'unknown'}`
    } else {
      const data = (result as any).data
      if (data && data.values) {
        content = `Leer rango A1:B10 → OK (${result.mode}, ${result.ms}ms)\n` + data.values.map((r: any[]) => r.join(' | ')).join('\n')
      } else if (data && data.values === undefined && data) {
        content = `Leer rango A1:B10 → OK (${result.mode}, ${result.ms}ms)\n` + JSON.stringify(data)
      } else {
        content = `Leer rango A1:B10 → OK (${result.mode}, ${result.ms}ms) - no data returned` 
      }
    }
    setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content }])
  }, [propertyId])

  // Address inspector for Excel iframe: show addresses and values for a range
  const [showAddresses, setShowAddresses] = useState(true)
  const [addressesData, setAddressesData] = useState<any[][] | null>(null)
  const [addressesLoading, setAddressesLoading] = useState(false)
  const [addressesError, setAddressesError] = useState<string | null>(null)
  const [selectedCell, setSelectedCell] = useState<string | null>(null)
  const [excelRefreshKey, setExcelRefreshKey] = useState<number>(0)
  const [worksheetName] = useState<string>('Sheet1')
  // autoSync removed - all changes are saved directly to DB

  const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:7901'
  const panelRef = useRef<HTMLDivElement | null>(null)
  const [zoom, setZoom] = useState<number>(0.85) // 85% default
  const BASE_W = 1600
  const BASE_H = 1000

  const loadAddresses = useCallback(async () => {
    if (!propertyId || !excelTemplate) {
      setAddressesError('No hay propertyId o template seleccionado')
      return
    }
    try {
      setAddressesLoading(true)
      setAddressesError(null)
      console.log('[Numbers Table] loading template', excelTemplate, 'for', propertyId)

      // Load structure from new Numbers Table API
      const structureRes = await fetch(`${BACKEND_URL}/api/numbers/template-structure?property_id=${encodeURIComponent(propertyId)}&template_key=${encodeURIComponent(excelTemplate)}`)
      if (!structureRes.ok) {
        const text = await structureRes.text().catch(() => '')
        throw new Error(`Failed to load structure: ${structureRes.status} ${text.slice(0, 200)}`)
      }
      const contentType = structureRes.headers.get('content-type') || ''
      if (!contentType.includes('application/json')) {
        const text = await structureRes.text().catch(() => '')
        throw new Error(`Expected JSON but got ${contentType}. Response: ${text.slice(0, 200)}`)
      }
      const structureData = await structureRes.json()
      console.log('[Numbers Table] structure response', structureData)
      
      // Handle both response formats: {ok: true, structure: {...}} and direct structure
      let structure = {}
      if (structureData?.ok && structureData?.structure) {
        structure = structureData.structure
      } else if (structureData?.structure) {
        structure = structureData.structure
      } else if (structureData && !structureData.error) {
        // Direct structure object
        structure = structureData
      } else {
        throw new Error(structureData?.error || 'Failed to load structure from database')
      }
      
      console.log('[Numbers Table] parsed structure:', structure, 'keys:', Object.keys(structure))
      
      // Check if structure is empty (template not imported yet)
      if (!structure || Object.keys(structure).length === 0 || !structure.cells || structure.cells.length === 0) {
        console.log('[Numbers Table] Structure is empty, triggering import...')
        console.log('[Numbers Table] Structure keys:', Object.keys(structure))
        setAddressesLoading(true)
        setAddressesError('Importando template desde Excel... Por favor espera.')
        
        // Show file upload prompt
        setAddressesError('Para importar la plantilla R2B, por favor sube el archivo Excel directamente usando el botón "Subir Excel R2B" abajo.')
        setAddressesLoading(false)
        return
      }
      
      console.log('[Numbers Table] structure loaded', structure, 'cells:', structure.cells?.length)

      // Load values from new Numbers Table API
      const valuesRes = await fetch(`${BACKEND_URL}/api/numbers/table-values?property_id=${encodeURIComponent(propertyId)}&template_key=${encodeURIComponent(excelTemplate)}`)
      let cellValues: Record<string, any> = {}
      if (valuesRes.ok) {
        const contentType = valuesRes.headers.get('content-type') || ''
        if (contentType.includes('application/json')) {
          const valuesData = await valuesRes.json()
          if (valuesData?.ok && valuesData?.values) {
            cellValues = valuesData.values
            console.log('[Numbers Table] values loaded', Object.keys(cellValues).length, 'cells')
          }
        } else {
          console.warn('[Numbers Table] Values response is not JSON:', contentType)
        }
      } else {
        console.warn('[Numbers Table] Failed to load values:', valuesRes.status)
      }

      // Build matrix from structure
      const maxRow = structure.rows || 30
      const maxCol = structure.columns || 5
      console.log('[Numbers Table] Building matrix:', maxRow, 'rows x', maxCol, 'cols')
      
      const rows: any[][] = []

      // Create maps for values and formats
      const valueMap: Record<string, string> = {}
      const formatMap: Record<string, any> = {}
      
      for (const [addr, cellData] of Object.entries(cellValues)) {
        if (typeof cellData === 'object' && cellData !== null) {
          valueMap[addr] = (cellData as any).value || ''
          formatMap[addr] = (cellData as any).format || {}
        } else {
          valueMap[addr] = String(cellData || '')
        }
      }
      
      // Also extract formats from structure cells
      if (structure.cells) {
        for (const cellInfo of structure.cells) {
          const addr = cellInfo.address
          if (cellInfo.format && !formatMap[addr]) {
            formatMap[addr] = cellInfo.format
          }
        }
      }
      
      console.log('[Numbers Table] Value map size:', Object.keys(valueMap).length, 'Format map size:', Object.keys(formatMap).length)

      // Build matrix row by row with values and formats
      for (let r = 0; r < maxRow; r++) {
        const row: any[] = []
        for (let c = 0; c < maxCol; c++) {
          // Convert column index to letter (A, B, C, ...)
          const colLetter = (() => {
            let s = ''
            let i = c
            while (i >= 0) {
              s = String.fromCharCode(65 + (i % 26)) + s
              i = Math.floor(i / 26) - 1
            }
            return s
          })()
          const addr = `${colLetter}${r + 1}`
          // Get value from cellValues, or from structure cells if available
          let cellValue = valueMap[addr]
          if (cellValue === undefined) {
            // Check if structure has this cell defined
            const cellInfo = structure.cells?.find((cell: any) => cell.address === addr)
            if (cellInfo) {
              cellValue = cellInfo.value || ''
            } else {
              cellValue = ''
            }
          }
          // Store cell data with format
          row.push({
            value: cellValue,
            format: formatMap[addr] || {},
            address: addr
          })
        }
        rows.push(row)
      }

      console.log('[Numbers Table] Matrix built:', rows.length, 'rows, first row:', rows[0]?.slice(0, 5))
      setAddressesData(rows)
      console.log('[Numbers Table] addressesData set, loading complete')
    } catch (e: any) {
      console.error('[Numbers Table] error', e)
      setAddressesError(String(e?.message || e))
      setAddressesData(null)
    } finally {
      setAddressesLoading(false)
    }
  }, [propertyId, excelTemplate])

  // Auto-load Numbers table when template is selected
  useEffect(() => {
    if (!excelTemplate || !propertyId) return
    // Wait a bit for import to complete, then load table structure and values
    const timer = setTimeout(() => {
      loadAddresses()
    }, 2000) // 2 second delay to allow import to complete
    return () => clearTimeout(timer)
  }, [excelTemplate, propertyId, loadAddresses])

  // Auto-show addresses by default when Excel panel/template is active
  // Reload when template changes (loadAddresses already handles propertyId and excelTemplate)
  useEffect(() => {
    setShowAddresses(true)
  }, [excelTemplate])

  // SSE realtime updates removed - Numbers Table uses direct API calls

  const setCellValue = useCallback(async (addr: string) => {
    setSelectedCell(addr)
    const v = window.prompt(`Valor para ${addr}`)
    if (v === null) return
    const parsed = Number(String(v).replace(',', '.'))
    const valueToWrite = isNaN(parsed) ? v : parsed
    try {
      const resp = await fetch(`${BACKEND_URL}/api/values`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({ property_id: propertyId || '', address: addr, value: String(valueToWrite) })
      })
      if (!resp.ok) {
        const text = await resp.text().catch(() => '')
        setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: `❌ Error escribiendo ${addr}: ${resp.status} ${text.slice(0,200)}` }])
      } else {
        setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: `✅ He escrito ${valueToWrite} en ${addr}` }])
        await loadAddresses()
        // auto sync full matrix if enabled
        // Auto-sync removed - all changes are saved directly to DB
      }
    } catch (e) {
      setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: `❌ Error escribiendo ${addr}: ${String(e)}` }])
    }
  }, [propertyId, loadAddresses])
  const quickSetA1 = useCallback(async () => {
    const t0 = Date.now()
    const result = await mcpExcel.setRange('A1', 'Hola RAMA', undefined, propertyId || undefined)
    setToolLogs(prev => [{ tool: 'excel.set_range', args: { address: 'A1', values: 'Hola RAMA' }, ms: result.ms || (Date.now()-t0), mode: result.mode, result }, ...prev])
    const data = (result as any).data
    const content = result.ok ? `Escribir A1 → OK (${result.mode}, ${result.ms}ms) ${data ? JSON.stringify(data) : ''}` : `Escribir A1 → ERROR: ${result.error?.message || 'unknown'}`
    setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content }])
  }, [propertyId])
  const quickAppend = useCallback(async () => {
    const t0 = Date.now()
    const result = await mcpExcel.appendRow('Tabla1', ['Nueva fila', Date.now()], undefined, propertyId || undefined)
    setToolLogs(prev => [{ tool: 'excel.append_row', args: { tableName: 'Tabla1', values: ['Nueva fila', Date.now()] }, ms: result.ms || (Date.now()-t0), mode: result.mode, result }, ...prev])
    const data = (result as any).data
    const content = result.ok ? `Añadir fila a Tabla1 → OK (${result.mode}, ${result.ms}ms) ${data ? JSON.stringify(data) : ''}` : `Añadir fila a Tabla1 → ERROR: ${result.error?.message || 'unknown'}`
    setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content }])
  }, [propertyId])
  // clearOldTemplate removed per request

  const startRecording = useCallback(async () => {
    if (isRecording) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000
        } 
      })
      // Try to use WAV format first, fallback to WebM if not supported
      let mimeType = 'audio/wav'
      if (!MediaRecorder.isTypeSupported('audio/wav')) {
        mimeType = 'audio/webm;codecs=opus'
      }
      const mr = new MediaRecorder(stream, { mimeType })
      mediaRecorderRef.current = mr
      chunksRef.current = []
      
      mr.ondataavailable = (e) => { 
        if (e.data.size) chunksRef.current.push(e.data) 
      }
      
      mr.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: mimeType })
        await processVoiceInput(blob)
        stream.getTracks().forEach(track => track.stop())
      }
      
      mr.start(100) // Collect data every 100ms
      setIsRecording(true)
    } catch (err) {
      console.error('Error starting recording:', err)
      alert('No se pudo acceder al micrófono. Por favor, verifica los permisos.')
    }
  }, [isRecording])

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      mediaRecorderRef.current = null
      setIsRecording(false)
    }
  }, [isRecording])

  const processVoiceInput = useCallback(async (audioBlob: Blob) => {
    setIsProcessingVoice(true)
    try {
      const form = new FormData()
      const fileExtension = audioBlob.type.includes('wav') ? 'wav' : 'webm'
      form.append('audio', audioBlob, `voice-input.${fileExtension}`)
      form.append('text', '') // Empty text for voice input
      form.append('session_id', 'web-ui')
      // Include property_id if we have one
      if (propertyId) {
        form.append('property_id', propertyId)
      }

      const response = await fetch('/api/chat', {
        method: 'POST',
        body: form,
      })

      const data = await response.json()
      
      if (data.error) {
        throw new Error(data.error)
      }

      // Add transcribed message to chat
      if (data.transcript) {
        const userMessage: ChatMessage = { 
          id: crypto.randomUUID(), 
          role: 'user', 
          content: data.transcript 
        }
        setMessages(prev => [...prev, userMessage])
      }

      // Add AI response
      if (data.answer) {
        const aiMessage: ChatMessage = { 
          id: crypto.randomUUID(), 
          role: 'assistant', 
          content: data.answer 
        }
        setMessages(prev => [...prev, aiMessage])
        // Detect numbers template confirmation → open Excel panel
        try {
          // Match "✅ Usaremos la plantilla de Números: [template]" or "Usaremos la plantilla de Números: [template]"
          // Also match variations like "Ya hemos establecido la plantilla de Números como [template]"
          const patterns = [
            /✅?\s*Usaremos la plantilla de Números:\s*([^\.\n]+)/i,
            /Usaremos la plantilla de Números:\s*([^\.\n]+)/i,
            /establecido la plantilla de Números (?:como|:)\s*([^\.\n]+)/i,
            /plantilla de Números:\s*([^\.\n]+)/i,
          ]
          for (const pattern of patterns) {
            const m = String(data.answer).match(pattern)
            if (m && m[1]) {
              const template = m[1].trim()
              setExcelTemplate(template)
              console.log('[Frontend] Excel template detected:', template)
              // Set focus to "numbers" when Excel opens
              if (propertyId) {
                fetch('/api/chat', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                  body: new URLSearchParams({
                    text: 'números',
                    session_id: 'web-ui',
                    property_id: propertyId,
                  }),
                }).catch(() => {}) // Silent fail - just trying to set focus
              }
              break
            }
          }
        } catch {}
        
        // Update property_id if backend sent it back
        if (data.property_id) {
          setPropertyId(data.property_id)
          // Use property_name from backend directly
          if (data.property_name) {
            setPropertyName(data.property_name)
          }
        }
      }

    } catch (error) {
      console.error('Error processing voice input:', error)
      const errorMessage: ChatMessage = { 
        id: crypto.randomUUID(), 
        role: 'assistant', 
        content: 'Lo siento, hubo un error procesando tu mensaje de voz. Por favor, intenta de nuevo.' 
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsProcessingVoice(false)
    }
  }, [propertyId])

  const removeFile = useCallback((idx: number) => {
    setFiles(prev => prev.filter((_, i) => i !== idx))
  }, [])

  const filePreviews = useMemo(() => files.map((f, i) => (
    <div key={i} className="flex items-center justify-between gap-3 rounded-2xl border-2 border-[color:var(--c-green-300)] glass px-4 py-3 text-sm nature-shadow">
      <span className="truncate max-w-[16rem] font-medium text-[color:var(--c-green-800)]" title={f.name}>
        📄 {f.name}
      </span>
      <button onClick={() => removeFile(i)} className="rounded-xl px-3 py-1.5 text-[color:var(--c-green-700)] hover:bg-[color:var(--c-green-200)] font-semibold transition-all hover:scale-105">
        ✕
      </button>
    </div>
  )), [files, removeFile])

  // Render assistant/user message with lightweight markdown, media embeds and a clear callout
  const renderMessageContent = useCallback((text: string) => {
    if (!text) return null
    
    // Extract markdown links to images/documents first so we can render them as blocks
    let processedText = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+?\.(?:png|jpg|jpeg|gif|webp)(?:\?[^\s)]*)?)\)/gi, (_m, _t, url) => `\n${url}\n`)
    processedText = processedText.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+?\.(?:pptx|xlsx|pdf|docx)(?:\?[^\s)]*)?)\)/gi, (_m, _t, url) => `\n${url}\n`)
    const fileRegex = /(https?:\/\/[^\s]+?\.(?:png|jpg|jpeg|gif|webp|pptx|xlsx|pdf|docx)(?:\?[^\s]*)?)/gi
    const parts = processedText.split(fileRegex)
    const nodes: React.ReactNode[] = []

    // Inline bold **text** helper
    const renderInline = (s: string) => {
      const bits: React.ReactNode[] = []
      const boldRegex = /\*\*([^*]+)\*\*/g
      let lastIndex = 0
      let m: RegExpExecArray | null
      while ((m = boldRegex.exec(s)) !== null) {
        if (m.index > lastIndex) bits.push(s.slice(lastIndex, m.index))
        bits.push(<strong key={`b-${m.index}`} className="font-semibold">{m[1]}</strong>)
        lastIndex = m.index + m[0].length
      }
      if (lastIndex < s.length) bits.push(s.slice(lastIndex))
      return bits
    }

    // Very light markdown for headings and lists
    const renderMarkdown = (block: string) => {
      const lines = block.split(/\n/)
      const out: React.ReactNode[] = []
      let listType: 'ul' | 'ol' | null = null
      let listItems: string[] = []
      const flush = () => {
        if (!listType || listItems.length === 0) return
        if (listType === 'ul') {
          out.push(
            <ul key={`ul-${out.length}`} className="list-disc pl-6 space-y-1">
              {listItems.map((li, i) => (<li key={i}>{renderInline(li)}</li>))}
            </ul>
          )
        } else {
          out.push(
            <ol key={`ol-${out.length}`} className="list-decimal pl-6 space-y-1">
              {listItems.map((li, i) => (<li key={i}>{renderInline(li)}</li>))}
            </ol>
          )
        }
        listType = null
        listItems = []
      }
      for (const raw of lines) {
        const line = raw.trimEnd()
        if (!line.trim()) { flush(); out.push(<div key={`sp-${out.length}`} className="h-2" />); continue }
        if (line.startsWith('### ')) { flush(); out.push(<div key={`h3-${out.length}`} className="mt-3 mb-2 text-[color:var(--c-green-800)] font-extrabold text-[18px]">{renderInline(line.slice(4))}</div>); continue }
        if (line.startsWith('## '))  { flush(); out.push(<div key={`h2-${out.length}`} className="mt-3 mb-2 text-[color:var(--c-green-800)] font-extrabold text-[20px]">{renderInline(line.slice(3))}</div>); continue }
        if (/^\d+\./.test(line)) { if (listType !== 'ol') { flush(); listType = 'ol' } listItems.push(line.replace(/^\d+\.\s*/, '')); continue }
        if (line.startsWith('- ')) { if (listType !== 'ul') { flush(); listType = 'ul' } listItems.push(line.slice(2)); continue }
        flush();
        out.push(<p key={`p-${out.length}`} className="leading-relaxed">{renderInline(line)}</p>)
      }
      flush()
      return out
    }

    // Callout: emphasize the "choose one of II/III/IV" rule whenever present
    if (/elegir\s+una\s+entre\s+ii\/iii\/iv/i.test(processedText)) {
      nodes.push(
        <div key="callout-optional" className="mb-3 rounded-2xl border-2 border-amber-300 bg-amber-50 px-4 py-3 text-amber-900 font-semibold flex items-start gap-3 nature-shadow">
          <span>⚠️</span>
          <span>Completa SOLO UNA de las secciones opcionales: II, III o IV. Dime cuál y te guiaré paso a paso.</span>
        </div>
      )
    }

    for (let i = 0; i < parts.length; i++) {
      const token = parts[i]
      if (!token) continue
      const isImg = /^(https?:\/\/[^\s]+?\.(?:png|jpg|jpeg|gif|webp)(?:\?[^\s]*)?)$/i.test(token)
      const isDoc = /^(https?:\/\/[^\s]+?\.(?:pptx|xlsx|pdf|docx)(?:\?[^\s]*)?)$/i.test(token)
      if (isImg) {
        nodes.push(
          <div key={`img-${i}`} className="mt-3 mb-3">
            <img src={token} alt="gráfico" className="max-w-full max-h-[500px] rounded-xl border border-[color:var(--c-green-200)] shadow-lg" />
          </div>
        )
      } else if (isDoc) {
        const ext = token.match(/\.(pptx|xlsx|pdf|docx)/i)?.[1]?.toUpperCase() || 'FILE'
        const filename = token.match(/\/([^/?]+\.(pptx|xlsx|pdf|docx))/i)?.[1] || `archivo.${ext.toLowerCase()}`
        nodes.push(
          <div key={`doc-${i}`} className="mt-3 inline-block">
            <a 
              href={token} 
              download={filename}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-gradient-to-br from-[color:var(--c-green-600)] to-[color:var(--c-green-700)] text-white font-semibold hover:scale-105 transition-all nature-shadow hover:shadow-xl"
            >
              <span>📄</span>
              <span>Descargar {ext}</span>
            </a>
          </div>
        )
      } else {
        nodes.push(<div key={`md-${i}`} className="space-y-1">{renderMarkdown(token)}</div>)
      }
    }
    return <>{nodes}</>
  }, [])

  const excelUrl = useMemo(() => {
    if (!excelTemplate) return ''
    const map: Record<string, string | undefined> = {
      'R2B': process.env.NEXT_PUBLIC_EXCEL_EMBED_R2B,
      'R2B + PM': process.env.NEXT_PUBLIC_EXCEL_EMBED_R2B_PM,
      'R2B + PM + Venta certs': process.env.NEXT_PUBLIC_EXCEL_EMBED_R2B_PM_VENTA,
      'Promoción': process.env.NEXT_PUBLIC_EXCEL_EMBED_PROMOCION,
      'Promocion': process.env.NEXT_PUBLIC_EXCEL_EMBED_PROMOCION,
    }
    const raw = map[excelTemplate] || ''
    if (!raw) return ''
    try {
      const u = new URL(raw)
      u.searchParams.set('wdAllowInteractivity', 'True')
      return u.toString()
    } catch {
      return raw.replace(/wdAllowInteractivity=\w+/i, 'wdAllowInteractivity=True')
    }
  }, [excelTemplate])

  const ExcelPanel = useMemo(() => {
    if (!excelTemplate) return null
    if (!excelUrl) {
      return (
        <div className="rounded-2xl border-2 border-amber-300 bg-amber-50 px-4 py-3 text-amber-900 nature-shadow">
          <div className="flex items-start justify-between">
            <div className="pr-4">
              <div className="font-bold mb-1">Excel para "{excelTemplate}"</div>
              <div>
                Falta configurar la URL de incrustación. Añade las variables de entorno en el frontend y reinicia `npm run dev`:
                <pre className="mt-2 whitespace-pre-wrap text-sm bg-white/70 p-2 rounded">NEXT_PUBLIC_EXCEL_EMBED_R2B=...
NEXT_PUBLIC_EXCEL_EMBED_R2B_PM=...
NEXT_PUBLIC_EXCEL_EMBED_R2B_PM_VENTA=...
NEXT_PUBLIC_EXCEL_EMBED_PROMOCION=...</pre>
                Acepta URLs públicas de Excel Online (OneDrive/SharePoint) o Google Sheets (publish/embed).
              </div>
            </div>
            <button onClick={() => setExcelTemplate(null)} className="px-3 py-1 rounded-lg bg-amber-100 hover:bg-amber-200 text-amber-900 font-semibold">Cerrar</button>
          </div>
        </div>
      )
    }
    return (
      <div className="rounded-3xl border-2 border-[color:var(--c-green-400)] bg-white/95 backdrop-blur-sm shadow-2xl overflow-hidden transition-all duration-300 hover:shadow-3xl flex flex-col h-auto max-h-[80vh] min-h-0">
        {/* Header with gradient and better styling */}
        <div className="flex items-center justify-between px-6 py-4 bg-gradient-to-r from-[color:var(--c-green-600)] to-[color:var(--c-green-700)] text-white flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <span className="text-2xl">📊</span>
            </div>
            <div>
              <div className="font-bold text-lg">Excel — {excelTemplate}</div>
              <div className="text-xs text-white/80 mt-0.5">Actualización en tiempo real vía chat</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <a 
              href={excelUrl} 
              target="_blank" 
              rel="noreferrer" 
              className="px-4 py-2 rounded-xl bg-white/20 hover:bg-white/30 backdrop-blur-sm text-white font-semibold transition-all duration-200 hover:scale-105 flex items-center gap-2"
            >
              <span>🔗</span>
              <span>Abrir en pestaña</span>
            </a>
            <div className="hidden md:flex items-center gap-1 bg-white/20 rounded-lg px-1 py-0.5">
              <button onClick={() => setZoom(z => Math.max(0.4, Math.round((z-0.1)*100)/100))} className="px-2 py-1 text-white/90 hover:text-white">−</button>
              <button onClick={() => setZoom(1)} className="px-2 py-1 text-white/90 hover:text-white">100%</button>
              <button onClick={() => {
                const box = panelRef.current
                if (!box) return
                const w = box.clientWidth - 24
                const h = box.clientHeight - 24
                const fit = Math.min(w/BASE_W, h/BASE_H)
                setZoom(Math.max(0.4, Math.min(1.2, Math.round(fit*100)/100)))
              }} className="px-2 py-1 text-white/90 hover:text-white">Ajustar</button>
              <button onClick={() => setZoom(z => Math.min(1.2, Math.round((z+0.1)*100)/100))} className="px-2 py-1 text-white/90 hover:text-white">＋</button>
            </div>
            <button 
              onClick={() => setExcelRefreshKey(Date.now())}
              className="px-4 py-2 rounded-xl bg-white/20 hover:bg-white/30 backdrop-blur-sm text-white font-semibold transition-all duration-200 hover:scale-105"
            >
              ↻ Recargar
            </button>
            <button 
              onClick={() => setExcelTemplate(null)} 
              className="px-4 py-2 rounded-xl bg-white/20 hover:bg-white/30 backdrop-blur-sm text-white font-semibold transition-all duration-200 hover:scale-105"
            >
              ✕
            </button>
          </div>
        </div>
        
        {/* Excel iframe - shows actual Excel from OneDrive */}
        <div className="relative bg-gray-50 flex-1 flex flex-col min-h-0">
          <div className="absolute top-2 right-2 z-10 px-3 py-1.5 rounded-lg bg-[color:var(--c-green-100)] text-[color:var(--c-green-800)] text-xs font-semibold flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[color:var(--c-green-500)] animate-pulse"></span>
            <span>Sincronizado</span>
          </div>
          {/** Replace iframe with in-app Spreadsheet for realtime editing */}
          {excelUrl ? (
            // Show mirrored in-app Spreadsheet for realtime editing/viewing
            <div className="relative w-full h-[70vh] flex flex-col">
              <div className="flex-1 overflow-auto p-4">
                {addressesData ? (
                  <Spreadsheet
                    data={addressesData}
                    addressRange={addressRange}
                    selected={selectedCell}
                    showAddresses={false}
                    onCellClick={(addr) => {
                      setSelectedCell(addr)
                      setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: `Seleccionada: ${addr}` }])
                    }}
                  />
                ) : addressesError ? (
                  <div className={`p-4 ${addressesError.includes('Error') || addressesError.includes('expir') || addressesError.includes('inválido') ? 'text-red-600' : 'text-[color:var(--c-green-700)]'}`}>
                    <div className="font-semibold mb-2">
                      {addressesError.includes('Error') || addressesError.includes('expir') || addressesError.includes('inválido') ? 'Error:' : 'Importando...'}
                    </div>
                    <div className="whitespace-pre-wrap">{addressesError}</div>
                    {(addressesError.includes('Error') || addressesError.includes('expir') || addressesError.includes('inválido')) && (
                      <button 
                        onClick={() => loadAddresses()} 
                        className="mt-2 px-3 py-1 rounded bg-[color:var(--c-green-700)] text-white text-sm"
                      >
                        Reintentar
                      </button>
                    )}
                  </div>
                ) : addressesLoading ? (
                  <div className="text-[color:var(--c-green-700)] flex items-center justify-center h-full">
                    <div className="text-center">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[color:var(--c-green-600)] mx-auto mb-2"></div>
                      <div>Cargando datos...</div>
                    </div>
                  </div>
                ) : (
                  <div className="text-[color:var(--c-green-700)] flex items-center justify-center h-full">
                    <div className="text-center p-8">
                      <div className="text-4xl mb-4">📊</div>
                      <div className="font-semibold mb-2">Sube el archivo Excel R2B</div>
                      <div className="text-sm text-[color:var(--c-green-600)]">
                        Haz clic en "Subir Excel R2B" para comenzar
                      </div>
                    </div>
                  </div>
                )}
              </div>
              <div className="px-4 py-2 bg-white border-t flex gap-2 items-center justify-between">
                <div className="flex gap-2 items-center">
                  <input 
                    type="file" 
                    accept=".xlsx,.xls" 
                    id="excel-upload-input"
                    style={{ display: 'none' }}
                    onChange={async (e) => {
                      const file = e.target.files?.[0]
                      if (!file || !propertyId || !excelTemplate) return
                      
                      setAddressesLoading(true)
                      setAddressesError('Subiendo y procesando archivo Excel...')
                      
                      try {
                        const formData = new FormData()
                        formData.append('property_id', propertyId)
                        formData.append('template_key', excelTemplate)
                        formData.append('excel_file', file, file.name)
                        
                        const res = await fetch(`${BACKEND_URL}/api/numbers/import-template`, {
                          method: 'POST',
                          body: formData
                        })
                        
                        const data = await res.json()
                        
                        if (data?.ok) {
                          setAddressesError(null)
                          setAddressesLoading(true) // Keep loading while we fetch the data
                          // Reload addresses immediately after successful import
                          console.log('[Numbers Table] Import successful, reloading addresses...')
                          await loadAddresses()
                        } else {
                          setAddressesError(`Error: ${data?.error || 'Error desconocido'}`)
                          setAddressesLoading(false)
                        }
                      } catch (err: any) {
                        setAddressesError(`Error al subir archivo: ${err?.message || String(err)}`)
                        setAddressesLoading(false)
                      }
                      
                      // Reset input
                      e.target.value = ''
                    }}
                  />
                  <label 
                    htmlFor="excel-upload-input"
                    className="px-4 py-2 rounded bg-[color:var(--c-green-600)] text-white cursor-pointer hover:bg-[color:var(--c-green-700)] font-semibold"
                  >
                    📤 Subir Excel R2B
                  </label>
                </div>
                
                {addressesData && (
                  <button
                    onClick={async () => {
                      if (!propertyId || !excelTemplate) return
                      try {
                        setAddressesLoading(true)
                        const res = await fetch(`${BACKEND_URL}/api/numbers/export?property_id=${encodeURIComponent(propertyId)}&template_key=${encodeURIComponent(excelTemplate)}`)
                        if (!res.ok) {
                          setAddressesError(`Error al exportar: ${res.status}`)
                          setAddressesLoading(false)
                          return
                        }
                        const blob = await res.blob()
                        const url = window.URL.createObjectURL(blob)
                        const a = document.createElement('a')
                        a.href = url
                        a.download = `numbers_table_${excelTemplate}_${propertyId.slice(0, 8)}.xlsx`
                        document.body.appendChild(a)
                        a.click()
                        window.URL.revokeObjectURL(url)
                        document.body.removeChild(a)
                        setAddressesLoading(false)
                      } catch (err: any) {
                        setAddressesError(`Error al exportar: ${err?.message || String(err)}`)
                        setAddressesLoading(false)
                      }
                    }}
                    className="px-4 py-2 rounded bg-[color:var(--c-green-600)] text-white hover:bg-[color:var(--c-green-700)] font-semibold"
                  >
                    📥 Exportar Excel
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-[color:var(--c-green-700)]">
              <div className="text-center p-8">
                <div className="text-4xl mb-4">📊</div>
                <div className="font-semibold mb-2">Excel no configurado</div>
                <div className="text-sm text-[color:var(--c-green-600)]">
                  Falta configurar la URL de Excel en .env.local
                </div>
              </div>
            </div>
          )}
        </div>
        
        {/* Footer with helpful hints - compact */}
        <div className="px-4 py-2 bg-gradient-to-r from-[color:var(--c-green-50)] to-[color:var(--c-green-100)] border-t border-[color:var(--c-green-200)] flex-shrink-0">
          <div className="text-xs text-[color:var(--c-green-700)] flex items-center gap-2">
            <span>💡</span>
            <span>Di "pon [campo] a [valor]" o "borra [campo]"</span>
          </div>
        </div>
      </div>
    )
  }, [excelTemplate, excelUrl, excelRefreshKey])

  // Layout: two columns when Excel is open, single column otherwise
  const hasExcel = !!excelTemplate

  return (
    <div className="flex h-[calc(100vh-140px)] flex-col gap-3">
      {/* Property indicator */}
      {propertyName && (
        <div className="rounded-2xl bg-gradient-to-r from-[color:var(--c-green-600)] to-[color:var(--c-green-700)] px-5 py-3 text-white font-semibold nature-shadow-lg flex items-center gap-3">
          <span className="text-xl">🏡</span>
          <span>Propiedad actual: {propertyName}</span>
        </div>
      )}
      
      {/* Main content area: split layout when Excel is open */}
      <div className={`flex-1 flex gap-4 ${hasExcel ? 'flex-row' : 'flex-col'}`}>
        {/* Excel Panel - Left side when open (larger) */}
        {hasExcel && (
          <div className="flex-[7] flex flex-col min-w-0">
            {ExcelPanel}
          </div>
        )}
        
        {/* Chat area - Right side when Excel is open (smaller), full width otherwise */}
        <div className={`${hasExcel ? 'flex-[2] flex-shrink-0 h-[70vh]' : 'flex-1'} flex flex-col min-h-0`}>
          <div ref={scrollRef} className="flex-1 overflow-auto rounded-3xl p-6 glass nature-shadow-lg scrollbar-thin">
            {!hasExcel && ExcelPanel}
            {hasExcel && (
              <>
                {/* Quick actions for MCP excel tools (visible only when completing a Numbers template) */}
                <div className="mb-4 flex flex-wrap gap-2 items-center">
                  <button onClick={quickGetRange} className="rounded-xl px-3 py-1.5 bg-[color:var(--c-green-600)] text-white text-sm font-semibold">Leer A1:B10</button>
                  <button onClick={quickSetA1} className="rounded-xl px-3 py-1.5 bg-[color:var(--c-green-600)] text-white text-sm font-semibold">Escribir A1</button>
                  <button onClick={quickAppend} className="rounded-xl px-3 py-1.5 bg-[color:var(--c-green-600)] text-white text-sm font-semibold">Añadir fila a Tabla1</button>
                  {selectedCell && (
                    <div className="ml-3 px-3 py-1 rounded bg-[color:var(--c-green-50)] text-[color:var(--c-green-700)] font-medium">Seleccionada: {selectedCell}</div>
                  )}
                </div>

                {toolLogs.length > 0 && (
                  <div className="mb-4 rounded-2xl border-2 border-[color:var(--c-green-200)] bg-white p-3 text-xs text-[color:var(--c-green-900)]">
                    <div className="font-bold mb-1">Logs de tools</div>
                    <div className="space-y-2 max-h-48 overflow-auto">
                      {toolLogs.map((l, i) => (
                        <div key={i} className="border-b last:border-b-0 pb-1">
                          <div className="font-semibold">{l.tool} <span className="opacity-70">({l.mode}, {l.ms}ms)</span></div>
                          <div className="opacity-80">args: {JSON.stringify(l.args)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
            {messages.length === 0 ? (
          <div className="text-center text-[color:var(--c-green-800)]">
            <div className="mb-4 text-5xl animate-pulse-soft">🌾</div>
            <div className="mb-3 text-3xl font-bold bg-gradient-to-r from-[color:var(--c-green-700)] to-[color:var(--c-green-600)] bg-clip-text text-transparent">
              ¡Bienvenido a RAMA Country Living!
            </div>
            <div className="opacity-80 text-lg mb-8 text-[color:var(--c-green-700)]">
              Tu asistente inteligente para gestionar propiedades rurales
            </div>
            <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-5 max-w-4xl mx-auto">
              {/* Crear ficha propiedad */}
              <div className="field-card h-auto min-h-[90px] rounded-3xl border-2 border-[color:var(--c-green-200)] text-left p-5 nature-shadow cursor-pointer shine-effect">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-12 h-12 rounded-2xl bg-gradient-to-br from-[color:var(--c-green-400)] to-[color:var(--c-green-500)] flex items-center justify-center text-2xl nature-shadow">
                    🏡
                  </div>
                  <div className="flex-1">
                    <div className="text-[17px] font-bold leading-5 text-[color:var(--c-green-800)] mb-1">
                      Crear ficha propiedad
                    </div>
                    <div className="text-[13px] text-[color:var(--c-green-600)] leading-relaxed">
                      Añade nuevas propiedades al sistema
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Gestión documentos */}
              <div className="field-card h-auto min-h-[90px] rounded-3xl border-2 border-[color:var(--c-green-200)] text-left p-5 nature-shadow cursor-pointer shine-effect" title="Al entrar en Números, verás la plantilla + acciones (calcular, what-if, break-even, sensibilidad, gráficos, Excel)">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-12 h-12 rounded-2xl bg-gradient-to-br from-[color:var(--c-sage-400)] to-[color:var(--c-sage-500)] flex items-center justify-center text-2xl nature-shadow">
                    📁
                  </div>
                  <div className="flex-1">
                    <div className="text-[17px] font-bold leading-5 text-[color:var(--c-green-800)] mb-1">
                      Gestión de documentos / Números
                    </div>
                    <div className="text-[13px] text-[color:var(--c-green-600)] leading-relaxed">
                      Sube documentos o entra en el framework de números
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Consultas inteligentes */}
              <div className="field-card h-auto min-h-[90px] rounded-3xl border-2 border-[color:var(--c-green-200)] text-left p-5 nature-shadow cursor-pointer shine-effect">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-12 h-12 rounded-2xl bg-gradient-to-br from-[color:var(--c-green-300)] to-[color:var(--c-green-400)] flex items-center justify-center text-2xl nature-shadow">
                    🤖
                  </div>
                  <div className="flex-1">
                    <div className="text-[17px] font-bold leading-5 text-[color:var(--c-green-800)] mb-1">
                      Consultas inteligentes
                    </div>
                    <div className="text-[13px] text-[color:var(--c-green-600)] leading-relaxed">
                      Pregunta sobre tus documentos
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Email automatizado */}
              <div className="field-card h-auto min-h-[90px] rounded-3xl border-2 border-[color:var(--c-green-200)] text-left p-5 nature-shadow cursor-pointer shine-effect">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-12 h-12 rounded-2xl bg-gradient-to-br from-[color:var(--c-earth-300)] to-[color:var(--c-earth-400)] flex items-center justify-center text-2xl nature-shadow">
                    ✉️
                  </div>
                  <div className="flex-1">
                    <div className="text-[17px] font-bold leading-5 text-[color:var(--c-green-800)] mb-1">
                      Email automatizado
                    </div>
                    <div className="text-[13px] text-[color:var(--c-green-600)] leading-relaxed">
                      Envía información por correo
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Resúmenes automáticos */}
              <div className="field-card h-auto min-h-[90px] rounded-3xl border-2 border-[color:var(--c-green-200)] text-left p-5 nature-shadow cursor-pointer shine-effect">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-12 h-12 rounded-2xl bg-gradient-to-br from-[color:var(--c-green-500)] to-[color:var(--c-green-600)] flex items-center justify-center text-2xl nature-shadow">
                    📊
                  </div>
                  <div className="flex-1">
                    <div className="text-[17px] font-bold leading-5 text-[color:var(--c-green-800)] mb-1">
                      Resúmenes automáticos
                    </div>
                    <div className="text-[13px] text-[color:var(--c-green-600)] leading-relaxed">
                      Analiza contratos al instante
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Recordatorios */}
              <div className="field-card h-auto min-h-[90px] rounded-3xl border-2 border-[color:var(--c-green-200)] text-left p-5 nature-shadow cursor-pointer shine-effect">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-12 h-12 rounded-2xl bg-gradient-to-br from-[color:var(--c-earth-400)] to-[color:var(--c-earth-500)] flex items-center justify-center text-2xl nature-shadow">
                    🔔
                  </div>
                  <div className="flex-1">
                    <div className="text-[17px] font-bold leading-5 text-[color:var(--c-green-800)] mb-1">
                      Recordatorios inteligentes
                    </div>
                    <div className="text-[13px] text-[color:var(--c-green-600)] leading-relaxed">
                      No olvides fechas de pago importantes
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-5">
            {messages.map(m => (
              <div key={m.id} className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
                <div className={
                  'max-w-[85%] whitespace-pre-wrap rounded-3xl px-6 py-4 nature-shadow-lg ' +
                  (m.role === 'user'
                    ? 'bg-gradient-to-br from-[color:var(--c-green-600)] to-[color:var(--c-green-700)] text-white font-medium'
                    : 'glass border-2 border-[color:var(--c-green-200)] text-[color:var(--c-green-900)]')
                }>
                  {m.role === 'assistant' ? renderMessageContent(m.content) : m.content}
                </div>
              </div>
            ))}
          </div>
        )}
          </div>
          
          {/* Drop zone - Inside chat area when Excel is open */}
          {hasExcel && (
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={onDrop}
              className="mt-3 rounded-2xl border-2 border-dashed border-[color:var(--c-green-400)] glass-strong p-4 text-[color:var(--c-green-800)] nature-shadow"
            >
              <div className="flex items-center justify-between">
                <div className="font-semibold text-sm flex items-center gap-2">
                  <span className="text-lg">📎</span>
                  <span>Arrastra PDFs</span>
                </div>
                <label className="cursor-pointer rounded-xl bg-gradient-to-br from-[color:var(--c-green-600)] to-[color:var(--c-green-700)] px-4 py-2 text-white text-sm font-semibold nature-shadow hover:scale-105 transition-all duration-200">
                  Archivos
                  <input type="file" multiple className="hidden" onChange={(e) => setFiles(prev => [...prev, ...Array.from(e.target.files || [])])} />
                </label>
              </div>
              {files.length > 0 && (
                <div className="mt-3 grid grid-cols-1 gap-2">
                  {filePreviews}
                </div>
              )}
              {/* removed inspector of addresses to show only the real Excel */}
            </div>
          )}
          
          {/* Composer - Inside chat area when Excel is open */}
          {hasExcel && (
            <div className="sticky bottom-0 mt-3 flex items-end gap-2 rounded-2xl p-3 glass-strong nature-shadow-lg backdrop-blur bg-white/60">
              <button
                onMouseDown={startRecording}
                onMouseUp={stopRecording}
                onTouchStart={startRecording}
                onTouchEnd={stopRecording}
                disabled={isProcessingVoice}
                className={
                  `${hasExcel ? 'h-10 w-10' : 'h-14 w-14'} shrink-0 rounded-full border-2 border-[color:var(--c-green-400)] nature-shadow transition-all duration-300 ` +
                  (isRecording 
                    ? 'bg-gradient-to-br from-[color:var(--c-green-600)] to-[color:var(--c-green-700)] text-white scale-110 animate-pulse' 
                    : isProcessingVoice
                    ? 'bg-gradient-to-br from-[color:var(--c-green-500)] to-[color:var(--c-green-600)] text-white animate-pulse'
                    : 'bg-gradient-to-br from-white to-[color:var(--c-green-50)] text-[color:var(--c-green-800)] hover:from-[color:var(--c-green-100)] hover:to-[color:var(--c-green-200)] hover:scale-105')
                }
              >
                <span className={hasExcel ? 'text-base' : 'text-xl'}>
                  {isRecording ? '⏺' : isProcessingVoice ? '⏳' : '🎤'}
                </span>
              </button>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Escribe tu mensaje..."
                rows={1}
                className="min-h-[40px] flex-1 resize-none rounded-xl border-2 border-[color:var(--c-green-300)] bg-white px-3 py-2 text-sm font-medium outline-none focus:ring-2 focus:ring-[color:var(--c-green-500)] focus:border-[color:var(--c-green-500)] transition-all duration-200 placeholder:text-[color:var(--c-green-400)]"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    onSend()
                  }
                }}
              />
              <button
                onClick={onSend}
                disabled={uploading}
                className="h-10 shrink-0 rounded-xl bg-gradient-to-br from-[color:var(--c-green-600)] to-[color:var(--c-green-700)] px-4 text-white text-sm font-bold nature-shadow hover:scale-105 transition-all duration-200 disabled:opacity-60 disabled:hover:scale-100"
              >
                {uploading ? '⏳' : '✈️'}
              </button>
            </div>
          )}
        </div>
      </div>
      
      {/* Drop zone - Outside chat area when Excel is NOT open */}
      {!hasExcel && (
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDrop}
          className="rounded-3xl border-2 border-dashed border-[color:var(--c-green-400)] glass-strong p-6 text-[color:var(--c-green-800)] nature-shadow hover:nature-shadow-lg transition-all duration-300 hover:border-[color:var(--c-green-500)]"
        >
          <div className="flex items-center justify-between">
            <div className="font-bold text-lg flex items-center gap-3">
              <span className="text-2xl">📎</span>
              <span>Arrastra PDFs aquí o haz click</span>
            </div>
            <label className="cursor-pointer rounded-2xl bg-gradient-to-br from-[color:var(--c-green-600)] to-[color:var(--c-green-700)] px-6 py-3 text-white font-semibold nature-shadow-lg hover:scale-105 transition-all duration-200 shine-effect">
              Elegir archivos
              <input type="file" multiple className="hidden" onChange={(e) => setFiles(prev => [...prev, ...Array.from(e.target.files || [])])} />
            </label>
          </div>
          {files.length > 0 && (
            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
              {filePreviews}
            </div>
          )}
        </div>
      )}

      {/* Composer - Outside chat area when Excel is NOT open */}
      {!hasExcel && (
        <div className="flex items-end gap-4 rounded-3xl p-5 glass-strong nature-shadow-lg">
          <button
            onMouseDown={startRecording}
            onMouseUp={stopRecording}
            onTouchStart={startRecording}
            onTouchEnd={stopRecording}
            disabled={isProcessingVoice}
            className={
              'h-14 w-14 shrink-0 rounded-full border-2 border-[color:var(--c-green-400)] nature-shadow transition-all duration-300 ' +
              (isRecording 
                ? 'bg-gradient-to-br from-[color:var(--c-green-600)] to-[color:var(--c-green-700)] text-white scale-110 animate-pulse' 
                : isProcessingVoice
                ? 'bg-gradient-to-br from-[color:var(--c-green-500)] to-[color:var(--c-green-600)] text-white animate-pulse'
                : 'bg-gradient-to-br from-white to-[color:var(--c-green-50)] text-[color:var(--c-green-800)] hover:from-[color:var(--c-green-100)] hover:to-[color:var(--c-green-200)] hover:scale-105')
            }
            title={
              isRecording 
                ? 'Suelta para detener' 
                : isProcessingVoice 
                ? 'Procesando mensaje de voz...' 
                : 'Mantén para grabar voz'
            }
          >
            <span className="text-xl">
              {isRecording ? '⏺' : isProcessingVoice ? '⏳' : '🎤'}
            </span>
          </button>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Escribe tu mensaje sobre propiedades..."
            rows={1}
            className="min-h-[56px] flex-1 resize-none rounded-2xl border-2 border-[color:var(--c-green-300)] bg-white px-5 py-4 text-base font-medium outline-none focus:ring-2 focus:ring-[color:var(--c-green-500)] focus:border-[color:var(--c-green-500)] transition-all duration-200 placeholder:text-[color:var(--c-green-400)]"
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                onSend()
              }
            }}
          />
          <button
            onClick={onSend}
            disabled={uploading}
            className="h-14 shrink-0 rounded-2xl bg-gradient-to-br from-[color:var(--c-green-600)] to-[color:var(--c-green-700)] px-8 text-white font-bold nature-shadow-lg hover:scale-105 transition-all duration-200 disabled:opacity-60 disabled:hover:scale-100 shine-effect"
          >
            {uploading ? '⏳ Enviando…' : '✈️ Enviar'}
          </button>
        </div>
      )}
    </div>
  )
}
