<template>
  <div class="page">
    <div class="page-header">
      <h1>Factures</h1>
      <div class="header-actions">
        <div class="filter-tabs">
          <button v-for="f in filters" :key="f.value"
            class="filter-tab" :class="{ active: activeFilter === f.value }"
            @click="activeFilter = f.value">
            {{ f.label }}
            <span class="tab-count">{{ f.value === 'all' ? store.list.length : store.counts[f.value] || 0 }}</span>
          </button>
        </div>
        <button class="btn-refresh" @click="store.fetchList()" :disabled="store.loading">
          <span :class="{ spinning: store.loading }">↻</span>
        </button>
      </div>
    </div>

    <!-- Table -->
    <div class="table-wrap">
      <table class="inv-table">
        <thead>
          <tr>
            <th>Statut</th>
            <th>Fournisseur</th>
            <th>N° Facture</th>
            <th>Date</th>
            <th class="right">HT</th>
            <th class="right">TVA</th>
            <th class="right">TTC</th>
            <th>OCR</th>
            <th>Validation</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <!-- Skeleton while loading -->
          <template v-if="store.loading">
            <tr v-for="i in 5" :key="i" class="skeleton-row">
              <td><div class="skeleton" style="width:80px;height:20px"></div></td>
              <td><div class="skeleton" style="width:160px;height:14px"></div></td>
              <td><div class="skeleton" style="width:90px;height:14px"></div></td>
              <td><div class="skeleton" style="width:80px;height:14px"></div></td>
              <td><div class="skeleton" style="width:70px;height:14px;margin-left:auto"></div></td>
              <td><div class="skeleton" style="width:60px;height:14px;margin-left:auto"></div></td>
              <td><div class="skeleton" style="width:80px;height:14px;margin-left:auto"></div></td>
              <td><div class="skeleton" style="width:60px;height:14px"></div></td>
              <td><div class="skeleton" style="width:50px;height:14px"></div></td>
              <td></td>
            </tr>
          </template>

          <template v-else>
            <tr v-for="inv in filtered" :key="inv.id" class="inv-row"
              @click="$router.push(`/invoices/${inv.id}`)">
              <td><StatusBadge :status="inv.status" /></td>
              <td class="vendor-cell">{{ inv.vendor_name || '—' }}</td>
              <td class="mono" style="font-size:12px">{{ inv.invoice_number || '—' }}</td>
              <td class="mono" style="font-size:12px">{{ formatDate(inv.invoice_date) }}</td>
              <td class="mono right">{{ fmt(inv.amount_ht) }}</td>
              <td class="mono right">{{ fmt(inv.amount_tva) }}</td>
              <td class="mono right bold">{{ fmt(inv.amount_ttc) }}</td>
              <td>
                <span class="ocr-badge" :title="`Confiance ${inv.confidence}%`">
                  {{ inv.ocr_method || '—' }}
                </span>
              </td>
              <td>
                <span class="val-badge" :class="inv.validation_status">
                  {{ inv.validation_status || '—' }}
                </span>
              </td>
              <td>
                <button class="btn-icon" title="Retraiter"
                  @click.stop="store.reprocess(inv.id)">↻</button>
              </td>
            </tr>

            <tr v-if="!filtered.length">
              <td colspan="10" class="empty">Aucune facture {{ activeFilter !== 'all' ? activeFilter : '' }}</td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useInvoicesStore } from '@/stores/invoices'
import StatusBadge from '@/components/StatusBadge.vue'

const store = useInvoicesStore()
const activeFilter = ref('all')

const filters = [
  { label: 'Toutes',     value: 'all' },
  { label: 'Validées',   value: 'validated' },
  { label: 'Anomalies',  value: 'anomaly' },
  { label: 'En cours',   value: 'processing' },
]

const filtered = computed(() =>
  activeFilter.value === 'all'
    ? store.list
    : store.list.filter(i => i.status === activeFilter.value)
)

function fmt(val) {
  if (val == null) return '—'
  return Number(val).toLocaleString('fr-TN', { minimumFractionDigits: 3 }) + ' د'
}
function formatDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: '2-digit' })
}
</script>

<style scoped>
.page { padding: 32px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; flex-wrap: wrap; gap: 12px; }
.page-header h1 { font-size: 22px; font-weight: 700; }

.header-actions { display: flex; align-items: center; gap: 12px; }
.filter-tabs { display: flex; gap: 4px; background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 3px; }
.filter-tab { background: none; border: none; color: var(--text-secondary); padding: 5px 12px; border-radius: 5px; cursor: pointer; font-size: 12px; font-weight: 500; display: flex; align-items: center; gap: 6px; transition: all 0.15s; }
.filter-tab:hover  { color: var(--text-primary); background: var(--bg-hover); }
.filter-tab.active { background: var(--bg-elevated); color: var(--text-primary); }
.tab-count { background: var(--bg-base); border-radius: 10px; padding: 1px 6px; font-size: 10px; color: var(--text-secondary); }

.btn-refresh { background: none; border: 1px solid var(--border); color: var(--text-secondary); width: 32px; height: 32px; border-radius: var(--radius); cursor: pointer; font-size: 16px; transition: all 0.15s; }
.btn-refresh:hover { color: var(--text-primary); border-color: var(--accent); }
@keyframes spin { to { transform: rotate(360deg); } }
.spinning { display: inline-block; animation: spin 0.8s linear infinite; }

.table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: var(--radius-lg); background: var(--bg-surface); }
.inv-table { width: 100%; border-collapse: collapse; }
.inv-table thead th { padding: 10px 14px; font-size: 11px; font-weight: 600; color: var(--text-secondary); text-align: left; text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid var(--border); white-space: nowrap; }
.inv-table th.right { text-align: right; }
.inv-row { border-bottom: 1px solid var(--border-subtle); cursor: pointer; transition: background 0.1s; }
.inv-row:hover { background: var(--bg-hover); }
.inv-row td { padding: 11px 14px; font-size: 13px; white-space: nowrap; }
.right { text-align: right; }
.bold { font-weight: 600; }
.vendor-cell { max-width: 180px; overflow: hidden; text-overflow: ellipsis; }

.ocr-badge { font-size: 10px; font-family: var(--font-mono); background: var(--bg-elevated); padding: 2px 6px; border-radius: 4px; color: var(--text-secondary); }
.val-badge { font-size: 10px; font-weight: 600; padding: 2px 7px; border-radius: 10px; text-transform: uppercase; }
.val-badge.ok { background: var(--success-dim); color: var(--success); }
.val-badge.mismatch { background: var(--danger-dim); color: var(--danger); }
.val-badge.skipped { background: var(--bg-elevated); color: var(--text-secondary); }

.btn-icon { background: none; border: none; color: var(--text-muted); cursor: pointer; font-size: 15px; padding: 4px; border-radius: 4px; transition: color 0.15s; }
.btn-icon:hover { color: var(--accent); }

.skeleton-row td { padding: 13px 14px; }
.empty { text-align: center; color: var(--text-muted); padding: 48px !important; font-size: 13px; }
</style>
