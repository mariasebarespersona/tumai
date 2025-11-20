'use client'

import { useState } from 'react'

interface FeedbackButtonsProps {
  messageId: string
  agentName: string
  userMessage: string
  agentResponse: string
  toolCalls?: any[]
  toolResults?: any[]
  propertyId?: string | null
}

export function FeedbackButtons({
  messageId,
  agentName,
  userMessage,
  agentResponse,
  toolCalls = [],
  toolResults = [],
  propertyId
}: FeedbackButtonsProps) {
  const [rated, setRated] = useState(false)
  const [showCommentBox, setShowCommentBox] = useState(false)
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleFeedback = async (rating: 1 | -1) => {
    if (rated) return

    if (rating === -1) {
      // Show comment box for negative feedback
      setShowCommentBox(true)
      return
    }

    // For positive feedback, submit immediately
    await submitFeedback(rating, null)
  }

  const submitFeedback = async (rating: number, commentText: string | null) => {
    setSubmitting(true)

    try {
      const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:7901'
      
      const response = await fetch(`${BACKEND_URL}/api/feedback`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message_id: messageId,
          rating,
          comment: commentText,
          property_id: propertyId,
          agent_name: agentName,
          user_message: userMessage,
          agent_response: agentResponse,
          tool_calls: toolCalls,
          tool_results: toolResults,
        }),
      })

      if (!response.ok) {
        throw new Error(`Failed to submit feedback: ${response.status}`)
      }

      const data = await response.json()
      
      if (data.ok) {
        setRated(true)
        setShowCommentBox(false)
        // Show success message briefly
        console.log('✅ Feedback submitted:', data.message)
      } else {
        console.error('❌ Feedback error:', data.error)
      }
    } catch (error) {
      console.error('❌ Error submitting feedback:', error)
    } finally {
      setSubmitting(false)
    }
  }

  if (rated) {
    return (
      <div className="mt-3 text-xs text-[color:var(--c-green-600)] font-medium flex items-center gap-1">
        <span>✅</span>
        <span>¡Gracias por tu feedback!</span>
      </div>
    )
  }

  return (
    <div className="mt-3">
      {/* Feedback buttons */}
      {!showCommentBox && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-[color:var(--c-green-600)] font-medium">¿Fue útil?</span>
          <button
            onClick={() => handleFeedback(1)}
            disabled={submitting}
            className="px-3 py-1.5 rounded-xl bg-[color:var(--c-green-100)] hover:bg-[color:var(--c-green-200)] text-[color:var(--c-green-700)] font-semibold transition-all duration-200 hover:scale-105 disabled:opacity-50 disabled:hover:scale-100"
            title="Respuesta útil"
          >
            👍
          </button>
          <button
            onClick={() => handleFeedback(-1)}
            disabled={submitting}
            className="px-3 py-1.5 rounded-xl bg-red-100 hover:bg-red-200 text-red-700 font-semibold transition-all duration-200 hover:scale-105 disabled:opacity-50 disabled:hover:scale-100"
            title="Respuesta no útil"
          >
            👎
          </button>
        </div>
      )}

      {/* Comment box (shows on thumbs down) */}
      {showCommentBox && (
        <div className="mt-2 rounded-xl border-2 border-red-300 bg-red-50 p-3 space-y-2">
          <div className="text-sm text-red-800 font-semibold">¿Qué podríamos mejorar?</div>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Tu comentario nos ayuda a mejorar..."
            rows={3}
            className="w-full resize-none rounded-lg border-2 border-red-200 bg-white px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-red-400 focus:border-red-400"
          />
          <div className="flex gap-2">
            <button
              onClick={() => submitFeedback(-1, comment)}
              disabled={submitting}
              className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white font-semibold text-sm transition-all duration-200 hover:scale-105 disabled:opacity-50 disabled:hover:scale-100"
            >
              {submitting ? '⏳ Enviando...' : 'Enviar'}
            </button>
            <button
              onClick={() => {
                setShowCommentBox(false)
                setComment('')
              }}
              className="px-4 py-2 rounded-lg bg-gray-200 hover:bg-gray-300 text-gray-700 font-semibold text-sm transition-all duration-200"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

