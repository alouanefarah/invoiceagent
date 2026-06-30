import { defineStore } from 'pinia'
import { api } from '@/services/api'

export const useInvoicesStore = defineStore('invoices', {
  state: () => ({
    list:      [],
    current:   null,
    dashboard: null,
    loading:   false,
    uploading: false,
    uploadProgress: 0,
    polling:   {},     // { [id]: intervalId }
  }),

  getters: {
    byStatus: (s) => (status) => s.list.filter(i => i.status === status),
    counts: (s) => ({
      total:      s.list.length,
      validated:  s.list.filter(i => i.status === 'validated').length,
      anomaly:    s.list.filter(i => i.status === 'anomaly').length,
      processing: s.list.filter(i => ['pending','processing'].includes(i.status)).length,
    }),
  },

  actions: {
    async fetchList(params = {}) {
      this.loading = true
      try {
        const { data } = await api.listInvoices(params)
        this.list = data
      } finally {
        this.loading = false
      }
    },

    async fetchOne(id) {
      const { data } = await api.getInvoice(id)
      this.current = data
      const idx = this.list.findIndex(i => i.id === id)
      if (idx >= 0) this.list[idx] = data
      return data
    },

    async upload(file) {
      this.uploading = true
      this.uploadProgress = 0
      try {
        const { data } = await api.uploadInvoice(file, p => { this.uploadProgress = p })
        await this.fetchList()
        this.startPolling(data.invoice_id)
        return data
      } finally {
        this.uploading = false
      }
    },

    startPolling(id) {
      if (this.polling[id]) return
      const interval = setInterval(async () => {
        const inv = await this.fetchOne(id)
        if (!['pending', 'processing'].includes(inv.status)) {
          clearInterval(this.polling[id])
          delete this.polling[id]
        }
      }, 2500)
      this.polling[id] = interval
    },

    async fetchDashboard() {
      const { data } = await api.getDashboard()
      this.dashboard = data
    },

    async reprocess(id) {
      await api.processInvoice(id)
      this.startPolling(id)
    },
  },
})
