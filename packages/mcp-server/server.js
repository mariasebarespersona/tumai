#!/usr/bin/env node
// Minimal MCP-like JSON-RPC server for excel.* tools
// No external deps; dev-only scaffold

const http = require('http')

const PORT = process.env.MCP_PORT ? Number(process.env.MCP_PORT) : 4310
const MODE = (process.env.MCP_MODE || 'OFFICEJS').toUpperCase()
const WEB_BASE = process.env.WEB_BASE || 'http://127.0.0.1:3000'

function json(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json' })
  res.end(JSON.stringify(body))
}

function notFound(res) { json(res, 404, { error: 'not_found' }) }

async function handleRpc(method, params) {
  const started = Date.now()
  try {
    if (!method || !method.startsWith('excel.')) {
      throw Object.assign(new Error('unknown_method'), { code: 'unknown_method' })
    }

    if (MODE === 'GRAPH') {
      // Proxy to Next.js API (Graph fallback)
      if (method === 'excel.get_range') {
        const resp = await fetch(`${WEB_BASE}/api/excel/getRange`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(params || {})
        })
        const data = await resp.json()
        return { ok: true, mode: MODE, data, ms: Date.now() - started }
      }
      if (method === 'excel.set_range') {
        const resp = await fetch(`${WEB_BASE}/api/excel/setRange`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(params || {})
        })
        const data = await resp.json()
        return { ok: true, mode: MODE, data, ms: Date.now() - started }
      }
      if (method === 'excel.append_row') {
        const resp = await fetch(`${WEB_BASE}/api/excel/appendRow`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(params || {})
        })
        const data = await resp.json()
        return { ok: true, mode: MODE, data, ms: Date.now() - started }
      }
    }
    // OFFICEJS mode: try to forward to an attached add-in via WebSocket broker
    if (MODE === 'OFFICEJS') {
      try {
        const propId = (params && (params.propertyId || params.workbookId)) || null
        let ws = null
        if (propId && clientsByProperty.has(propId)) ws = clientsByProperty.get(propId)
        // fallback to any connected client
        if (!ws) {
          for (const [k,v] of clientsByProperty.entries()) { ws = v; break }
        }
        if (ws && ws.readyState === ws.OPEN) {
          const rpcId = String(Date.now()) + '-' + Math.floor(Math.random()*1000)
          const payload = JSON.stringify({ id: rpcId, type: 'rpc', method, params })
          const promise = new Promise((resolve, reject) => {
            const to = setTimeout(() => { pending.delete(rpcId); reject(new Error('timeout')) }, 5000)
            pending.set(rpcId, { resolve: (r) => { clearTimeout(to); resolve(r) }, reject: (e) => { clearTimeout(to); reject(e) } })
          })
          ws.send(payload)
          const result = await promise.catch(e => ({ ok: false, error: { message: e.message } }))
          return { ok: true, mode: MODE, data: result, ms: Date.now() - started }
        }
      } catch (e) {
        console.warn('[MCP] websocket forward failed:', e)
      }
    }

    // If no WS client or forward failed: instruct client to use officejs-adapter or fallback to proxy
    return { ok: true, mode: MODE, proxy: 'officejs-client', ms: Date.now() - started }
  } catch (e) {
    return { ok: false, mode: MODE, error: { message: e.message, code: e.code || 'internal_error' }, ms: Date.now() - started }
  }
}

const server = http.createServer(async (req, res) => {
  // CORS headers for browser clients (dev only)
  res.setHeader('Access-Control-Allow-Origin', process.env.MCP_CORS_ORIGIN || '*')
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type,Authorization')
  res.setHeader('Access-Control-Max-Age', '86400')

  // Handle preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(204)
    return res.end()
  }

  if (req.method === 'POST' && req.url === '/jsonrpc') {
    let body = ''
    req.on('data', chunk => body += chunk)
    req.on('end', async () => {
      try {
        const { id, method, params } = JSON.parse(body || '{}')
        const result = await handleRpc(method, params)
        json(res, 200, { jsonrpc: '2.0', id: id || null, result })
      } catch (e) {
        json(res, 400, { jsonrpc: '2.0', id: null, error: { code: -32700, message: 'Parse error', details: e.message } })
      }
    })
    return
  }
  if (req.method === 'GET' && req.url === '/') {
    return json(res, 200, { status: 'ok', mode: MODE, tools: ['excel.get_range','excel.set_range','excel.append_row'] })
  }
  return notFound(res)
})

// --- WebSocket broker (same process) ---
let WebSocket
try { WebSocket = require('ws') } catch (e) { WebSocket = null }

// pending RPCs forwarded to add-in clients
const pending = new Map()
const clientsByProperty = new Map()

if (WebSocket) {
  const wss = new WebSocket.Server({ noServer: true })

  server.on('upgrade', (req, socket, head) => {
    // handle websocket upgrade at /ws
    if (req.url && req.url.startsWith('/ws')) {
      wss.handleUpgrade(req, socket, head, (ws) => {
        wss.emit('connection', ws, req)
      })
    } else {
      socket.destroy()
    }
  })

  wss.on('connection', (ws, req) => {
    ws.isAlive = true
    ws.on('pong', () => ws.isAlive = true)

    ws.on('message', (raw) => {
      try {
        const msg = JSON.parse(raw.toString())
        // register: { type: 'register', propertyId }
        if (msg && msg.type === 'register' && msg.propertyId) {
          clientsByProperty.set(msg.propertyId, ws)
          ws._propertyId = msg.propertyId
          console.log(`[MCP WS] client registered for property ${msg.propertyId}`)
          return
        }
        // response: { type: 'response', id, result }
        if (msg && msg.type === 'response' && msg.id) {
          const p = pending.get(msg.id)
          if (p) {
            pending.delete(msg.id)
            p.resolve(msg.result)
          }
          return
        }
      } catch (e) {
        console.warn('[MCP WS] invalid message', e)
      }
    })

    ws.on('close', () => {
      if (ws._propertyId) {
        clientsByProperty.delete(ws._propertyId)
      }
    })
  })

  // heartbeat
  setInterval(() => {
    wss.clients.forEach((ws) => {
      if (!ws.isAlive) return ws.terminate()
      ws.isAlive = false
      ws.ping(() => {})
    })
  }, 30000)
}

server.listen(PORT, () => {
  console.log(`[MCP] server listening on http://127.0.0.1:${PORT} (mode=${MODE}) → proxy to ${WEB_BASE}`)
  if (!WebSocket) console.warn('[MCP] ws module not available: WebSocket broker disabled. Install `ws` to enable. `npm install ws` in packages/mcp-server')
})



