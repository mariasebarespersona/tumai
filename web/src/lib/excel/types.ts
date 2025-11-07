export type ExcelAddress = string
export type ExcelValues = any[][] | any

export type ExcelEvent = {
  type: 'cellChanged'
  address: ExcelAddress
  value?: any
  at: string
}


