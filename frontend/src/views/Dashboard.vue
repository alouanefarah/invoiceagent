<template>
  <div class="page">
    <div class="page-header">
      <h1>Dashboard</h1>
      <span class="text-muted mono" style="font-size:12px">{{ today }}</span>
    </div>

    <!-- KPI cards -->
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Total importées</div>
        <div class="kpi-value">{{ store.counts.total }}</div>
      </div>
      <div class="kpi-card success">
        <div class="kpi-label">Validées</div>
        <div class="kpi-value">{{ store.counts.validated }}</div>
        <div class="kpi-rate text-muted">{{ pct(store.counts.validated, store.counts.total) }}</div>
      </div>
      <div class="kpi-card danger">
        <div class="kpi-label">Anomalies</div>
        <div class="kpi-value">{{ store.counts.anomaly }}</div>
        <div class="kpi-rate text-muted">{{ pct(store.counts.anomaly, store.counts.total) }}</div>
      </div>
      <div class="kpi-card accent">
        <div class="kpi-label">En traitement</div>
        <div class="kpi-value">{{ store.counts.processing }}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Montant TTC total</div>
        <div class="kpi-value mono" style="font-size:20px">{{ totalTtc }}</div>
        <div class="kpi-rate text-muted">TND</div>
      </div>
    </div>

    <!-- Charts row -->
    <div class="charts-row">
      <!-- Donut statuts -->
      <div class="chart-card">
        <h2 class="section-title">Répartition par statut</h2>
        <div class="donut-wrap">
          <Doughnut v-if="donutData" :data="donutData" :options="donutOptions" />
          <div v-else class="no-data text-muted">Aucune donnée</div>
        </div>
      </div>

      <!-- Barre méthode OCR -->
      <div class="chart-card">
        <h2 class="section-title">Méthodes OCR utilisées</h2>
        <div class="bar-wrap">
          <Bar v-if="ocrBarData" :data="ocrBarData" :options="barOptions" />
          <div v-else class="no-data text-muted">Aucune donnée</div>
        </div>
      </div>

      <!-- Donut validation -->
      <div class="chart-card">
        <h2 class="section-title">Résultats de validation</h2>
        <div class="donut-wrap">
          <Doughnut v-if="valData" :data="valData" :options="donutOptions" />
          <div v-else class="no-data text-muted">Aucune donnée</div>
        </div>
      </div>
    </div>

    <!-- Anomalies récentes -->
    <div class="anomalies-section" v-if="anomalies.length">
      <h2 class="section-title">⚠ Anomalies à traiter</h2>
      <div class="anomaly-list">
        <div v-for="inv in anomalies" :key="inv.id" class="anomaly-row"
          @click="$router.push(`/invoices/${inv.id}`)">
          <div class="anomaly-icon">⚠</div>
          <div class="anomaly-body">
            <div class="anomaly-vendor">{{ inv.vendor_name || inv.filename }}</div>
            <div class="anomaly-reason text-muted">{{ inv.processing_log?.[0]?.validation_reason || 'Erreur extraction' }}</div>
          </div>
          <div class="anomaly-amount mono">{{ inv.amount_ttc ? inv.amount_ttc.toFixed(3) : '—' }} TND</div>
          <div class="anomaly-arrow">→</div>
        </div>
      </div>
    </div>

    <!-- Activité récente -->
    <div class="activity-section">
      <h2 class="section-title">Activité récente</h2>
      <div class="activity-list">
        <div v-for="inv in store.list.slice(0, 8)" :key="inv.id" class="activity-item"
          @click="$router.push(`/invoices/${inv.id}`)">
          <div class="act-status-bar" :class="inv.status"></div>
          <div class="act-body">
            <span class="act-vendor">{{ inv.vendor_name || '—' }}</span>
            <span class="act-num mono text-muted">{{ inv.invoice_number || inv.filename }}</span>
          </div>
          <span class="act-ttc mono">{{ inv.amount_ttc ? inv.amount_ttc.toFixed(3) : '—' }}</span>
          <StatusBadge :status="inv.status" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { Doughnut, Bar } from 'vue-chartjs'
import { Chart as ChartJS, ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement } from 'chart.js'
import { useInvoicesStore } from '@/stores/invoices'
import StatusBadge from '@/components/StatusBadge.vue'

ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale, LinearScale, BarElement)

const store = useInvoicesStore()

onMounted(() => store.fetchList())

const today = new Date().toLocaleDateString('fr-FR', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })

const anomalies = computed(() => store.list.filter(i => i.status === 'anomaly'))

const totalTtc = computed(() => {
  const sum = store.list.filter(i => i.amount_ttc).reduce((acc, i) => acc + Number(i.amount_ttc), 0)
  return sum.toLocaleString('fr-TN', { minimumFractionDigits: 3 })
})

function pct(a, b) { return b ? (a / b * 100).toFixed(0) + '%' : '—' }

// Donut statuts
const donutData = computed(() => {
  const { validated, anomaly, processing } = store.counts
  const pending = store.list.filter(i => i.status === 'pending').length
  if (!store.counts.total) return null
  return {
    labels: ['Validées', 'Anomalies', 'En cours', 'En attente'],
    datasets: [{ data: [validated, anomaly, processing, pending],
      backgroundColor: ['#22C55E', '#EF4444', '#6C63FF', '#475569'],
      borderWidth: 0, hoverOffset: 6 }]
  }
})

// Barre OCR
const ocrBarData = computed(() => {
  const counts = {}
  store.list.forEach(i => {
    const m = i.processing_log?.[0]?.ocr_method || 'unknown'
    counts[m] = (counts[m] || 0) + 1
  })
  if (!Object.keys(counts).length) return null
  return {
    labels: Object.keys(counts),
    datasets: [{ label: 'Factures', data: Object.values(counts),
      backgroundColor: '#6C63FF88', borderColor: '#6C63FF', borderWidth: 1, borderRadius: 4 }]
  }
})

// Donut validation
const valData = computed(() => {
  const ok      = store.list.filter(i => i.validation_status === 'ok').length
  const mismatch= store.list.filter(i => i.validation_status === 'mismatch').length
  const skipped = store.list.filter(i => i.validation_status === 'skipped').length
  if (!store.counts.total) return null
  return {
    labels: ['OK', 'Mismatch', 'Non calculé'],
    datasets: [{ data: [ok, mismatch, skipped],
      backgroundColor: ['#22C55E', '#EF4444', '#475569'],
      borderWidth: 0, hoverOffset: 6 }]
  }
})

const donutOptions = { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { color: '#94A3B8', font: { size: 11 }, padding: 12 } } }, cutout: '68%' }
const barOptions   = { responsive: true, maintainAspectRatio: false, scales: { x: { ticks: { color: '#94A3B8' }, grid: { color: '#252A3A' } }, y: { ticks: { color: '#94A3B8' }, grid: { color: '#252A3A' } } }, plugins: { legend: { display: false } } }
</script>

<style scoped>
.page { padding: 32px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 28px; }
.page-header h1 { font-size: 22px; font-weight: 700; }

.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 28px; }
.kpi-card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px; }
.kpi-card.success { border-left: 3px solid var(--success); }
.kpi-card.danger  { border-left: 3px solid var(--danger);  }
.kpi-card.accent  { border-left: 3px solid var(--accent);  }
.kpi-label { font-size: 11px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px; }
.kpi-value { font-size: 28px; font-weight: 700; line-height: 1; margin-bottom: 4px; }
.kpi-rate  { font-size: 12px; }

.charts-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; margin-bottom: 28px; }
.chart-card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px; }
.section-title { font-size: 11px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 14px; }
.donut-wrap, .bar-wrap { height: 180px; position: relative; }
.no-data { display: flex; align-items: center; justify-content: center; height: 100%; font-size: 12px; }

.anomalies-section { margin-bottom: 28px; }
.anomaly-list { display: flex; flex-direction: column; gap: 6px; }
.anomaly-row { display: flex; align-items: center; gap: 14px; background: var(--danger-dim); border: 1px solid var(--danger)33; border-radius: var(--radius); padding: 12px 16px; cursor: pointer; transition: border-color 0.15s; }
.anomaly-row:hover { border-color: var(--danger); }
.anomaly-icon { font-size: 16px; color: var(--danger); flex-shrink: 0; }
.anomaly-body { flex: 1; min-width: 0; }
.anomaly-vendor { font-size: 13px; font-weight: 500; }
.anomaly-reason { font-size: 11px; margin-top: 2px; }
.anomaly-amount { font-size: 13px; color: var(--danger); flex-shrink: 0; }
.anomaly-arrow { color: var(--text-muted); font-size: 14px; }

.activity-section { }
.activity-list { display: flex; flex-direction: column; gap: 4px; }
.activity-item { display: flex; align-items: center; gap: 12px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 10px 14px; cursor: pointer; transition: border-color 0.15s; }
.activity-item:hover { border-color: var(--accent); }
.act-status-bar { width: 4px; height: 32px; border-radius: 2px; flex-shrink: 0; }
.act-status-bar.validated  { background: var(--success); }
.act-status-bar.anomaly    { background: var(--danger);  }
.act-status-bar.processing { background: var(--accent);  }
.act-status-bar.pending    { background: var(--border);  }
.act-body { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.act-vendor { font-size: 13px; font-weight: 500; }
.act-num    { font-size: 11px; }
.act-ttc    { font-size: 13px; font-weight: 600; flex-shrink: 0; }
</style>
