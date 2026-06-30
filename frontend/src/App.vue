<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="logo">
        <span class="logo-icon">⬡</span>
        <span class="logo-text">InvoiceAgent</span>
      </div>

      <nav class="nav">
        <RouterLink to="/" class="nav-item" :class="{ active: $route.name === 'dashboard' }">
          <IconChart /> Dashboard
        </RouterLink>
        <RouterLink to="/invoices" class="nav-item" :class="{ active: $route.name === 'invoices' || $route.name === 'invoice-detail' }">
          <IconList /> Factures
          <span v-if="store.counts.processing > 0" class="nav-badge">
            <span class="pulse">●</span> {{ store.counts.processing }}
          </span>
        </RouterLink>
        <RouterLink to="/upload" class="nav-item" :class="{ active: $route.name === 'upload' }">
          <IconUpload /> Importer
        </RouterLink>
      </nav>

      <div class="sidebar-footer">
        <div class="status-row">
          <span class="status-dot ok"></span>
          <span class="text-muted">API connectée</span>
        </div>
        <div class="stat-mini">
          <span class="mono">{{ store.counts.validated }}</span>
          <span class="text-muted"> validées</span>
        </div>
        <div class="stat-mini" v-if="store.counts.anomaly > 0">
          <span class="mono danger">{{ store.counts.anomaly }}</span>
          <span class="text-muted"> anomalies</span>
        </div>
      </div>
    </aside>

    <main class="main-area">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useInvoicesStore } from '@/stores/invoices'
const store = useInvoicesStore()
onMounted(() => store.fetchList())

const IconChart  = { template: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="12" width="4" height="10"/><rect x="9" y="6" width="4" height="16"/><rect x="16" y="2" width="4" height="20"/></svg>` }
const IconList   = { template: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><line x1="9" y1="12" x2="15" y2="12"/><line x1="9" y1="16" x2="13" y2="16"/></svg>` }
const IconUpload = { template: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>` }
</script>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  width: 220px;
  flex-shrink: 0;
  background: var(--bg-surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 20px 0;
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px 24px;
  border-bottom: 1px solid var(--border);
}
.logo-icon { font-size: 22px; color: var(--accent); }
.logo-text  { font-size: 15px; font-weight: 700; letter-spacing: -0.02em; }

.nav {
  flex: 1;
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border-radius: var(--radius);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  transition: background 0.15s, color 0.15s;
}
.nav-item:hover  { background: var(--bg-hover); color: var(--text-primary); }
.nav-item.active { background: var(--accent-dim); color: var(--accent); }

.nav-badge {
  margin-left: auto;
  font-size: 11px;
  color: var(--accent);
  display: flex;
  align-items: center;
  gap: 4px;
}

.sidebar-footer {
  padding: 16px 20px 0;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.status-row { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.status-dot { width: 7px; height: 7px; border-radius: 50%; }
.status-dot.ok { background: var(--success); }
.stat-mini { font-size: 12px; }
.danger { color: var(--danger); }

.main-area {
  flex: 1;
  overflow-y: auto;
  background: var(--bg-base);
}
</style>
