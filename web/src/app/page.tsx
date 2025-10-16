'use client'

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { DragEvent } from 'react'

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
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const scrollRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages.length])

  const onDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    const dropped = Array.from(e.dataTransfer.files || [])
    if (dropped.length) setFiles(prev => [...prev, ...dropped])
  }, [])

  const onSend = useCallback(async () => {
    if (!input.trim() && files.length === 0) return
    const userMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', content: input }
    setMessages(prev => [...prev, userMessage])
    setInput('')

    const form = new FormData()
    form.append('text', userMessage.content)
    form.append('session_id', 'web-ui')
    for (const f of files) form.append('files', f)
    setUploading(true)
    try {
      const resp = await fetch('/api/chat', { method: 'POST', body: form })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data?.error || 'Request failed')
      const answer = String(data?.answer ?? '')
      setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: answer }])
      setFiles([])
    } catch (e: any) {
      setMessages(prev => [...prev, { id: crypto.randomUUID(), role: 'assistant', content: `Error: ${e?.message || String(e)}` }])
    } finally {
      setUploading(false)
    }
  }, [input, files])

  const startRecording = useCallback(async () => {
    if (isRecording) return
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    const mr = new MediaRecorder(stream)
    mediaRecorderRef.current = mr
    chunksRef.current = []
    mr.ondataavailable = (e) => { if (e.data.size) chunksRef.current.push(e.data) }
    mr.onstop = async () => {
      const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
      const file = new File([blob], `voice-${Date.now()}.webm`, { type: 'audio/webm' })
      setFiles(prev => [...prev, file])
    }
    mr.start()
    setIsRecording(true)
  }, [isRecording])

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop()
    mediaRecorderRef.current = null
    setIsRecording(false)
  }, [])

  const removeFile = useCallback((idx: number) => {
    setFiles(prev => prev.filter((_, i) => i !== idx))
  }, [])

  const filePreviews = useMemo(() => files.map((f, i) => (
    <div key={i} className="flex items-center justify-between gap-2 rounded-md border border-[color:var(--c-green-300)] bg-white/70 px-3 py-2 text-sm">
      <span className="truncate max-w-[16rem]" title={f.name}>{f.name}</span>
      <button onClick={() => removeFile(i)} className="rounded-md px-2 py-1 text-[color:var(--c-green-800)] hover:bg-[color:var(--c-green-100)]">Remove</button>
    </div>
  )), [files, removeFile])

  return (
    <div className="flex h-[calc(100vh-140px)] flex-col gap-3">
      {/* Chat area */}
      <div ref={scrollRef} className="flex-1 overflow-auto rounded-2xl p-6 bg-gradient-to-br from-[color:var(--c-green-50)] to-[color:var(--c-green-100)] shadow-lg border border-[color:var(--c-green-200)]">
        {messages.length === 0 ? (
          <div className="text-center text-[color:var(--c-green-800)]">
            <div className="mb-3 text-3xl animate-pulse">🌾</div>
            <div className="mb-2 text-2xl font-bold bg-gradient-to-r from-[color:var(--c-green-700)] to-[color:var(--c-green-600)] bg-clip-text text-transparent">
              ¡Bienvenido a RAMA Country Living!
            </div>
            <div className="opacity-80 text-base mb-6">Tu asistente inteligente para gestionar propiedades</div>
            <div className="mt-6 grid grid-cols-2 gap-4">
              <div className="h-[70px] rounded-2xl bg-gradient-to-br from-white to-[color:var(--c-green-50)] border border-[color:var(--c-green-200)] text-left px-4 py-3 shadow-md hover:shadow-lg hover:scale-105 transition-all duration-200 cursor-default">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">🛠️</span>
                  <div>
                    <div className="text-[15px] font-semibold leading-4 text-[color:var(--c-green-800)]">Crear ficha propiedad</div>
                    <div className="text-[12px] opacity-70 mt-1 text-[color:var(--c-green-600)]">Nueva propiedad</div>
                  </div>
                </div>
              </div>
              <div className="h-[70px] rounded-2xl bg-gradient-to-br from-white to-[color:var(--c-green-50)] border border-[color:var(--c-green-200)] text-left px-4 py-3 shadow-md hover:shadow-lg hover:scale-105 transition-all duration-200 cursor-default">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">▸</span>
                  <div>
                    <div className="text-[15px] font-semibold leading-4 text-[color:var(--c-green-800)]">Gestión documentos</div>
                    <div className="text-[12px] opacity-70 mt-1 text-[color:var(--c-green-600)]">Subir y organizar</div>
                  </div>
                </div>
              </div>
              <div className="h-[70px] rounded-2xl bg-gradient-to-br from-white to-[color:var(--c-green-50)] border border-[color:var(--c-green-200)] text-left px-4 py-3 shadow-md hover:shadow-lg hover:scale-105 transition-all duration-200 cursor-default">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">💬</span>
                  <div>
                    <div className="text-[15px] font-semibold leading-4 text-[color:var(--c-green-800)]">Consultas inteligentes</div>
                    <div className="text-[12px] opacity-70 mt-1 text-[color:var(--c-green-600)]">Preguntas sobre docs</div>
                  </div>
                </div>
              </div>
              <div className="h-[70px] rounded-2xl bg-gradient-to-br from-white to-[color:var(--c-green-50)] border border-[color:var(--c-green-200)] text-left px-4 py-3 shadow-md hover:shadow-lg hover:scale-105 transition-all duration-200 cursor-default">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">✉️</span>
                  <div>
                    <div className="text-[15px] font-semibold leading-4 text-[color:var(--c-green-800)]">Email automatizado</div>
                    <div className="text-[12px] opacity-70 mt-1 text-[color:var(--c-green-600)]">Enviar información</div>
                  </div>
                </div>
              </div>
              <div className="h-[70px] rounded-2xl bg-gradient-to-br from-white to-[color:var(--c-green-50)] border border-[color:var(--c-green-200)] text-left px-4 py-3 shadow-md hover:shadow-lg hover:scale-105 transition-all duration-200 cursor-default">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">📊</span>
                  <div>
                    <div className="text-[15px] font-semibold leading-4 text-[color:var(--c-green-800)]">Resúmenes automáticos</div>
                    <div className="text-[12px] opacity-70 mt-1 text-[color:var(--c-green-600)]">Análisis de contratos</div>
                  </div>
                </div>
              </div>
              <div className="h-[70px] rounded-2xl bg-gradient-to-br from-white to-[color:var(--c-green-50)] border border-[color:var(--c-green-200)] text-left px-4 py-3 shadow-md hover:shadow-lg hover:scale-105 transition-all duration-200 cursor-default">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">⚠️</span>
                  <div>
                    <div className="text-[15px] font-semibold leading-4 text-[color:var(--c-green-800)]">Recordatorios</div>
                    <div className="text-[12px] opacity-70 mt-1 text-[color:var(--c-green-600)]">Fechas de pago</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map(m => (
              <div key={m.id} className={m.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
                <div className={
                  'max-w-[85%] whitespace-pre-wrap rounded-2xl px-5 py-3 shadow-lg ' +
                  (m.role === 'user'
                    ? 'bg-gradient-to-r from-[color:var(--c-green-500)] to-[color:var(--c-green-600)] text-white'
                    : 'bg-gradient-to-br from-white to-[color:var(--c-green-50)] text-[color:var(--c-green-900)] border border-[color:var(--c-green-200)]')
                }>
                  {m.content}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Drop zone */}
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={onDrop}
        className="rounded-2xl border-2 border-dashed border-[color:var(--c-green-300)] bg-gradient-to-r from-[color:var(--c-green-100)] to-[color:var(--c-green-200)] p-4 text-[color:var(--c-green-800)] shadow-md hover:shadow-lg transition-all duration-200"
      >
        <div className="flex items-center justify-between">
          <div className="font-semibold text-base flex items-center gap-2">
            <span className="text-xl">📎</span>
            Arrastra PDFs aquí o haz click
          </div>
          <label className="cursor-pointer rounded-xl bg-gradient-to-r from-[color:var(--c-green-500)] to-[color:var(--c-green-600)] px-4 py-2 text-white font-medium shadow-md hover:shadow-lg hover:scale-105 transition-all duration-200">
            Elegir archivos
            <input type="file" multiple className="hidden" onChange={(e) => setFiles(prev => [...prev, ...Array.from(e.target.files || [])])} />
          </label>
        </div>
        {files.length > 0 && (
          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-3">
            {filePreviews}
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="flex items-end gap-3 rounded-2xl p-4 bg-gradient-to-r from-white to-[color:var(--c-green-50)] border border-[color:var(--c-green-200)] shadow-lg">
        <button
          onMouseDown={startRecording}
          onMouseUp={stopRecording}
          onTouchStart={startRecording}
          onTouchEnd={stopRecording}
          className={
            'h-11 w-11 shrink-0 rounded-full border-2 border-[color:var(--c-green-300)] shadow-md transition-all duration-200 ' +
            (isRecording 
              ? 'bg-gradient-to-r from-[color:var(--c-green-600)] to-[color:var(--c-green-700)] text-white scale-110' 
              : 'bg-white text-[color:var(--c-green-800)] hover:bg-[color:var(--c-green-100)] hover:scale-105')
          }
          title={isRecording ? 'Suelta para detener' : 'Mantén para grabar voz'}
        >
          <span className="text-lg">{isRecording ? '◉' : '🎤'}</span>
        </button>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Escribe tu mensaje..."
          rows={1}
          className="min-h-[44px] flex-1 resize-none rounded-xl border-2 border-[color:var(--c-green-300)] bg-white px-4 py-3 text-base outline-none focus:ring-2 focus:ring-[color:var(--c-green-400)] focus:border-[color:var(--c-green-500)] transition-all duration-200"
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
          className="h-11 shrink-0 rounded-xl bg-gradient-to-r from-[color:var(--c-green-600)] to-[color:var(--c-green-700)] px-6 text-white font-medium shadow-md hover:shadow-lg hover:scale-105 transition-all duration-200 disabled:opacity-60 disabled:hover:scale-100"
        >
          {uploading ? 'Enviando…' : 'Enviar ✈️'}
        </button>
      </div>
    </div>
  )
}
