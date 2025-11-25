'use client'

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { mcpExcel } from '@/lib/mcp/client'
import Spreadsheet from '@/components/Spreadsheet'
import { FeedbackButtons } from '@/components/FeedbackButtons'
import { DocumentFramework } from '@/components/DocumentFramework'
import type { DragEvent } from 'react'
// Removed EditableExcel import - using iframe instead

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  agentName?: string
  toolCalls?: any[]
  toolResults?: any[]
  userMessage?: string  // Store user message for feedback
  showDocuments?: boolean  // Flag to show DocumentFramework component
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
  
  // Document list state
  const [documents, setDocuments] = useState<{uploaded: any[], pending: any[]}>({uploaded: [], pending: []})
  const [documentsLoading, setDocumentsLoading] = useState(false)
  const [showDocumentList, setShowDocumentList] = useState(false)

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

  // Fetch documents when property changes
  const fetchDocuments = useCallback(async (pid: string) => {
    if (!pid) return
    console.log(`[Documents] 🔄 Fetching documents for property: ${pid.substring(0, 8)}...`)
    setDocumentsLoading(true)
    try {
      const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:7901'
      const url = `${BACKEND_URL}/api/documents?property_id=${pid}`
      console.log(`[Documents] Fetching from: ${url}`)
      const resp = await fetch(url)
      const data = await resp.json()
      console.log(`[Documents] Response:`, data)
      if (data.ok) {
        setDocuments({
          uploaded: data.uploaded || [],
          pending: data.pending || []
        })
        console.log(`[Documents] ✅ Fetched ${data.uploaded?.length || 0} uploaded, ${data.pending?.length || 0} pending`)
      } else {
        console.error('[Documents] ❌ Error:', data.error)
      }
    } catch (e) {
      console.error('[Documents] ❌ Failed to fetch:', e)
    } finally {
      setDocumentsLoading(false)
    }
  }, [])

  // Fetch documents when property_id changes
  useEffect(() => {
    if (propertyId) {
      console.log(`[Documents] Property changed to: ${propertyId.substring(0, 8)}..., fetching documents`)
      fetchDocuments(propertyId)
    } else {
      console.log('[Documents] No property_id, clearing documents')
      setDocuments({uploaded: [], pending: []})
      setShowDocumentList(false)
    }
  }, [propertyId, fetchDocuments])

  // Auto-open document list when documents are loaded
  useEffect(() => {
    if (documents.uploaded.length > 0 && !showDocumentList) {
      console.log(`[Documents] Auto-opening list (${documents.uploaded.length} documents)`)
      setShowDocumentList(true)
    }
  }, [documents.uploaded.length])

  useEffect(() => {
    // Auto-scroll to bottom when new messages arrive (only if already near bottom)
    if (scrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollRef.current
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 100 // Within 100px of bottom
      if (isNearBottom) {
        scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
      }
    }
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
    const userMessageContent = input  // Store for feedback
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
        // Check if it's an HTML error page (404, 500, etc.)
        if (text.includes('<!DOCTYPE html>') || text.includes('<html')) {
          throw new Error(`Error ${resp.status}: El servidor backend no está disponible o la ruta no existe. Por favor, verifica que el backend esté corriendo en ${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:7901'}`)
        }
        throw new Error(`Request failed: ${resp.status} ${text.slice(0, 200)}`)
      }
      const contentType = resp.headers.get('content-type') || ''
      if (!contentType.includes('application/json')) {
        const text = await resp.text().catch(() => '')
        // Check if it's an HTML error page
        if (text.includes('<!DOCTYPE html>') || text.includes('<html')) {
          throw new Error(`Error: El servidor devolvió HTML en lugar de JSON. Esto puede indicar que la ruta /api/chat no existe o hay un problema con el servidor.`)
        }
        throw new Error(`Expected JSON but got ${contentType}. Response: ${text.slice(0, 200)}`)
      }
      const data = await resp.json()
      const answer = String(data?.answer ?? '')
      
      // Debug: Log what backend sent
      console.log('[DEBUG] Backend response:', {
        show_documents: data?.show_documents,
        answer_preview: answer.substring(0, 100)
      })
      
      // If backend says to show documents, fetch them now
      if (data?.show_documents && propertyId) {
        console.log('[Documents] ✅ Backend requested document framework UI, fetching documents...')
        await fetchDocuments(propertyId)
      } else {
        console.log('[Documents] ❌ NOT showing framework UI:', {
          show_documents: data?.show_documents,
          has_property: !!propertyId
        })
      }
      
      setMessages(prev => [...prev, { 
        id: crypto.randomUUID(), 
        role: 'assistant', 
        content: answer,
        agentName: data?.agent_name || 'MainAgent',
        toolCalls: data?.tool_calls || [],
        toolResults: data?.tool_results || [],
        userMessage: userMessageContent,  // Store user message for feedback
        showDocuments: data?.show_documents || false  // Flag to show DocumentFramework
      }])
      
      console.log('[DEBUG] Message added with showDocuments:', data?.show_documents || false)
      
      // Auto-reload documents if agent confirms a document was uploaded
      if (propertyId && files.length > 0) {
        const uploadKeywords = ['subido', 'guardado', 'documento subido', 'he subido', 'documento guardado']
        const answerLower = answer.toLowerCase()
        if (uploadKeywords.some(keyword => answerLower.includes(keyword))) {
          console.log('[Documents] 🔄 Detected document upload in chat response, reloading documents...')
          setTimeout(() => {
            fetchDocuments(propertyId)
          }, 500)
        }
      }
      
      // Auto-reload Numbers table if agent confirms a value update or deletion
      if (excelTemplate && propertyId) {
        const updateKeywords = ['actualizado', 'guardado', 'he actualizado', 'he guardado', 'valor actualizado', 'valor guardado', 'actualicé', 'guardé']
        const deleteKeywords = ['borrado', 'eliminado', 'he borrado', 'he eliminado', 'valor borrado', 'valor eliminado', 'borré', 'eliminé']
        const answerLower = answer.toLowerCase()
        const hasUpdate = updateKeywords.some(keyword => answerLower.includes(keyword))
        const hasDelete = deleteKeywords.some(keyword => answerLower.includes(keyword))
        
        if (hasUpdate || hasDelete) {
          console.log('[Numbers Table] 🔄 Detected value update/delete in chat response, reloading table...')
          // Small delay to ensure backend has saved/deleted the value, but don't show progress bar
          setTimeout(() => {
            loadAddresses(false)
          }, 500)
        }
      }
      
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
          /La plantilla\s+["'“”]?([^\n"'“”]+)["'“”]?\s+ya está seleccionada/i, // e.g., La plantilla "R2B" ya está seleccionada
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
  // Progress bar states
  const [importProgress, setImportProgress] = useState(0) // 0-100
  const [timeRemaining, setTimeRemaining] = useState(0) // seconds
  const [estimatedTime, setEstimatedTime] = useState(0) // total estimated seconds
  // autoSync removed - all changes are saved directly to DB

  // Backend URL (defensive sanitation in case .env lines were concatenated)
  const RAW_BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:7901'
  const BACKEND_URL = (() => {
    let s = String(RAW_BACKEND_URL || '').trim()
    // If someone accidentally appended another env line into the value, cut before it
    const cutIdx = s.indexOf('NEXT_PUBLIC_API_URL=')
    if (cutIdx >= 0) s = s.slice(0, cutIdx)
    // Remove trailing quotes
    s = s.replace(/"+$/g, '').trim()
    return s || 'http://127.0.0.1:7901'
  })()
  const panelRef = useRef<HTMLDivElement | null>(null)
  const [zoom, setZoom] = useState<number>(0.85) // 85% default
  const BASE_W = 1600
  const BASE_H = 1000

  const loadAddresses = useCallback(async (showProgress = false) => {
    if (!propertyId || !excelTemplate) {
      setAddressesError('No hay propertyId o template seleccionado')
      return
    }
    try {
      // Only show progress bar if explicitly requested (e.g., during file upload)
      if (showProgress) {
        setAddressesLoading(true)
      }
      setAddressesError(null)
      console.log('[Numbers Table] loading template', excelTemplate, 'for', propertyId, 'showProgress:', showProgress)

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
      let structure: any = {}
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
      const structureIsEmpty = !structure || Object.keys(structure).length === 0 || !structure.cells || structure.cells.length === 0
      
      if (structureIsEmpty) {
        console.log('[Numbers Table] Structure is empty - template not imported yet')
        console.log('[Numbers Table] Structure keys:', Object.keys(structure))
        // Structure doesn't exist - show upload prompt
        setAddressesData(null)
        setAddressesError(null) // Clear any previous errors
        setAddressesLoading(false)
        return // Return early - can't build matrix without structure
      }
      
      console.log('[Numbers Table] structure loaded', structure, 'cells:', structure.cells?.length)

      // Load values from new Numbers Table API (always load to get saved values)
      const valuesRes = await fetch(`${BACKEND_URL}/api/numbers/table-values?property_id=${encodeURIComponent(propertyId)}&template_key=${encodeURIComponent(excelTemplate)}`)
      let cellValues: Record<string, any> = {}
      if (valuesRes.ok) {
        const contentType = valuesRes.headers.get('content-type') || ''
        if (contentType.includes('application/json')) {
          const valuesData = await valuesRes.json()
          if (valuesData?.ok && valuesData?.values) {
            cellValues = valuesData.values
            console.log('[Numbers Table] ✅ values loaded from DB:', Object.keys(cellValues).length, 'cells with saved values')
          }
        } else {
          console.warn('[Numbers Table] Values response is not JSON:', contentType)
        }
      } else {
        console.warn('[Numbers Table] Failed to load values:', valuesRes.status)
      }

      // Build matrix from structure (structure exists, so we can build it)
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
      // Debug: Log formula cells (D5, E5, etc.)
      const formulaCells = ['D5', 'E5', 'D6', 'E6', 'B10', 'B12', 'B13', 'B14', 'B15']
      formulaCells.forEach(addr => {
        if (valueMap[addr] !== undefined) {
          console.log(`[Numbers Table] ✅ Formula cell ${addr} has value:`, valueMap[addr])
        }
      })

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
          // Get format from structure or formatMap (prefer structure as it has is_user_input)
          const cellInfo = structure.cells?.find((cell: any) => cell.address === addr)
          const cellFormat = cellInfo?.format || formatMap[addr] || {}
          
          // Store cell data with format
          row.push({
            value: cellValue,
            format: cellFormat,
            address: addr,
            is_user_input: cellInfo?.is_user_input || false  // Mark yellow cells
          })
        }
        rows.push(row)
      }

      console.log('[Numbers Table] Matrix built:', rows.length, 'rows, first row:', rows[0]?.slice(0, 5))
      
      // Verify data was set correctly before setting state
      if (rows.length === 0) {
        console.warn('[Numbers Table] WARNING: Matrix is empty after building!')
        setAddressesError('La tabla se cargó pero está vacía. Por favor, verifica que el archivo Excel tenga datos.')
        setAddressesData(null)
      } else {
        setAddressesData(rows)
        console.log('[Numbers Table] ✅ addressesData set successfully! Rows:', rows.length, 'First row sample:', rows[0]?.slice(0, 3))
      }
    } catch (e: any) {
      console.error('[Numbers Table] error', e)
      setAddressesError(String(e?.message || e))
      setAddressesData(null)
    } finally {
      // Only hide progress bar if it was shown
      if (showProgress) {
        setAddressesLoading(false)
      }
      console.log('[Numbers Table] loadAddresses finished, addressesLoading set to false (showProgress:', showProgress, ')')
    }
  }, [propertyId, excelTemplate])

  // Auto-recalculate formulas when loading the table
  const autoRecalculateFormulas = useCallback(async () => {
    if (!propertyId || !excelTemplate) return
    
    try {
      console.log('[Numbers Table] 🔄 Auto-recalculating formulas...')
      const form = new FormData()
      form.append('property_id', propertyId)
      form.append('template_key', excelTemplate)
      
      const resp = await fetch(`${BACKEND_URL}/api/numbers/recalculate`, {
        method: 'POST',
        body: form
      })
      
      if (resp.ok) {
        const result = await resp.json()
        if (result.calculated && Object.keys(result.calculated).length > 0) {
          console.log('[Numbers Table] ✅ Formulas recalculated:', result.calculated)
          
          // Update addressesData with calculated values
          setAddressesData(prev => {
            if (!prev) return prev
            
            const newData = prev.map(row => row.map(cell => {
              if (cell.address && result.calculated[cell.address] !== undefined) {
                return {
                  ...cell,
                  value: result.calculated[cell.address]
                }
              }
              return cell
            }))
            
            console.log('[Numbers Table] ✅ Updated table with calculated values')
            return newData
          })
        } else {
          console.log('[Numbers Table] No formulas to calculate')
        }
      }
    } catch (e) {
      console.error('[Numbers Table] Error recalculating formulas:', e)
    }
  }, [propertyId, excelTemplate])

  // Auto-load Numbers table when template is selected (only if we don't have data)
  // This also handles reload scenarios - if template is set, try to load data
  useEffect(() => {
    if (!excelTemplate || !propertyId) return
    
    // Check localStorage to see if we recently uploaded a file
    const recentlyUploaded = localStorage.getItem(`excel_uploaded_${propertyId}_${excelTemplate}`)
    
    // Only auto-load if:
    // 1. We don't have data AND we're not currently loading AND no error
    // 2. OR we recently uploaded (but only once)
    const shouldLoad = (!addressesData || addressesData.length === 0) && !addressesLoading && !addressesError
    
    if (shouldLoad || recentlyUploaded) {
      if (recentlyUploaded) {
        // Clear the flag immediately to prevent re-triggering
        localStorage.removeItem(`excel_uploaded_${propertyId}_${excelTemplate}`)
      }
      console.log('[Numbers Table] Auto-loading triggered:', { shouldLoad, recentlyUploaded: !!recentlyUploaded, hasData: !!addressesData })
      // Initial load should not show progress bar
      loadAddresses(false).then(() => {
        console.log('[Numbers Table] loadAddresses complete, calling autoRecalculateFormulas...')
        // After loading data, auto-recalculate formulas if there are values
        autoRecalculateFormulas().catch(err => {
          console.error('[Numbers Table] autoRecalculateFormulas error:', err)
        })
      }).catch(err => {
        console.error('[Numbers Table] loadAddresses error:', err)
      })
    }
  }, [excelTemplate, propertyId, loadAddresses, autoRecalculateFormulas]) // Include all dependencies

  // Auto-reload table when messages change and contain update confirmations
  // Use a ref to track the last message we processed to avoid duplicate reloads
  const lastProcessedMessageId = useRef<string | null>(null)
  
  useEffect(() => {
    if (!excelTemplate || !propertyId || !addressesData || messages.length === 0) return
    
    const lastMessage = messages[messages.length - 1]
    if (!lastMessage || lastMessage.role !== 'assistant') return
    
    // Skip if we already processed this message
    if (lastProcessedMessageId.current === lastMessage.id) return
    
    const updateKeywords = ['actualizado', 'guardado', 'he actualizado', 'he guardado', 'valor actualizado', 'valor guardado', 'actualicé', 'guardé', 'calculando', 'recalculado', 'se han recalculado']
    const deleteKeywords = ['borrado', 'eliminado', 'he borrado', 'he eliminado', 'valor borrado', 'valor eliminado', 'borré', 'eliminé']
    const answerLower = lastMessage.content.toLowerCase()
    const hasUpdate = updateKeywords.some(keyword => answerLower.includes(keyword))
    const hasDelete = deleteKeywords.some(keyword => answerLower.includes(keyword))
    
    if (hasUpdate || hasDelete) {
      console.log('[Numbers Table] 🔄 Auto-reload triggered by assistant update/delete confirmation:', lastMessage.content.substring(0, 100))
      // Mark this message as processed
      lastProcessedMessageId.current = lastMessage.id
      // Delay to ensure backend has saved/deleted the value, but DON'T show loading state
      const timeoutId = setTimeout(async () => {
        // Reload without showing progress bar (silent reload)
        console.log('[Numbers Table] 🔄 Reloading table after update...')
        await loadAddresses(false)
        console.log('[Numbers Table] ✅ Table reloaded successfully')
      }, 1200) // Increased to 1.2s to ensure values are saved
      return () => clearTimeout(timeoutId)
    }
  }, [messages, excelTemplate, propertyId, addressesData, loadAddresses])

  // Auto-show addresses by default when Excel panel/template is active
  // Reload when template changes (loadAddresses already handles propertyId and excelTemplate)
  useEffect(() => {
    setShowAddresses(true)
  }, [excelTemplate])

  // Progress bar countdown timer
  useEffect(() => {
    if (!addressesLoading || estimatedTime === 0) {
      // Don't reset progress if we're still loading but timer ran out
      if (!addressesLoading) {
        setImportProgress(0)
        setTimeRemaining(0)
      }
      return
    }

    const interval = setInterval(() => {
      setTimeRemaining(prev => {
        if (prev <= 1) {
          // Don't clear interval if still loading - let it continue
          if (!addressesLoading) {
            clearInterval(interval)
            return 0
          }
          return 0
        }
        const newTime = prev - 1
        const progress = ((estimatedTime - newTime) / estimatedTime) * 100
        // Only update progress if we haven't manually set it higher (e.g., 80% after import)
        setImportProgress(current => Math.max(current, Math.min(progress, 95)))
        return newTime
      })
    }, 1000)

    return () => clearInterval(interval)
  }, [addressesLoading, estimatedTime])

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
            /La plantilla\s+["'“”]?([^\n"'“”]+)["'“”]?\s+ya está seleccionada/i,
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
    <div key={i} className="flex items-center justify-between gap-3 rounded-lg border border-[color:var(--border-subtle)] bg-[color:var(--bg-surface)] px-3 py-2 text-sm shadow-sm">
      <span className="truncate max-w-[16rem] font-medium text-[color:var(--text-primary)]" title={f.name}>
        📄 {f.name}
      </span>
      <button onClick={() => removeFile(i)} className="rounded-md px-2 py-1 text-[color:var(--text-tertiary)] hover:bg-[color:var(--stone-100)] transition-colors">
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
        bits.push(<strong key={`b-${m.index}`} className="font-bold text-[color:var(--text-primary)]">{m[1]}</strong>)
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
            <ul key={`ul-${out.length}`} className="list-disc pl-6 space-y-1 text-[color:var(--text-secondary)] marker:text-[color:var(--stone-400)]">
              {listItems.map((li, i) => (<li key={i}>{renderInline(li)}</li>))}
            </ul>
          )
        } else {
          out.push(
            <ol key={`ol-${out.length}`} className="list-decimal pl-6 space-y-1 text-[color:var(--text-secondary)] marker:text-[color:var(--stone-400)]">
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
        if (line.startsWith('### ')) { flush(); out.push(<div key={`h3-${out.length}`} className="mt-4 mb-2 text-[color:var(--text-primary)] font-serif font-bold text-lg">{renderInline(line.slice(4))}</div>); continue }
        if (line.startsWith('## '))  { flush(); out.push(<div key={`h2-${out.length}`} className="mt-5 mb-3 text-[color:var(--text-primary)] font-serif font-bold text-xl border-b border-[color:var(--border-subtle)] pb-1">{renderInline(line.slice(3))}</div>); continue }
        if (/^\d+\./.test(line)) { if (listType !== 'ol') { flush(); listType = 'ol' } listItems.push(line.replace(/^\d+\.\s*/, '')); continue }
        if (line.startsWith('- ')) { if (listType !== 'ul') { flush(); listType = 'ul' } listItems.push(line.slice(2)); continue }
        flush();
        out.push(<p key={`p-${out.length}`} className="leading-relaxed text-[color:var(--text-secondary)] mb-2 last:mb-0">{renderInline(line)}</p>)
      }
      flush()
      return out
    }

    // Callout: emphasize the "choose one of II/III/IV" rule whenever present
    if (/elegir\s+una\s+entre\s+ii\/iii\/iv/i.test(processedText)) {
      nodes.push(
        <div key="callout-optional" className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900 text-sm flex items-start gap-3 shadow-sm">
          <span className="text-amber-600 mt-0.5">⚠️</span>
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
            <img src={token} alt="gráfico" className="max-w-full max-h-[400px] rounded-lg border border-[color:var(--border-subtle)] shadow-sm" />
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
              className="inline-flex items-center gap-3 px-4 py-2.5 rounded-lg border border-[color:var(--border-subtle)] bg-white hover:bg-[color:var(--stone-50)] text-[color:var(--text-primary)] transition-colors shadow-sm group"
            >
              <span className="p-1.5 rounded bg-[color:var(--stone-100)] text-[color:var(--text-tertiary)] group-hover:text-[color:var(--text-primary)]">📄</span>
              <span className="font-medium text-sm">Descargar {ext}</span>
            </a>
          </div>
        )
      } else {
        nodes.push(<div key={`md-${i}`} className="space-y-1">{renderMarkdown(token)}</div>)
      }
    }
    return <>{nodes}</>
  }, [])

  const ExcelPanel = useMemo(() => {
    if (!excelTemplate) return null
    return (
      <div className="flex flex-col h-full rounded-xl border border-[color:var(--border-strong)] bg-white shadow-sm overflow-hidden">
        {/* Header with gradient and better styling */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[color:var(--border-subtle)] bg-[color:var(--stone-50)]">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded bg-white shadow-sm text-lg border border-[color:var(--border-subtle)]">
              📊
            </div>
            <div>
              <div className="font-serif font-bold text-[color:var(--text-primary)]">Excel — {excelTemplate}</div>
              <div className="text-[10px] uppercase tracking-wider text-[color:var(--text-tertiary)]">Edición en tiempo real</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div className="hidden md:flex items-center gap-px rounded-lg border border-[color:var(--border-subtle)] bg-white p-0.5">
              <button onClick={() => setZoom(z => Math.max(0.4, Math.round((z-0.1)*100)/100))} className="px-2 py-1 text-xs hover:bg-[color:var(--stone-100)] rounded text-[color:var(--text-secondary)]">−</button>
              <button onClick={() => setZoom(1)} className="px-2 py-1 text-xs font-medium hover:bg-[color:var(--stone-100)] rounded text-[color:var(--text-primary)]">100%</button>
              <button onClick={() => setZoom(z => Math.min(1.2, Math.round((z+0.1)*100)/100))} className="px-2 py-1 text-xs hover:bg-[color:var(--stone-100)] rounded text-[color:var(--text-secondary)]">＋</button>
            </div>
            <button 
              onClick={() => {
                console.log('[Numbers Table] 🔄 Manual reload triggered')
                setExcelRefreshKey(Date.now())
                // Manual reload should show progress briefly
                loadAddresses(true)
              }}
              className="p-2 rounded-lg hover:bg-[color:var(--stone-200)] text-[color:var(--text-secondary)] transition-colors"
              title="Recargar"
            >
              ↻
            </button>
            <button 
              onClick={() => setExcelTemplate(null)} 
              className="p-2 rounded-lg hover:bg-[color:var(--stone-200)] text-[color:var(--text-secondary)] transition-colors"
              title="Cerrar"
            >
              ✕
            </button>
          </div>
        </div>
        
        {/* Spreadsheet replica (DB-backed) */}
        <div className="relative flex-1 flex flex-col min-h-0 bg-[color:var(--stone-50)]">
          {/* Show mirrored in-app Spreadsheet for realtime editing/viewing */}
          <div className="relative w-full h-full flex flex-col">
              <div className="flex-1 overflow-auto p-0 relative" style={{ minHeight: '400px' }}>
                {/* Progress bar overlay - ALWAYS show when addressesLoading is true */}
                {addressesLoading ? (
                  <div 
                    className="absolute inset-0 flex items-center justify-center bg-white/80 backdrop-blur-sm z-50"
                  >
                    <div className="text-center w-full max-w-sm p-6 bg-white rounded-xl shadow-lg border border-[color:var(--border-subtle)]">
                      <div className="animate-spin rounded-full h-10 w-10 border-2 border-[color:var(--stone-200)] border-t-[color:var(--forest-900)] mx-auto mb-4"></div>
                      <div className="font-medium mb-4 text-[color:var(--text-primary)]">Procesando archivo Excel...</div>
                      
                      {/* Progress Bar */}
                      <div className="w-full bg-[color:var(--stone-200)] rounded-full h-2 mb-4 overflow-hidden">
                        <div 
                          className="bg-[color:var(--forest-900)] h-full rounded-full transition-all duration-300 ease-out"
                          style={{ width: `${Math.max(10, Math.min(100, importProgress))}%` }}
                        ></div>
                      </div>
                      
                      <div className="text-2xl font-serif font-bold text-[color:var(--forest-900)]">
                        {Math.round(Math.max(10, Math.min(100, importProgress)))}%
                      </div>
              </div>
            </div>
                ) : null}

                {/* Main content */}
                {addressesData && addressesData.length > 0 ? (
                  <Spreadsheet
                    data={addressesData}
                    addressRange="A1"
                    selected={selectedCell}
                    showAddresses={false}
                    onCellClick={async (addr) => {
                      setSelectedCell(addr)
                      
                      // Fetch cell info to show formula if exists
                      try {
                        const structureResp = await fetch(`${BACKEND_URL}/api/numbers/template-structure?property_id=${propertyId}&template_key=${excelTemplate}`)
                        const structureData = await structureResp.json()
                        
                        const valuesResp = await fetch(`${BACKEND_URL}/api/numbers/table-values?property_id=${propertyId}&template_key=${excelTemplate}`)
                        const valuesData = await valuesResp.json()
                        
                        // Find cell in structure
                        const cellInfo = structureData.structure?.cells?.find((c: any) => c.address === addr)
                        const cellValue = valuesData[addr]
                        
                        if (cellInfo?.formula) {
                          // Cell has a formula - show detailed info
                          const actualValue = cellValue?.value || cellValue || ''
                          let message = `📊 **Celda ${addr}**\n\n`
                          message += `**Fórmula:** ${cellInfo.formula}\n`
                          if (actualValue) {
                            message += `**Resultado:** ${actualValue}\n`
                          }
                          
                          // Try to explain the calculation
                          const formula = cellInfo.formula.substring(1) // Remove leading "="
                          const explanation = formula
                            .replace(/\*/g, ' × ')
                            .replace(/\//g, ' ÷ ')
                            .replace(/\+/g, ' + ')
                            .replace(/-/g, ' − ')
                          
                          if (explanation !== formula) {
                            message += `**Cálculo:** ${explanation}`
                            if (actualValue) {
                              message += ` = ${actualValue}`
                            }
                          }
                          
                          setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: message }])
                        } else {
                          // Regular cell - just show selection
                          setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: `Seleccionada: ${addr}` }])
                        }
                      } catch (error) {
                        console.error('Error fetching cell info:', error)
                        setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: `Seleccionada: ${addr}` }])
                      }
                    }}
                  />
                ) : !addressesLoading && addressesError ? (
                  <div className="p-8 text-center">
                    <div className="mb-2 text-lg font-medium text-red-600">
                      {addressesError.includes('Error') ? 'Error de carga' : 'Información'}
                    </div>
                    <p className="text-sm text-[color:var(--text-tertiary)] max-w-md mx-auto mb-4">{addressesError}</p>
                    <button 
                      onClick={() => loadAddresses()} 
                      className="btn-secondary text-sm"
                    >
                      Reintentar
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center h-full text-center p-8">
                    <div className="mb-4 p-4 rounded-full bg-[color:var(--stone-100)] text-3xl text-[color:var(--stone-400)]">
                      📊
                    </div>
                    <h3 className="font-serif font-bold text-lg text-[color:var(--text-primary)] mb-2">
                      Plantilla de Números
                    </h3>
                    <p className="text-sm text-[color:var(--text-secondary)] max-w-xs mb-6">
                      Sube el archivo Excel para comenzar a trabajar con los datos.
                    </p>
                  </div>
                )}
              </div>
              <div className="px-4 py-3 bg-[color:var(--stone-50)] border-t border-[color:var(--border-subtle)] flex gap-3 items-center justify-between">
                <div className="flex gap-2 items-center">
                  <input 
                    type="file" 
                    accept=".xlsx,.xls" 
                    id="excel-upload-input"
                    style={{ display: 'none' }}
                    onChange={async (e) => {
                      const file = e.target.files?.[0]
                      if (!file || !propertyId || !excelTemplate) return
                      
                      // Estimate time based on file size (roughly 1 second per 100KB, minimum 5 seconds)
                      const fileSizeKB = file.size / 1024
                      const estimatedSeconds = Math.max(5, Math.ceil(fileSizeKB / 100) + 3) // +3 for processing
                      console.log('[Numbers Table] 📤 Starting file upload:', file.name, 'Size:', fileSizeKB.toFixed(2), 'KB, Estimated time:', estimatedSeconds, 's')
                      
                      // CRITICAL: Set loading state FIRST, before anything else
                      // This ensures the progress bar appears immediately
                      setAddressesLoading(true)
                      
                      // Clear previous data and errors
                      setAddressesData(null)
                      setAddressesError(null)
                      
                      // Set progress states
                      setEstimatedTime(estimatedSeconds)
                      setTimeRemaining(estimatedSeconds)
                      setImportProgress(15) // Start at 15% to show progress immediately
                      
                      console.log('[Numbers Table] ✅ Loading state set to true, progress bar should be visible NOW')
                      
                      // Force React to flush state updates - use multiple frames to ensure render
                      await new Promise(resolve => {
                        requestAnimationFrame(() => {
                          requestAnimationFrame(() => {
                            setTimeout(resolve, 150) // Give React plenty of time to render
                          })
                        })
                      })
                      
                      console.log('[Numbers Table] ✅ After delay, addressesLoading should be true and progress bar visible')
                      
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
                        console.log('[Numbers Table] 📥 Upload response:', data?.ok ? 'OK' : 'ERROR', data)
                        
                        if (data?.ok) {
                          setAddressesError(null)
                          // Update progress to 80% after successful upload
                          setImportProgress(80)
                          setTimeRemaining(Math.max(1, Math.ceil(estimatedSeconds * 0.2))) // 20% remaining
                          console.log('[Numbers Table] ✅ File uploaded successfully, progress at 80%, now loading data...')
                          // Mark in localStorage that we just uploaded (for reload scenarios)
                          localStorage.setItem(`excel_uploaded_${propertyId}_${excelTemplate}`, Date.now().toString())
                          
                          // Load data directly without calling loadAddresses (which would reset loading state)
                          try {
                            // Ensure loading state stays true
                            setAddressesLoading(true)
                            
                            // Load structure
                            const structureRes = await fetch(`${BACKEND_URL}/api/numbers/template-structure?property_id=${encodeURIComponent(propertyId)}&template_key=${encodeURIComponent(excelTemplate)}`)
                            if (!structureRes.ok) throw new Error(`Failed to load structure: ${structureRes.status}`)
                            const structureData = await structureRes.json()
                            let structure = structureData?.ok && structureData?.structure ? structureData.structure : (structureData?.structure || structureData)
                            
                            if (!structure || Object.keys(structure).length === 0 || !structure.cells || structure.cells.length === 0) {
                              throw new Error('Structure is empty after import')
                            }
                            
                            // Update progress to 90%
                            setImportProgress(90)
                            
                            // Load values
                            const valuesRes = await fetch(`${BACKEND_URL}/api/numbers/table-values?property_id=${encodeURIComponent(propertyId)}&template_key=${encodeURIComponent(excelTemplate)}`)
                            let cellValues: Record<string, any> = {}
                            if (valuesRes.ok) {
                              const valuesData = await valuesRes.json()
                              if (valuesData?.ok && valuesData?.values) {
                                cellValues = valuesData.values
                              }
                            }
                            
                            // Build matrix
                            const maxRow = structure.rows || 30
                            const maxCol = structure.columns || 5
                            const rows: any[][] = []
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
                            
                            if (structure.cells) {
                              for (const cellInfo of structure.cells) {
                                const addr = cellInfo.address
                                if (cellInfo.format && !formatMap[addr]) {
                                  formatMap[addr] = cellInfo.format
                                }
                              }
                            }
                            
                            for (let r = 0; r < maxRow; r++) {
                              const row: any[] = []
                              for (let c = 0; c < maxCol; c++) {
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
                                let cellValue = valueMap[addr]
                                if (cellValue === undefined) {
                                  const cellInfo = structure.cells?.find((cell: any) => cell.address === addr)
                                  cellValue = cellInfo?.value || ''
                                }
                                row.push({
                                  value: cellValue,
                                  format: formatMap[addr] || {},
                                  address: addr
                                })
                              }
                              rows.push(row)
                            }
                            
                            if (rows.length === 0) {
                              throw new Error('Table is empty after import')
                            }
                            
                            // Set data and show 100%
                            setAddressesData(rows)
                            setImportProgress(100)
                            setTimeRemaining(0)
                            console.log('[Numbers Table] ✅ Data loaded, setting progress to 100%')
                            
                            // Small delay to show 100% before hiding
                            setTimeout(() => {
                              setAddressesLoading(false)
                              setImportProgress(0)
                              setEstimatedTime(0)
                              console.log('[Numbers Table] ✅ Loading complete, table should be visible now')
                            }, 1000) // Show 100% for 1 second
                          } catch (loadErr: any) {
                            console.error('[Numbers Table] ❌ Error reloading addresses after import:', loadErr)
                            setAddressesError(`Error al cargar datos después de importar: ${loadErr?.message || String(loadErr)}`)
                            setAddressesLoading(false)
                            setImportProgress(0)
                            setTimeRemaining(0)
                            setEstimatedTime(0)
                          }
                        } else {
                          setAddressesError(`Error: ${data?.error || 'Error desconocido'}`)
                          setAddressesLoading(false)
                          setImportProgress(0)
                          setTimeRemaining(0)
                          setEstimatedTime(0)
                        }
                      } catch (err: any) {
                        setAddressesError(`Error al subir archivo: ${err?.message || String(err)}`)
                        setAddressesLoading(false)
                        setImportProgress(0)
                        setTimeRemaining(0)
                        setEstimatedTime(0)
                      }
                      
                      // Reset input
                      e.target.value = ''
                    }}
                  />
                  <label 
                    htmlFor="excel-upload-input"
                    className="btn-primary cursor-pointer text-sm flex items-center gap-2"
                  >
                    <span>📤</span> Subir Excel
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
                    className="btn-secondary text-sm flex items-center gap-2"
                  >
                    <span>📥</span> Exportar
                  </button>
                )}
              </div>
            </div>
        </div>
        
        {/* Footer with helpful hints - compact */}
        <div className="px-4 py-2 bg-[color:var(--stone-100)] border-t border-[color:var(--border-subtle)] flex-shrink-0">
          <div className="text-xs text-[color:var(--text-secondary)] flex items-center gap-2">
            <span>💡</span>
            <span>Di "pon [campo] a [valor]" o "borra [campo]" para editar.</span>
          </div>
        </div>
      </div>
    )
  }, [excelTemplate, excelRefreshKey, addressesLoading, addressesData, addressesError, importProgress, timeRemaining, estimatedTime, selectedCell, propertyId])

  // Layout: two columns when Excel is open, single column otherwise
  const hasExcel = !!excelTemplate

  return (
    <div className="flex h-[calc(100vh-6rem)] flex-col gap-4">
      {/* Property indicator */}
      {propertyName && (
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-[color:var(--text-tertiary)]">Propiedad actual:</span>
            <span className="font-serif font-bold text-[color:var(--forest-900)] bg-[color:var(--forest-50)] px-3 py-1 rounded-full border border-[color:var(--forest-100)]">
              {propertyName}
            </span>
            {documents.uploaded.length > 0 && (
              <button
                onClick={() => setShowDocumentList(!showDocumentList)}
                className="text-xs text-[color:var(--text-tertiary)] bg-[color:var(--stone-100)] hover:bg-[color:var(--stone-200)] px-2 py-1 rounded-full transition-colors cursor-pointer"
              >
                📄 {documents.uploaded.length} documento{documents.uploaded.length !== 1 ? 's' : ''} {showDocumentList ? '▼' : '▶'}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Document List - Collapsible */}
      {propertyName && showDocumentList && (
        <div className="rama-card p-4 animate-fade-in">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-serif font-bold text-[color:var(--text-primary)]">
              📄 Documentos Subidos
            </h3>
            <button 
              onClick={() => fetchDocuments(propertyId!)}
              className="text-xs px-2 py-1 rounded bg-[color:var(--stone-100)] hover:bg-[color:var(--stone-200)] text-[color:var(--text-secondary)] transition-colors"
              disabled={documentsLoading}
            >
              {documentsLoading ? '⏳' : '↻'} Recargar
            </button>
          </div>
          
          {documentsLoading ? (
            <div className="text-sm text-[color:var(--text-tertiary)] py-4 text-center">
              Cargando documentos...
            </div>
          ) : documents.uploaded.length > 0 || documents.pending.length > 0 ? (
            <div className="max-h-[600px] overflow-y-auto scrollbar-thin">
              <DocumentFramework 
                uploaded={documents.uploaded} 
                pending={documents.pending}
              />
            </div>
          ) : (
            <div className="text-sm text-[color:var(--text-tertiary)] py-4 text-center">
              No hay documentos aún
            </div>
          )}
        </div>
      )}
      
      {/* Main content area: split layout when Excel is open */}
      <div className={`flex-1 flex gap-6 ${hasExcel ? 'flex-row' : 'flex-col'}`}>
        {/* Excel Panel - Left side when open (larger) */}
        {hasExcel && (
          <div className="flex-[7] flex flex-col min-w-0 animate-fade-in">
            {ExcelPanel}
          </div>
        )}
        
        {/* Chat area - Right side when Excel is open (smaller), full width otherwise */}
        <div className={`${hasExcel ? 'flex-[3] flex-shrink-0 h-full' : 'flex-1'} flex flex-col min-h-0`}>
          <div ref={scrollRef} className={`flex-1 overflow-y-auto p-4 max-h-[600px] ${hasExcel ? 'rounded-xl border border-[color:var(--border-strong)] bg-white' : ''} scrollbar-thin`}>
            {!hasExcel && ExcelPanel}
            {hasExcel && (
              <>
                {/* Quick actions for MCP excel tools (visible only when completing a Numbers template) */}
                <div className="mb-4 flex flex-wrap gap-2 items-center">
                  <button onClick={quickGetRange} className="text-xs px-2 py-1 rounded bg-[color:var(--stone-100)] hover:bg-[color:var(--stone-200)] text-[color:var(--text-secondary)] border border-[color:var(--border-subtle)]">Leer A1:B10</button>
                  <button onClick={quickSetA1} className="text-xs px-2 py-1 rounded bg-[color:var(--stone-100)] hover:bg-[color:var(--stone-200)] text-[color:var(--text-secondary)] border border-[color:var(--border-subtle)]">Escribir A1</button>
                  <button onClick={quickAppend} className="text-xs px-2 py-1 rounded bg-[color:var(--stone-100)] hover:bg-[color:var(--stone-200)] text-[color:var(--text-secondary)] border border-[color:var(--border-subtle)]">Añadir fila</button>
                  {selectedCell && (
                    <div className="ml-auto text-xs px-2 py-1 rounded bg-[color:var(--forest-50)] text-[color:var(--forest-900)] border border-[color:var(--forest-100)]">
                      Selección: <b>{selectedCell}</b>
                    </div>
                  )}
                </div>

                {toolLogs.length > 0 && (
                  <div className="mb-4 rounded-lg border border-[color:var(--border-subtle)] bg-[color:var(--stone-50)] p-3 text-xs text-[color:var(--text-secondary)]">
                    <div className="font-bold mb-2 text-[color:var(--text-primary)]">Debug Log</div>
                    <div className="space-y-1.5 max-h-32 overflow-auto">
                      {toolLogs.map((l, i) => (
                        <div key={i} className="border-b border-[color:var(--border-subtle)] last:border-b-0 pb-1">
                          <div className="font-mono text-[10px] text-[color:var(--forest-800)]">{l.tool} <span className="text-[color:var(--text-tertiary)]">({l.ms}ms)</span></div>
                          <div className="opacity-70 truncate">{JSON.stringify(l.args)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
            {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full py-12">
            <div className="mb-6 text-6xl opacity-90">🌾</div>
            <h2 className="mb-2 text-3xl font-serif font-bold text-[color:var(--text-primary)] text-center">
              Bienvenido a RAMA
            </h2>
            <p className="text-lg text-[color:var(--text-secondary)] mb-12 text-center max-w-md">
              Tu asistente inteligente para la gestión integral de propiedades rurales.
            </p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-3xl w-full">
              {/* Crear ficha propiedad */}
              <div className="rama-card p-5 cursor-pointer hover:bg-[color:var(--stone-50)] group">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 h-10 w-10 rounded-full bg-[color:var(--forest-50)] flex items-center justify-center text-xl group-hover:bg-[color:var(--forest-100)] transition-colors">
                    🏡
                  </div>
                  <div>
                    <h3 className="font-serif font-bold text-[color:var(--text-primary)] mb-1">
                      Nueva Propiedad
                    </h3>
                    <p className="text-sm text-[color:var(--text-tertiary)]">
                      Crear ficha y configurar
                    </p>
                  </div>
                </div>
              </div>
              
              {/* Gestión documentos */}
              <div className="rama-card p-5 cursor-pointer hover:bg-[color:var(--stone-50)] group">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 h-10 w-10 rounded-full bg-[color:var(--stone-100)] flex items-center justify-center text-xl group-hover:bg-[color:var(--stone-200)] transition-colors">
                    📊
                  </div>
                  <div>
                    <h3 className="font-serif font-bold text-[color:var(--text-primary)] mb-1">
                      Números y Documentos
                    </h3>
                    <p className="text-sm text-[color:var(--text-tertiary)]">
                      Gestionar archivos y finanzas
                    </p>
                  </div>
                </div>
              </div>
              
              {/* Consultas inteligentes */}
              <div className="rama-card p-5 cursor-pointer hover:bg-[color:var(--stone-50)] group">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 h-10 w-10 rounded-full bg-amber-50 flex items-center justify-center text-xl group-hover:bg-amber-100 transition-colors">
                    🤖
                  </div>
                  <div>
                    <h3 className="font-serif font-bold text-[color:var(--text-primary)] mb-1">
                      Consultas
                    </h3>
                    <p className="text-sm text-[color:var(--text-tertiary)]">
                      Pregunta sobre tus contratos
                    </p>
                  </div>
                </div>
              </div>
              
              {/* Resúmenes */}
              <div className="rama-card p-5 cursor-pointer hover:bg-[color:var(--stone-50)] group">
                <div className="flex items-start gap-4">
                  <div className="flex-shrink-0 h-10 w-10 rounded-full bg-blue-50 flex items-center justify-center text-xl group-hover:bg-blue-100 transition-colors">
                    📝
                  </div>
                  <div>
                    <h3 className="font-serif font-bold text-[color:var(--text-primary)] mb-1">
                      Resúmenes
                    </h3>
                    <p className="text-sm text-[color:var(--text-tertiary)]">
                      Analiza documentos al instante
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-6 pb-4">
            {messages.map((m, idx) => (
              <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={
                  'max-w-[85%] md:max-w-[75%] rounded-2xl px-5 py-4 shadow-sm ' +
                  (m.role === 'user'
                    ? 'bg-[color:var(--forest-900)] text-white rounded-tr-sm'
                    : 'bg-white border border-[color:var(--border-strong)] text-[color:var(--text-primary)] rounded-tl-sm')
                }>
                  <div className={m.role === 'user' ? 'text-white/90' : ''}>
                    {(() => {
                      console.log('[DEBUG RENDER] Message:', {
                        id: m.id,
                        role: m.role,
                        showDocuments: m.showDocuments,
                        hasDocuments: !!(documents.uploaded.length || documents.pending.length)
                      })
                      
                      if (m.role === 'assistant' && m.showDocuments) {
                        console.log('[DEBUG] ✅ Rendering DocumentFramework in chat for message', m.id)
                        return (
                          <div className="w-full border-2 border-red-500 p-2 rounded animate-pulse">
                            <div className="text-sm text-[color:var(--text-secondary)] mb-4 font-bold text-red-600">
                              [DEBUG MODE] Rendering DocumentFramework Component:
                            </div>
                            <div className="text-sm text-[color:var(--text-secondary)] mb-4">
                              {m.content.split('\n')[0]} {/* Only show first line ("Para la propiedad...") */}
                            </div>
                            <DocumentFramework uploaded={documents.uploaded} pending={documents.pending} />
                          </div>
                        )
                      }
                      console.log('[DEBUG] ❌ NOT rendering DocumentFramework (showDocuments:', m.showDocuments, ')')
                      return m.role === 'assistant' ? renderMessageContent(m.content) : m.content
                    })()}
                  </div>
                  
                  {/* Add feedback buttons for assistant messages */}
                  {m.role === 'assistant' && (
                    <div className="mt-3 pt-3 border-t border-[color:var(--border-subtle)]">
                      <FeedbackButtons
                        messageId={m.id}
                        agentName={m.agentName || 'MainAgent'}
                        userMessage={m.userMessage || (idx > 0 && messages[idx - 1]?.role === 'user' ? messages[idx - 1].content : '')}
                        agentResponse={m.content}
                        toolCalls={m.toolCalls}
                        toolResults={m.toolResults}
                        propertyId={propertyId}
                      />
                    </div>
                  )}
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
              className="mt-3 rounded-xl border border-dashed border-[color:var(--border-strong)] bg-[color:var(--stone-50)] p-3 text-center"
            >
              <div className="flex items-center justify-between">
                <div className="text-xs text-[color:var(--text-tertiary)] flex items-center gap-2">
                  <span>📎</span>
                  <span>Arrastra archivos aquí</span>
                </div>
                <label className="cursor-pointer text-xs font-medium text-[color:var(--forest-900)] hover:underline">
                  Explorar
                  <input type="file" multiple className="hidden" onChange={(e) => setFiles(prev => [...prev, ...Array.from(e.target.files || [])])} />
                </label>
              </div>
              {files.length > 0 && (
                <div className="mt-2 grid grid-cols-1 gap-1 text-left">
                  {filePreviews}
                </div>
              )}
            </div>
          )}
          
          {/* Composer - Inside chat area when Excel is open */}
          {hasExcel && (
            <div className="sticky bottom-0 mt-3 flex items-center gap-2 rounded-xl border border-[color:var(--border-strong)] bg-white p-2 shadow-sm">
              <button
                onMouseDown={startRecording}
                onMouseUp={stopRecording}
                onTouchStart={startRecording}
                onTouchEnd={stopRecording}
                disabled={isProcessingVoice}
                className={
                  `flex h-8 w-8 items-center justify-center rounded-full transition-all ` +
                  (isRecording 
                    ? 'bg-red-500 text-white animate-pulse' 
                    : isProcessingVoice
                    ? 'bg-[color:var(--stone-200)] text-[color:var(--text-tertiary)]'
                    : 'text-[color:var(--text-secondary)] hover:bg-[color:var(--stone-100)]')
                }
              >
                <span>
                  {isRecording ? '⏺' : isProcessingVoice ? '⏳' : '🎤'}
                </span>
              </button>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Escribe..."
                rows={1}
                className="flex-1 resize-none bg-transparent text-sm outline-none placeholder:text-[color:var(--text-tertiary)]"
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
                className="flex h-8 w-8 items-center justify-center rounded-full bg-[color:var(--forest-900)] text-white hover:bg-[color:var(--forest-800)] disabled:opacity-50"
              >
                {uploading ? '⏳' : '↑'}
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
          className={`rounded-xl border border-dashed border-[color:var(--wheat-500)] p-4 transition-colors ${files.length > 0 ? 'bg-[color:var(--wheat-100)] border-[color:var(--wheat-600)]' : 'bg-[color:var(--stone-50)] hover:bg-[color:var(--wheat-100)]'}`}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 text-[color:var(--text-secondary)]">
              <span className="text-xl text-[color:var(--stone-400)]">📎</span>
              <span className="text-sm font-medium">Arrastra documentos aquí para analizarlos</span>
            </div>
            <label className="btn-secondary text-xs cursor-pointer">
              Seleccionar archivos
              <input type="file" multiple className="hidden" onChange={(e) => setFiles(prev => [...prev, ...Array.from(e.target.files || [])])} />
            </label>
          </div>
          {files.length > 0 && (
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
              {filePreviews}
            </div>
          )}
        </div>
      )}

      {/* Composer - Outside chat area when Excel is NOT open */}
      {!hasExcel && (
        <div className="flex items-end gap-3 rounded-xl border border-[color:var(--border-strong)] bg-white p-3 shadow-sm focus-within:ring-2 focus-within:ring-[color:var(--forest-100)] focus-within:border-[color:var(--forest-500)] transition-all">
          <button
            onMouseDown={startRecording}
            onMouseUp={stopRecording}
            onTouchStart={startRecording}
            onTouchEnd={stopRecording}
            disabled={isProcessingVoice}
            className={
              'flex h-10 w-10 shrink-0 items-center justify-center rounded-full transition-all ' +
              (isRecording 
                ? 'bg-red-50 text-red-600 border border-red-200 animate-pulse' 
                : isProcessingVoice
                ? 'bg-[color:var(--stone-100)] text-[color:var(--text-tertiary)]'
                : 'bg-[color:var(--stone-50)] text-[color:var(--text-secondary)] hover:bg-[color:var(--stone-100)] border border-[color:var(--border-subtle)]')
            }
            title={
              isRecording 
                ? 'Suelta para detener' 
                : isProcessingVoice 
                ? 'Procesando...' 
                : 'Mantén para grabar'
            }
          >
            <span className="text-lg">
              {isRecording ? '⏺' : isProcessingVoice ? '⏳' : '🎤'}
            </span>
          </button>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Escribe tu mensaje..."
            rows={1}
            className="min-h-[40px] flex-1 resize-none bg-transparent py-2.5 text-[color:var(--text-primary)] placeholder:text-[color:var(--stone-400)] outline-none"
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
            className="h-10 rounded-lg bg-[color:var(--forest-900)] px-6 text-sm font-medium text-white shadow-sm hover:bg-[color:var(--forest-800)] disabled:opacity-50 disabled:hover:bg-[color:var(--forest-900)] transition-colors"
          >
            {uploading ? '...' : 'Enviar'}
          </button>
        </div>
      )}
    </div>
  )
}
