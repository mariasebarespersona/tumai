import { NextRequest, NextResponse } from 'next/server'

/**
 * Import Excel template structure using Next.js Graph token (from web/.env.local)
 * This endpoint reads the Excel file via Microsoft Graph API and saves the structure
 * to the backend's Supabase database.
 */
export async function POST(req: NextRequest) {
  try {
    console.log('[Next.js Import] Starting import request...')
    const formData = await req.formData()
    const propertyId = formData.get('property_id') as string
    const templateKey = formData.get('template_key') as string
    const excelFileId = formData.get('excel_file_id') as string || process.env.EXCEL_FILE_ID || ''
    const token = process.env.GRAPH_ACCESS_TOKEN || ''
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:7901'

    console.log('[Next.js Import] Config check:', {
      hasPropertyId: !!propertyId,
      hasTemplateKey: !!templateKey,
      hasExcelFileId: !!excelFileId,
      hasToken: !!token,
      tokenLength: token.length,
      tokenHasDots: token.includes('.')
    })

    if (!propertyId || !templateKey) {
      return NextResponse.json({ ok: false, error: 'property_id and template_key are required' }, { status: 400 })
    }

    if (!excelFileId || !token) {
      console.error('[Next.js Import] Missing config:', { excelFileId: !!excelFileId, token: !!token })
      return NextResponse.json({ 
        ok: false, 
        error: 'EXCEL_FILE_ID and GRAPH_ACCESS_TOKEN must be configured in web/.env.local' 
      }, { status: 400 })
    }
    
    // Validate token format (should be a JWT with dots, but also accept session tokens)
    // JWT tokens start with 'eyJ' and have dots, session tokens start with 'EwB' and don't have dots
    const isJWT = token.startsWith('eyJ') && token.includes('.')
    const isSessionToken = token.startsWith('EwB') && !token.includes('.')
    
    if (!isJWT && !isSessionToken) {
      console.error('[Next.js Import] Invalid token format')
      return NextResponse.json({
        ok: false,
        error: 'GRAPH_ACCESS_TOKEN in web/.env.local is not a valid token. Please get a new token from Graph Explorer. JWT tokens should start with "eyJ" and have dots. Session tokens start with "EwB".'
      }, { status: 400 })
    }
    
    if (isSessionToken) {
      console.warn('[Next.js Import] Using session token (may not work for all operations)')
    }

    // Parse excel_file_id - can be "DRIVE_ID!ITEM_ID" or just "ITEM_ID"
    let baseUrl: string
    if (excelFileId.includes('!')) {
      const [driveId, itemId] = excelFileId.split('!', 2)
      baseUrl = `https://graph.microsoft.com/v1.0/drives/${driveId}/items/${itemId}`
    } else {
      baseUrl = `https://graph.microsoft.com/v1.0/me/drive/items/${excelFileId}`
    }

    // Create workbook session
    const sessionUrl = `${baseUrl}/workbook/createSession`
    const sessionResp = await fetch(sessionUrl, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ persistChanges: true })
    })

    if (!sessionResp.ok) {
      const errorText = await sessionResp.text().catch(() => '')
      if (sessionResp.status === 401) {
        return NextResponse.json({
          ok: false,
          error: 'InvalidAuthenticationToken: El token de Graph está expirado o es inválido. Por favor, actualiza GRAPH_ACCESS_TOKEN en web/.env.local con un token válido desde Graph Explorer.'
        }, { status: 401 })
      }
      return NextResponse.json({
        ok: false,
        error: `Session creation failed: ${sessionResp.status} - ${errorText.slice(0, 200)}`
      }, { status: sessionResp.status })
    }

    const sessionData = await sessionResp.json()
    const sessionId = sessionData.id
    const headers = {
      'Authorization': `Bearer ${token}`,
      'workbook-session-id': sessionId,
      'Content-Type': 'application/json'
    }

    // Read full range (A1:Z100 to capture structure)
    const rangeUrl = `${baseUrl}/workbook/worksheets('Sheet1')/range(address='A1:Z100')`
    const rangeResp = await fetch(rangeUrl, { headers })
    
    if (!rangeResp.ok) {
      const errorText = await rangeResp.text().catch(() => '')
      return NextResponse.json({
        ok: false,
        error: `Failed to read Excel range: ${rangeResp.status} - ${errorText.slice(0, 200)}`
      }, { status: rangeResp.status })
    }

    const rangeData = await rangeResp.json()
    const values = rangeData.values || []
    
    // Read formulas if available
    const formulasUrl = `${baseUrl}/workbook/worksheets('Sheet1')/range(address='A1:Z100')/formulas`
    let formulas: any[][] = []
    try {
      const formulasResp = await fetch(formulasUrl, { headers })
      if (formulasResp.ok) {
        const formulasData = await formulasResp.json()
        formulas = formulasData.formulas || []
      }
    } catch (e) {
      // Formulas are optional
    }

    // Read basic format (colors, bold, etc.)
    const formatUrl = `${baseUrl}/workbook/worksheets('Sheet1')/range(address='A1:Z100')/format`
    let formatData: any = {}
    try {
      const formatResp = await fetch(formatUrl, { headers })
      if (formatResp.ok) {
        formatData = await formatResp.json()
      }
    } catch (e) {
      // Format is optional
    }

    // Build structure JSON
    const structure: any = {
      rows: values.length,
      columns: values[0]?.length || 0,
      cells: []
    }

    // Detect headers (first row and first column)
    const headerRow: string[] = values[0] || []
    const headerCol: string[] = values.map(row => row[0]?.toString() || '').filter(v => v)

    structure.header_row = headerRow
    structure.header_col = headerCol

    // Build cells array with addresses, values, formulas, and format
    for (let row = 0; row < values.length; row++) {
      for (let col = 0; col < (values[row]?.length || 0); col++) {
        const cellAddress = `${String.fromCharCode(65 + col)}${row + 1}`
        const value = values[row]?.[col]
        const formula = formulas[row]?.[col] || null
        
        // Extract format for this cell
        const cellFormat: any = {}
        if (formatData.rows && formatData.rows[row] && formatData.rows[row].values && formatData.rows[row].values[col]) {
          const f = formatData.rows[row].values[col]
          if (f.fill) {
            cellFormat.bg_color = f.fill.color || null
          }
          if (f.font) {
            cellFormat.font_color = f.font.color || null
            cellFormat.bold = f.font.bold || false
          }
        }

        structure.cells.push({
          address: cellAddress,
          row: row + 1,
          col: col + 1,
          value: value?.toString() || '',
          formula: formula,
          format: cellFormat,
          row_label: row === 0 ? null : (values[row]?.[0]?.toString() || null),
          col_label: col === 0 ? null : (headerRow[col]?.toString() || null)
        })
      }
    }

    // Save structure to backend via Supabase RPC
    // We'll call the backend's endpoint that saves to Supabase
    const saveResp = await fetch(`${backendUrl}/api/numbers/save-template-structure`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        property_id: propertyId,
        template_key: templateKey,
        structure_json: structure
      })
    })

    if (!saveResp.ok) {
      const errorText = await saveResp.text().catch(() => '')
      return NextResponse.json({
        ok: false,
        error: `Failed to save structure to backend: ${saveResp.status} - ${errorText.slice(0, 200)}`
      }, { status: saveResp.status })
    }

    // Also save initial values to numbers_table_values
    const initialValues: any = {}
    for (const cell of structure.cells) {
      if (cell.value) {
        initialValues[cell.address] = {
          value: cell.value,
          row_label: cell.row_label,
          col_label: cell.col_label,
          format: cell.format
        }
      }
    }

    // Save initial values
    for (const [address, data] of Object.entries(initialValues)) {
      try {
        await fetch(`${backendUrl}/api/numbers/set-cell-value`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            property_id: propertyId,
            template_key: templateKey,
            cell_address: address,
            value: (data as any).value,
            row_label: (data as any).row_label,
            col_label: (data as any).col_label,
            format_json: (data as any).format
          })
        })
      } catch (e) {
        // Continue even if individual cell save fails
      }
    }

    return NextResponse.json({
      ok: true,
      template_key: templateKey,
      property_id: propertyId,
      cells_imported: structure.cells.length,
      rows: structure.rows,
      columns: structure.columns
    })

  } catch (error: any) {
    return NextResponse.json({
      ok: false,
      error: error?.message || String(error)
    }, { status: 500 })
  }
}

