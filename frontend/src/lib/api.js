import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

export default api

// ─── Upload ──────────────────────────────────────────────────────────────────
export const uploadTransactions = (file, onProgress) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/upload-transactions', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => onProgress?.(Math.round((e.loaded / e.total) * 100)),
  })
}

export const uploadMaster = (file, onProgress) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/upload-master', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => onProgress?.(Math.round((e.loaded / e.total) * 100)),
  })
}

export const mergeData = () => api.post('/merge')

// ─── Status & Filters ─────────────────────────────────────────────────────────
export const fetchStatus = () => api.get('/status').then(r => r.data)
export const fetchFilters = () => api.get('/filters').then(r => r.data)

// ─── Analytics ───────────────────────────────────────────────────────────────
export const fetchSummary              = (p) => api.get('/summary', { params: p }).then(r => r.data)
export const fetchSupplierAnalysis     = (p) => api.get('/supplier-analysis', { params: p }).then(r => r.data)
export const fetchCompanyAnalysis      = (p) => api.get('/company-analysis', { params: p }).then(r => r.data)
export const fetchMaterialAnalysis     = (p) => api.get('/material-analysis', { params: p }).then(r => r.data)
export const fetchOpenValueAnalysis    = (p) => api.get('/open-value-analysis', { params: p }).then(r => r.data)
export const fetchMonthlyTrend         = (p) => api.get('/monthly-trend', { params: p }).then(r => r.data)
export const fetchPlantAnalysis        = (p) => api.get('/plant-analysis', { params: p }).then(r => r.data)
export const fetchPurchasingGroup      = (p) => api.get('/purchasing-group-analysis', { params: p }).then(r => r.data)
export const fetchItemCategory         = (p) => api.get('/item-category-analysis', { params: p }).then(r => r.data)
export const fetchAging                = (p) => api.get('/aging', { params: p }).then(r => r.data)
export const fetchDeliveryAnalysis     = (p) => api.get('/delivery-analysis', { params: p }).then(r => r.data)
export const fetchCurrencyExposure     = (p) => api.get('/currency-exposure', { params: p }).then(r => r.data)
export const fetchPareto               = (p) => api.get('/pareto', { params: p }).then(r => r.data)
export const fetchMonthlyCompanyTrend  = (p) => api.get('/monthly-company-trend', { params: p }).then(r => r.data)
export const fetchAIInsights           = (p) => api.get('/ai-insights', { params: p }).then(r => r.data)
export const fetchSearch               = (q) => api.get('/search', { params: { q } }).then(r => r.data)
export const fetchChat                 = (message, history, filters) => api.post('/chat', { message, history, filters }).then(r => r.data)
export const fetchGrirSummary          = () => api.get('/grir/summary').then(r => r.data)
export const fetchGrirItems            = (p) => api.get('/grir/items', { params: p }).then(r => r.data)
export const uploadGrirFile            = (file, onProgress) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/grir/upload', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => onProgress?.(Math.round((e.loaded / e.total) * 100)),
  })
}
export const fetchGrirUploadMetadata   = () => api.get('/grir/upload/metadata').then(r => r.data)
export const fetchGrirAIInsights       = () => api.get('/grir/ai-insights').then(r => r.data)
export const getExportUrl              = (params) => {
  const qs = new URLSearchParams(params).toString()
  return `/api/export${qs ? '?' + qs : ''}`
}

