<template>
  <div class="page" :dir="isRtl ? 'rtl' : 'ltr'">
    <button class="btn-back" @click="$router.push('/invoices')">← Retour</button>

    <div v-if="loading" class="loading-state">
      <div class="skeleton" style="width:220px;height:28px;margin-bottom:8px"></div>
      <div class="skeleton" style="width:140px;height:18px"></div>
    </div>

    <template v-else-if="inv">

      <!-- ── En-tête ── -->
      <div class="detail-header">
        <div>
          <div class="detail-vendor">{{ inv.vendor_name || 'Fournisseur inconnu' }}</div>
          <div class="detail-num mono">{{ inv.invoice_number || 'N° inconnu' }}</div>
        </div>
        <div class="header-right">
          <StatusBadge :status="inv.status" />
          <button class="btn-reprocess" @click="reprocess" :disabled="reprocessing">
            {{ reprocessing ? '…' : '↻ Retraiter' }}
          </button>
        </div>
      </div>

      <!-- ── Alertes ── -->
      <div v-if="inv.validation_status === 'mismatch'" class="alert danger">
        <strong>⚠ Incohérence mathématique</strong>
        <p>{{ inv.processing_log?.[0]?.validation_reason }}</p>
        <p class="mono">Écart : {{ inv.validation_delta?.toFixed(3) }} TND</p>
      </div>
      <div v-if="inv.processing_log?.[0]?.timbre_suspect" class="alert warning">
        <strong>⚠ Timbre fiscal suspect</strong>
        <p>Valeur extraite ({{ inv.timbre_fiscal }} DT) probablement erronée — à vérifier.</p>
      </div>

      <!-- ── Grille principale ── -->
      <div class="main-grid">

        <!-- COLONNE 1 -->
        <div class="col">

          <!-- Identification -->
          <div class="card">
            <div class="card-title">📄 Identification</div>
            <div class="fields">
              <Field label="N° Facture"     :value="inv.invoice_number" mono />
              <Field label="Date facture"   :value="fmtDate(inv.invoice_date)" />
              <Field label="Date échéance"  :value="fmtDate(inv.due_date)" />
              <Field label="Langue"         :value="inv.language" />
              <Field label="Juridiction"    :value="inv.jurisdiction" mono />
              <Field label="Devise"         :value="inv.currency" mono />
              <Field label="Statut"         :value="inv.status" />
              <Field label="Validation"     :value="inv.validation_status" />
            </div>
          </div>

          <!-- Fournisseur -->
          <div class="card">
            <div class="card-title">🏢 Fournisseur</div>
            <div class="fields">
              <Field label="Nom"             :value="inv.vendor_name" />
              <Field label="Matricule fiscal" :value="inv.vendor_tax_id" mono />
              <Field label="Adresse"         :value="inv.vendor_address" />
              <Field label="Pays"            :value="inv.vendor_country" mono />
              <Field label="Email"           :value="inv.vendor_email" />
              <Field label="Téléphone"       :value="inv.vendor_phone" mono />
              <Field label="Fournisseur connu" :value="inv.vendor_is_known === true ? 'Oui' : inv.vendor_is_known === false ? 'Non' : null" />
            </div>
          </div>

        </div>

        <!-- COLONNE 2 -->
        <div class="col">

          <!-- Montants -->
          <div class="card">
            <div class="card-title">💰 Montants</div>
            <div class="fields">
              <Field label="Montant HT"    :value="fmt3(inv.amount_ht)"    mono suffix="TND" />
              <Field label="Taux TVA"      :value="inv.tva_rate ? inv.tva_rate + '%' : null" mono />
              <Field label="Montant TVA"   :value="fmt3(inv.amount_tva)"   mono suffix="TND" />
              <Field label="Timbre fiscal" :value="fmt3(inv.timbre_fiscal)" mono suffix="TND" />
              <div class="field-separator"></div>
              <Field label="Total TTC"     :value="fmt3(inv.amount_ttc)"   mono suffix="TND" highlight />
              <Field v-if="inv.validation_delta" label="Écart validation" :value="fmt3(inv.validation_delta)" mono suffix="TND" danger />
            </div>
          </div>

          <!-- Fichier & Pipeline -->
          <div class="card">
            <div class="card-title">⚙️ Fichier & Pipeline</div>
            <div class="fields">
              <Field label="Fichier"         :value="inv.filename" />
              <Field label="Type MIME"       :value="inv.mime_type" mono />
              <Field label="Taille"          :value="inv.file_size_bytes ? (inv.file_size_bytes / 1024).toFixed(0) + ' Ko' : null" mono />
              <Field label="Méthode OCR"     :value="inv.processing_log?.[0]?.ocr_method" mono />
              <Field label="Confiance OCR"   :value="inv.processing_log?.[0]?.ocr_confidence ? inv.processing_log[0].ocr_confidence + '%' : null" mono />
              <Field label="Tentatives"      :value="inv.processing_log?.[0]?.parse_attempts" mono />
              <Field label="Importé le"      :value="fmtDatetime(inv.uploaded_at)" />
              <Field label="Traité le"       :value="fmtDatetime(inv.processed_at)" />
              <div v-if="inv.file_url" class="field-row">
                <span class="field-label">Fichier original</span>
                <a :href="inv.file_url" target="_blank" class="file-link">Ouvrir ↗</a>
              </div>
            </div>
          </div>

        </div>
      </div>

      <!-- ── Lignes de facture ── -->
      <div v-if="inv.line_items?.length" class="card full-width">
        <div class="card-title">📋 Lignes de facture ({{ inv.line_items.length }})</div>
        <div class="table-wrap">
          <table class="lines-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Désignation</th>
                <th class="right">Quantité</th>
                <th class="right">P.U. HT</th>
                <th class="right">TVA</th>
                <th class="right">Total HT</th>
                <th class="right">Total TTC</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="l in inv.line_items" :key="l.id">
                <td class="mono muted">{{ l.line_number ?? '—' }}</td>
                <td>{{ l.description || '—' }}</td>
                <td class="mono right">{{ l.quantity ?? '—' }}</td>
                <td class="mono right">{{ fmt3(l.unit_price) }}</td>
                <td class="mono right">{{ l.tva_rate ? l.tva_rate + '%' : '—' }}</td>
                <td class="mono right">{{ fmt3(l.amount_ht) }}</td>
                <td class="mono right bold">{{ fmt3(l.amount_ttc) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ── Données brutes JSON ── -->
      <div class="card full-width" v-if="inv.structured_data">
        <div class="card-title collapsible" @click="showJson = !showJson">
          {{ showJson ? '▾' : '▸' }} JSON structuré complet (structured_data)
        </div>
        <pre v-if="showJson" class="raw-block">{{ JSON.stringify(inv.structured_data, null, 2) }}</pre>
      </div>

      <!-- ── Texte OCR brut ── -->
      <div class="card full-width">
        <div class="card-title collapsible" @click="showRaw = !showRaw">
          {{ showRaw ? '▾' : '▸' }} Texte brut OCR
        </div>
        <pre v-if="showRaw" class="raw-block">{{ inv.raw_text || 'Aucun texte extrait.' }}</pre>
      </div>

      <!-- ── Log pipeline ── -->
      <div class="card full-width">
        <div class="card-title collapsible" @click="showLog = !showLog">
          {{ showLog ? '▾' : '▸' }} Log pipeline
        </div>
        <pre v-if="showLog" class="raw-block">{{ JSON.stringify(inv.processing_log, null, 2) }}</pre>
      </div>

    </template>

    <div v-else class="loading-state muted">Facture introuvable.</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useInvoicesStore } from '@/stores/invoices'
import StatusBadge from '@/components/StatusBadge.vue'

const Field = {
  props: ['label', 'value', 'mono', 'suffix', 'highlight', 'danger'],
  template: `
    <div class="field-row" v-if="value !== null && value !== undefined">
      <span class="field-label">{{ label }}</span>
      <span class="field-value" :class="{ mono, highlight, danger }">
        {{ value }}<span v-if="suffix" class="field-suffix"> {{ suffix }}</span>
      </span>
    </div>
    <div class="field-row empty" v-else>
      <span class="field-label">{{ label }}</span>
      <span class="field-value muted">—</span>
    </div>
  `
}

const props   = defineProps({ id: String })
const store   = useInvoicesStore()
const loading = ref(true)
const reprocessing = ref(false)
const showRaw = ref(false)
const showJson = ref(false)
const showLog  = ref(false)

const inv   = computed(() => store.current)
const isRtl = computed(() => inv.value?.language === 'ar')

onMounted(async () => {
  await store.fetchOne(props.id)
  loading.value = false
})

async function reprocess() {
  reprocessing.value = true
  await store.reprocess(props.id)
  setTimeout(async () => {
    await store.fetchOne(props.id)
    reprocessing.value = false
  }, 4000)
}

function fmt3(v) {
  if (v == null) return null
  return Number(v).toLocaleString('fr-TN', { minimumFractionDigits: 3 })
}
function fmtDate(d) {
  if (!d) return null
  return new Date(d).toLocaleDateString('fr-FR')
}
function fmtDatetime(d) {
  if (!d) return null
  return new Date(d).toLocaleString('fr-FR')
}
</script>

<style scoped>
.page { padding: 28px 32px; max-width: 1100px; }

.btn-back { background: none; border: none; color: var(--text-secondary); cursor: pointer; font-size: 13px; margin-bottom: 20px; padding: 4px 0; }
.btn-back:hover { color: var(--text-primary); }

.loading-state { padding: 48px; }
.muted { color: var(--text-muted); }

/* Header */
.detail-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
.detail-vendor { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
.detail-num    { font-size: 14px; color: var(--accent); }
.header-right  { display: flex; flex-direction: column; align-items: flex-end; gap: 10px; }
.btn-reprocess { background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-secondary); padding: 7px 14px; border-radius: var(--radius); cursor: pointer; font-size: 12px; font-weight: 500; transition: all 0.15s; }
.btn-reprocess:hover:not(:disabled) { color: var(--accent); border-color: var(--accent); }
.btn-reprocess:disabled { opacity: 0.5; cursor: default; }

/* Alertes */
.alert { border-radius: var(--radius); padding: 12px 16px; margin-bottom: 16px; }
.alert p { font-size: 12px; margin-top: 4px; }
.alert strong { font-size: 13px; }
.alert.danger  { background: var(--danger-dim);  border-left: 3px solid var(--danger);  color: var(--danger); }
.alert.warning { background: var(--warning-dim); border-left: 3px solid var(--warning); color: var(--warning); }

/* Grille principale */
.main-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.col { display: flex; flex-direction: column; gap: 16px; }

/* Cards */
.card { background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; }
.card.full-width { margin-bottom: 16px; }
.card-title { font-size: 12px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 14px; }
.card-title.collapsible { cursor: pointer; user-select: none; margin-bottom: 0; }
.card-title.collapsible:hover { color: var(--text-primary); }

/* Champs */
.fields { display: flex; flex-direction: column; gap: 0; }
.field-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; padding: 7px 0; border-bottom: 1px solid var(--border-subtle); }
.field-row:last-child { border-bottom: none; }
.field-row.empty .field-value { color: var(--text-muted) !important; }
.field-label { font-size: 12px; color: var(--text-secondary); flex-shrink: 0; max-width: 140px; }
.field-value { font-size: 12px; font-weight: 500; text-align: right; word-break: break-all; }
.field-value.mono { font-family: var(--font-mono); }
.field-value.highlight { color: var(--accent); font-size: 14px; font-weight: 700; }
.field-value.danger { color: var(--danger); }
.field-value.muted { color: var(--text-muted); font-weight: 400; }
.field-suffix { color: var(--text-secondary); font-weight: 400; font-size: 11px; }
.field-separator { height: 1px; background: var(--border); margin: 4px 0; }

.file-link { font-size: 12px; color: var(--accent); text-decoration: none; font-weight: 500; }
.file-link:hover { text-decoration: underline; }

/* Lignes de facture */
.table-wrap { overflow-x: auto; border-radius: var(--radius-sm); border: 1px solid var(--border); margin-top: 12px; }
.lines-table { width: 100%; border-collapse: collapse; }
.lines-table th { padding: 8px 12px; font-size: 11px; font-weight: 600; color: var(--text-secondary); text-align: left; border-bottom: 1px solid var(--border); text-transform: uppercase; letter-spacing: 0.04em; background: var(--bg-elevated); }
.lines-table th.right { text-align: right; }
.lines-table td { padding: 9px 12px; font-size: 12px; border-bottom: 1px solid var(--border-subtle); }
.lines-table tr:last-child td { border-bottom: none; }
.right { text-align: right; }
.bold  { font-weight: 700; }

/* Raw blocks */
.raw-block { background: var(--bg-elevated); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 14px; font-family: var(--font-mono); font-size: 11px; color: var(--text-secondary); white-space: pre-wrap; word-break: break-all; max-height: 320px; overflow-y: auto; line-height: 1.6; margin-top: 10px; }

@media (max-width: 700px) {
  .main-grid { grid-template-columns: 1fr; }
}
</style>
