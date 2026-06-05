import { useQuery } from '@tanstack/react-query'
import {
  fetchSummary, fetchSupplierAnalysis, fetchCompanyAnalysis,
  fetchMaterialAnalysis, fetchOpenValueAnalysis, fetchMonthlyTrend,
  fetchPlantAnalysis, fetchPurchasingGroup, fetchItemCategory,
  fetchAging, fetchDeliveryAnalysis, fetchCurrencyExposure,
  fetchPareto, fetchMonthlyCompanyTrend, fetchAIInsights, fetchFilters, fetchStatus,
  fetchGrirSummary, fetchGrirItems,
} from '../lib/api'

const makeOpts = (key, fn, params, extra = {}) => ({
  queryKey: [key, params],
  queryFn: () => fn(params),
  enabled: !!params,
  ...extra,
})

export const useStatus      = () => useQuery({ queryKey: ['status'], queryFn: fetchStatus, refetchInterval: 3000 })
export const useFilters     = (enabled) => useQuery({ queryKey: ['filters'], queryFn: fetchFilters, enabled })
export const useSummary     = (p) => useQuery(makeOpts('summary', fetchSummary, p))
export const useSupplier    = (p) => useQuery(makeOpts('supplier', fetchSupplierAnalysis, p))
export const useCompany     = (p) => useQuery(makeOpts('company', fetchCompanyAnalysis, p))
export const useMaterial    = (p) => useQuery(makeOpts('material', fetchMaterialAnalysis, p))
export const useOpenValue   = (p) => useQuery(makeOpts('openValue', fetchOpenValueAnalysis, p))
export const useMonthly     = (p) => useQuery(makeOpts('monthly', fetchMonthlyTrend, p))
export const usePlant       = (p) => useQuery(makeOpts('plant', fetchPlantAnalysis, p))
export const usePurchGroup  = (p) => useQuery(makeOpts('purchGroup', fetchPurchasingGroup, p))
export const useItemCat     = (p) => useQuery(makeOpts('itemCat', fetchItemCategory, p))
export const useAging       = (p) => useQuery(makeOpts('aging', fetchAging, p))
export const useDelivery    = (p) => useQuery(makeOpts('delivery', fetchDeliveryAnalysis, p))
export const useCurrency    = (p) => useQuery(makeOpts('currency', fetchCurrencyExposure, p))
export const usePareto      = (p) => useQuery(makeOpts('pareto', fetchPareto, p))
export const useCompanyTrend = (p) => useQuery(makeOpts('companyTrend', fetchMonthlyCompanyTrend, p))
export const useAIInsights  = (p) => useQuery(makeOpts('insights', fetchAIInsights, p, { staleTime: 60 * 1000 }))
export const useGrirSummary = () => useQuery({ queryKey: ['grirSummary'], queryFn: fetchGrirSummary, staleTime: 5 * 60 * 1000 })
export const useGrirItems   = (p) => useQuery({ queryKey: ['grirItems', p], queryFn: () => fetchGrirItems(p) })
