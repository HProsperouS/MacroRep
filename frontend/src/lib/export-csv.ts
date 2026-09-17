/** Builds a CSV (RFC 4180 quoting) and triggers a browser download. */
export function downloadCsv(filename: string, header: string[], rows: (string | number | null)[][]) {
  const escape = (value: string | number | null) => {
    const text = value == null ? "" : String(value)
    return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
  }
  const csv = [header, ...rows].map((row) => row.map(escape).join(",")).join("\n")
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }))
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
