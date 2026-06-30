<template>
  <div class="page">
    <div class="page-header">
      <h1>Importer des factures</h1>
      <p class="text-muted">PDF, JPEG, PNG, WEBP — jusqu'à 20 Mo</p>
    </div>

    <div
      class="dropzone"
      :class="{ 'drop-active': isDragging, 'is-uploading': store.uploading }"
      @dragover.prevent="isDragging = true"
      @dragleave="isDragging = false"
      @drop.prevent="onDrop"
      @click="fileInput.click()"
    >
      <input ref="fileInput" type="file" accept=".pdf,image/*" multiple hidden @change="onFileChange" />

      <div v-if="!store.uploading" class="dz-idle">
        <div class="dz-icon">↑</div>
        <p class="dz-label">Glisser-déposer ou cliquer pour sélectionner</p>
        <p class="text-muted" style="font-size:12px">PDF natifs · Scans AR/FR · Lots multi-pages</p>
      </div>

      <div v-else class="dz-progress">
        <div class="progress-ring">
          <svg width="64" height="64" viewBox="0 0 64 64">
            <circle cx="32" cy="32" r="28" fill="none" stroke="var(--border)" stroke-width="4"/>
            <circle cx="32" cy="32" r="28" fill="none" stroke="var(--accent)" stroke-width="4"
              stroke-dasharray="175.9" :stroke-dashoffset="175.9 * (1 - store.uploadProgress / 100)"
              stroke-linecap="round" transform="rotate(-90 32 32)"
              style="transition: stroke-dashoffset 0.3s ease"/>
          </svg>
          <span class="progress-pct mono">{{ store.uploadProgress }}%</span>
        </div>
        <p class="text-muted" style="margin-top:12px">Envoi en cours…</p>
      </div>
    </div>

    <!-- File queue -->
    <div v-if="queue.length" class="queue">
      <div v-for="(f, i) in queue" :key="i" class="queue-item">
        <div class="queue-icon">📄</div>
        <div class="queue-info">
          <span class="queue-name">{{ f.name }}</span>
          <span class="text-muted mono" style="font-size:11px">{{ (f.size / 1024).toFixed(0) }} Ko</span>
        </div>
        <div class="queue-status" :class="f.status">
          <span v-if="f.status === 'ok'">✓ Uploadé</span>
          <span v-else-if="f.status === 'error'" style="color:var(--danger)">✕ Erreur</span>
          <span v-else class="text-muted">En attente</span>
        </div>
      </div>
    </div>

    <!-- Recent uploads -->
    <div class="recent" v-if="store.list.length">
      <h2 class="section-title">Dernières factures importées</h2>
      <div class="recent-grid">
        <div v-for="inv in store.list.slice(0, 6)" :key="inv.id" class="recent-card"
          @click="$router.push(`/invoices/${inv.id}`)">
          <div class="recent-status-bar" :class="inv.status"></div>
          <div class="recent-body">
            <div class="recent-vendor">{{ inv.vendor_name || inv.filename }}</div>
            <div class="recent-meta mono">
              {{ inv.invoice_number || '—' }} · {{ inv.amount_ttc ? inv.amount_ttc.toFixed(3) + ' TND' : '—' }}
            </div>
            <StatusBadge :status="inv.status" style="margin-top:8px" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useInvoicesStore } from '@/stores/invoices'
import StatusBadge from '@/components/StatusBadge.vue'

const store = useInvoicesStore()
const fileInput = ref(null)
const isDragging = ref(false)
const queue = ref([])

async function processFiles(files) {
  for (const file of files) {
    const entry = { name: file.name, size: file.size, status: 'pending' }
    queue.value.unshift(entry)
    try {
      await store.upload(file)
      entry.status = 'ok'
    } catch {
      entry.status = 'error'
    }
  }
}

function onDrop(e) {
  isDragging.value = false
  const files = [...e.dataTransfer.files]
  if (files.length) processFiles(files)
}

function onFileChange(e) {
  const files = [...e.target.files]
  if (files.length) processFiles(files)
  e.target.value = ''
}
</script>

<style scoped>
.page { padding: 32px; max-width: 860px; }
.page-header { margin-bottom: 28px; }
.page-header h1 { font-size: 22px; font-weight: 700; margin-bottom: 4px; }

.dropzone {
  border: 2px dashed var(--border);
  border-radius: var(--radius-lg);
  padding: 56px 32px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
  background: var(--bg-surface);
  margin-bottom: 24px;
}
.dropzone:hover { border-color: var(--accent); background: var(--accent-dim); }
.is-uploading { cursor: default; pointer-events: none; }

.dz-icon { font-size: 36px; margin-bottom: 12px; color: var(--accent); }
.dz-label { font-size: 15px; font-weight: 500; margin-bottom: 6px; }

.progress-ring { position: relative; display: inline-flex; align-items: center; justify-content: center; }
.progress-pct { position: absolute; font-size: 13px; font-weight: 600; }

.queue { margin-bottom: 32px; display: flex; flex-direction: column; gap: 6px; }
.queue-item {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 14px;
}
.queue-icon { font-size: 18px; }
.queue-info { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.queue-name { font-size: 13px; font-weight: 500; }
.queue-status { font-size: 12px; color: var(--success); }

.section-title { font-size: 14px; font-weight: 600; color: var(--text-secondary); margin-bottom: 14px; text-transform: uppercase; letter-spacing: 0.06em; }

.recent-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
.recent-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s, transform 0.15s;
  display: flex;
}
.recent-card:hover { border-color: var(--accent); transform: translateY(-1px); }

.recent-status-bar { width: 4px; flex-shrink: 0; }
.recent-status-bar.validated  { background: var(--success); }
.recent-status-bar.anomaly    { background: var(--danger); }
.recent-status-bar.processing { background: var(--accent); }
.recent-status-bar.pending    { background: var(--border); }

.recent-body { padding: 12px; flex: 1; min-width: 0; }
.recent-vendor { font-size: 13px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 4px; }
.recent-meta { font-size: 11px; color: var(--text-secondary); }
</style>
