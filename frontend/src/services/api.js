import axios from 'axios'

const http = axios.create({ baseURL: '/api' })

export const api = {
  // Factures
  listInvoices:  (params = {}) => http.get('/invoices/', { params }),
  getInvoice:    (id)          => http.get(`/invoices/${id}`),
  processInvoice:(id)          => http.post(`/process/${id}`),
  uploadInvoice: (file, onProgress) => {
    const form = new FormData()
    form.append('file', file)
    return http.post('/upload/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: e => onProgress && onProgress(Math.round(e.loaded * 100 / e.total))
    })
  },
  // Dashboard
  getDashboard: () => http.get('/dashboard/'),
}
