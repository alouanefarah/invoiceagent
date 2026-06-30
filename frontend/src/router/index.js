import { createRouter, createWebHistory } from 'vue-router'
import Dashboard  from '@/views/Dashboard.vue'
import Invoices   from '@/views/Invoices.vue'
import InvoiceDetail from '@/views/InvoiceDetail.vue'
import Upload     from '@/views/Upload.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',           component: Dashboard,     name: 'dashboard' },
    { path: '/invoices',   component: Invoices,      name: 'invoices' },
    { path: '/invoices/:id', component: InvoiceDetail, name: 'invoice-detail', props: true },
    { path: '/upload',     component: Upload,        name: 'upload' },
  ],
})
