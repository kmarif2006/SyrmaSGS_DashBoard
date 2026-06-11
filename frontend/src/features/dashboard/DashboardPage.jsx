import { useState, useMemo } from 'react'
import { 
  DollarSign, 
  ShoppingCart, 
  Users, 
  Package, 
  Activity, 
  Trash2, 
  Clock, 
  ChevronRight,
  TrendingUp,
  Landmark,
  Building2,
  Factory,
  Layers,
  BarChart4
} from 'lucide-react'
import {
  NavBar,
  GlobalFilters,
  KPICard,
  AIInsights,
  ChatBot,
  SupplierChart,
  MonthlyTrendChart,
  CompanyChart,
  PlantChart,
  MaterialChart,
  ParetoChart,
  CurrencyChart,
  DeliveryChart,
  AgingChart,
  TreemapChart,
  OpenValueChart,
  CompanyTrendChart,
  PurchGroupChart,
} from '../../shared'

// Hooks
import { 
  useSummary, 
  useSupplier, 
  useCompany, 
  useMaterial, 
  useOpenValue, 
  useMonthly, 
  usePlant, 
  usePurchGroup, 
  useItemCat, 
  useAging, 
  useDelivery, 
  useCurrency, 
  usePareto, 
  useCompanyTrend, 
  useAIInsights, 
  useFilters 
} from '../../hooks/useAnalytics'

function SectionHeader({ title, icon: Icon, color = 'indigo' }) {
  const colors = {
    indigo: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20',
    amber: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    emerald: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    rose: 'text-rose-400 bg-rose-500/10 border-rose-500/20',
    cyan: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
    violet: 'text-violet-400 bg-violet-500/10 border-violet-500/20',
  }
  
  return (
    <div className="flex items-center gap-3 mb-6">
      <div className={`p-2 rounded-xl border ${colors[color]}`}>
        <Icon size={18} />
      </div>
      <h2 className="text-xl font-bold text-white tracking-tight">{title}</h2>
      <div className="h-px flex-1 bg-slate-800 ml-4" />
    </div>
  )
}

function ChartCard({ title, subtitle, children, className }) {
  return (
    <div className={`glass-card p-6 flex flex-col ${className}`}>
      <div className="mb-6">
        <h3 className="text-base font-bold text-slate-100 mb-1">{title}</h3>
        {subtitle && <p className="text-xs text-slate-500 font-medium tracking-wide uppercase">{subtitle}</p>}
      </div>
      <div className="flex-1 min-h-0">
        {children}
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const [filters, setFilters] = useState({})
  
  // Data Fetching
  const { data: filterOptions } = useFilters(true)
  const { data: summary, isLoading: loadingSummary } = useSummary(filters)
  const { data: supplierData, isLoading: loadingSupplier } = useSupplier(filters)
  const { data: companyData, isLoading: loadingCompany } = useCompany(filters)
  const { data: materialData, isLoading: loadingMaterial } = useMaterial(filters)
  const { data: openValueData, isLoading: loadingOpenValue } = useOpenValue(filters)
  const { data: monthlyData, isLoading: loadingMonthly } = useMonthly(filters)
  const { data: plantData, isLoading: loadingPlant } = usePlant(filters)
  const { data: purchGroupData, isLoading: loadingPurchGroup } = usePurchGroup(filters)
  const { data: itemCatData, isLoading: loadingItemCat } = useItemCat(filters)
  const { data: agingData, isLoading: loadingAging } = useAging(filters)
  const { data: deliveryData, isLoading: loadingDelivery } = useDelivery(filters)
  const { data: currencyData, isLoading: loadingCurrency } = useCurrency(filters)
  const { data: paretoData, isLoading: loadingPareto } = usePareto(filters)
  const { data: companyTrendData, isLoading: loadingCompanyTrend } = useCompanyTrend(filters)
  const { data: insightsData, isLoading: loadingInsights } = useAIInsights(filters)

  return (
    <div className="min-h-screen bg-slate-950 pb-12">
      <NavBar filters={filters} />
      <GlobalFilters filterOptions={filterOptions} filters={filters} setFilters={setFilters} />

      <main id="dashboard-container" className="max-w-[1600px] mx-auto px-5 pt-8 space-y-10 bg-slate-950">
        
        {/* KPI Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <KPICard 
            icon={Landmark} 
            label="Total Spend (INR)" 
            value={summary?.total_spend_inr} 
            sub="Gross purchase volume"
            index={0}
            isLoading={loadingSummary} 
          />
          <KPICard 
            icon={Clock} 
            label="Open PO Value" 
            value={summary?.total_open_value_inr} 
            sub="Awaiting fulfillment"
            index={1}
            isLoading={loadingSummary} 
          />
          <KPICard 
            icon={ShoppingCart} 
            label="Total POs" 
            value={summary?.total_pos} 
            format="number"
            sub="Unique purchasing docs"
            index={2}
            isLoading={loadingSummary} 
          />
          <KPICard 
            icon={Activity} 
            label="Efficiency Rate" 
            value={summary?.procurement_efficiency} 
            format="pct"
            sub="Open vs Total Ratio"
            index={3}
            isLoading={loadingSummary} 
          />
          <KPICard 
            icon={Users} 
            label="Suppliers" 
            value={summary?.total_suppliers} 
            format="number"
            sub="Active vendor pool"
            index={4}
            isLoading={loadingSummary} 
          />
          <KPICard 
            icon={Package} 
            label="Materials" 
            value={summary?.total_materials} 
            format="number"
            sub="Unique SKUs categorized"
            index={5}
            isLoading={loadingSummary} 
          />
          <KPICard 
            icon={Trash2} 
            label="Deleted POs" 
            value={summary?.deleted_pos} 
            format="number"
            sub="Flagged for deletion"
            index={6}
            isLoading={loadingSummary} 
          />
          <KPICard 
            icon={TrendingUp} 
            label="Avg. Net Price" 
            value={summary?.total_spend_inr / (summary?.total_quantity || 1)} 
            sub="Per unit weighted avg"
            index={7}
            isLoading={loadingSummary} 
          />
        </div>

        {/* AI Insights Section */}
        <AIInsights data={insightsData} isLoading={loadingInsights} />

        {/* Trend Analysis */}
        <section>
          <SectionHeader title="Expenditure Trends" icon={TrendingUp} color="indigo" />
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <ChartCard title="Monthly Spend Evolution" subtitle="Total INR Spend by Document date" className="xl:col-span-2">
              <MonthlyTrendChart data={monthlyData} isLoading={loadingMonthly} />
            </ChartCard>
            <ChartCard title="Company Spend Heatmap" subtitle="Monthly trend per Company Code">
              <CompanyTrendChart data={companyTrendData} isLoading={loadingCompanyTrend} />
            </ChartCard>
          </div>
        </section>

        {/* Supplier & Concentration */}
        <section>
          <SectionHeader title="Supplier Analysis" icon={Users} color="emerald" />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <ChartCard title="Top 15 Suppliers by Spend" subtitle="Spend value in INR">
              <SupplierChart data={supplierData} isLoading={loadingSupplier} />
            </ChartCard>
            <div className="space-y-6">
              <ChartCard title="Supplier Concentration (Pareto)" subtitle="Top 10 Suppliers vs Cumulative Spend %">
                <ParetoChart data={paretoData} isLoading={loadingPareto} />
              </ChartCard>
              <ChartCard title="Open Value Exposure" subtitle="Pending INR value by Top Suppliers">
                <OpenValueChart data={openValueData} isLoading={loadingOpenValue} />
              </ChartCard>
            </div>
          </div>
        </section>

        {/* Operational View */}
        <section>
          <SectionHeader title="Operational Distribution" icon={Layers} color="violet" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <ChartCard title="Spend by Company Code" subtitle="Entity-wise breakdown">
              <CompanyChart data={companyData} isLoading={loadingCompany} />
            </ChartCard>
            <ChartCard title="Spend by Plant" subtitle="Manufacturing unit distribution">
              <PlantChart data={plantData} isLoading={loadingPlant} />
            </ChartCard>
            <ChartCard title="Spend by Purchasing Group" subtitle="Buyer group allocation">
              <PurchGroupChart data={purchGroupData} isLoading={loadingPurchGroup} />
            </ChartCard>
          </div>
        </section>

        {/* Material & Financials */}
        <section>
          <SectionHeader title="Material & Finance" icon={Landmark} color="amber" />
          <div className="grid grid-cols-1 xl:grid-cols-4 gap-6">
            <ChartCard title="Category Spend Distribution" subtitle="Item Category Treemap Analysis" className="xl:col-span-2">
              <TreemapChart data={itemCatData} isLoading={loadingItemCat} />
            </ChartCard>
            <ChartCard title="Top 20 Materials" subtitle="By total procurement value" className="xl:col-span-2">
              <MaterialChart data={materialData} isLoading={loadingMaterial} />
            </ChartCard>
            <ChartCard title="Currency Exposure" subtitle="Original vs Converted Spend" className="xl:col-span-2">
              <CurrencyChart data={currencyData} isLoading={loadingCurrency} />
            </ChartCard>
            <ChartCard title="Delivery Performance" subtitle="On-time vs Delayed deliveries">
              <DeliveryChart data={deliveryData} isLoading={loadingDelivery} />
            </ChartCard>
            <ChartCard title="Purchase Order Aging" subtitle="PO count by Days elapsed">
              <AgingChart data={agingData} isLoading={loadingAging} />
            </ChartCard>
          </div>
        </section>

      </main>
      <ChatBot filters={filters} />
    </div>
  )
}
