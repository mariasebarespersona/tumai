MCP excel.* tools

- excel.get_range
  - input: { address: string, workbookId?: string }
  - output: { values: any[][], address: string }
  - errors: invalid_range, not_found

- excel.set_range
  - input: { address: string, values: any[][] | any, workbookId?: string }
  - output: { wrote: any[][] | any, address: string }
  - errors: address_required, write_failed

- excel.append_row
  - input: { tableName: string, values: any[] | any, workbookId?: string }
  - output: { appended: any[], index: number }
  - errors: table_not_found

Example prompts
- "Leer rango A1:B10"
- "Escribe en A1 el texto 'Hola'"
- "Añade una fila a la tabla Tabla1 con ['Concepto', 1200]"

