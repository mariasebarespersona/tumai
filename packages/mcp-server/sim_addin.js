#!/usr/bin/env node
// Simple simulated add-in that registers to the MCP WS broker and responds to RPCs
const WebSocket = require('ws')

const WS_URL = process.env.MCP_WS_URL || 'ws://127.0.0.1:4310/ws'
const PROPERTY_ID = process.env.PROPERTY_ID || '54d5729b-7e42-4d7f-83ef-024e76fbb6fb'

console.log(`[sim_addin] connecting to ${WS_URL} as property ${PROPERTY_ID}`)
const ws = new WebSocket(WS_URL)

ws.on('open', () => {
  console.log('[sim_addin] ws open, registering...')
  ws.send(JSON.stringify({ type: 'register', propertyId: PROPERTY_ID }))
})

ws.on('message', async (raw) => {
  try {
    const msg = JSON.parse(raw.toString())
    // handle rpc
    if (msg && msg.type === 'rpc') {
      console.log('[sim_addin] rpc received', msg.method, msg.id)
      if (msg.method === 'excel.get_range') {
        // return a mock 2x2 values matrix
        const result = { values: [["mock", 123], ["data", 456]] }
        ws.send(JSON.stringify({ type: 'response', id: msg.id, result }))
        console.log('[sim_addin] responded get_range')
      } else if (msg.method === 'excel.set_range') {
        const result = { ok: true, address: msg.params && msg.params.address }
        ws.send(JSON.stringify({ type: 'response', id: msg.id, result }))
        console.log('[sim_addin] responded set_range')
      } else if (msg.method === 'excel.append_row') {
        const result = { ok: true }
        ws.send(JSON.stringify({ type: 'response', id: msg.id, result }))
        console.log('[sim_addin] responded append_row')
      } else if (msg.method === 'excel.inject_addresses') {
        const result = { ok: true, created: 'RAMA_Addresses' }
        ws.send(JSON.stringify({ type: 'response', id: msg.id, result }))
        console.log('[sim_addin] responded inject_addresses')
      } else {
        ws.send(JSON.stringify({ type: 'response', id: msg.id, result: { error: 'unsupported_method' } }))
      }
    }
  } catch (e) { console.error('[sim_addin] parse error', e) }
})

ws.on('close', () => console.log('[sim_addin] ws closed'))
ws.on('error', (e) => console.error('[sim_addin] ws error', e))

// keep alive
setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) ws.ping()
}, 30000)


