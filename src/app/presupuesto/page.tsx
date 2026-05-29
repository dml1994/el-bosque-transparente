export const revalidate = 86400;


export const metadata = {
  title: "Presupuesto municipal",
  description:
    "Partidas de ingresos y gastos del presupuesto municipal de Ubrique. Datos oficiales del Ministerio de Hacienda.",
  alternates: { canonical: "https://el-bosque-transparente.vercel.app/presupuesto" },
  openGraph: {
    title: "Presupuesto municipal — El Bosque Transparente",
    description: "Presupuesto del Ayuntamiento de Ubrique con desglose de ingresos y gastos por partida.",
    url: "https://el-bosque-transparente.vercel.app/presupuesto",
  },
};

import { getBudgetLines, getBudgetYears, getBudgetStats } from "@/lib/budget";

const fmt = new Intl.NumberFormat("es-ES", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

const pct = (n: number, total: number) =>
  total > 0 ? Math.round((n / total) * 100) : 0;

type PageProps = { searchParams: Promise<{ year?: string }> };

export default async function PresupuestoPage({ searchParams }: PageProps) {
  const filters = await searchParams;

  const years = await getBudgetYears();
  const latestYear = years[0];
  const selectedYear = filters.year ? parseInt(filters.year, 10) : latestYear;

  const [rows, stats] = await Promise.all([
    getBudgetLines(selectedYear),
    getBudgetStats(selectedYear),
  ]);

  const gastos = rows
    .filter((r) => r.section === "Gastos")
    .sort((a, b) => Number(b.plannedAmount ?? 0) - Number(a.plannedAmount ?? 0));

  const ingresos = rows
    .filter((r) => r.section === "Ingresos")
    .sort((a, b) => Number(b.plannedAmount ?? 0) - Number(a.plannedAmount ?? 0));

  return (
    <div className="space-y-6">
      {/* Cabecera */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Presupuesto municipal</h1>
          <p className="text-sm text-gray-500 mt-1">
            Partidas presupuestarias de {selectedYear}. Fuente: Ministerio de Hacienda.
          </p>
        </div>
      </div>

      {/* Selector de año */}
      <div className="flex flex-wrap gap-2">
        {years.map((y) => {
          const isActive = selectedYear === y;
          return (
            <a
              key={y}
              href={y === latestYear ? "/presupuesto" : `/presupuesto?year=${y}`}
              className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-brand-600 border-brand-600 text-white"
                  : "bg-white border-gray-200 text-gray-600 hover:border-brand-400"
              }`}
            >
              {y}
            </a>
          );
        })}
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-xs text-gray-400 uppercase tracking-wide">Gastos planificados</p>
          <p className="text-xl md:text-2xl font-bold text-gray-900 mt-1">{fmt.format(stats.gastos)}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-xs text-gray-400 uppercase tracking-wide">Ingresos planificados</p>
          <p className="text-xl md:text-2xl font-bold text-brand-600 mt-1">{fmt.format(stats.ingresos)}</p>
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-16 text-center">
          <p className="text-lg font-semibold text-gray-700">Sin datos para {selectedYear}</p>
        </div>
      ) : (
        <div className="space-y-4">
          {[
            { label: "Gastos", items: gastos, total: stats.gastos, color: "bg-red-400" },
            { label: "Ingresos", items: ingresos, total: stats.ingresos, color: "bg-brand-500" },
          ].map(({ label, items, total, color }) => (
            <div key={label} className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
                <h2 className="font-semibold text-gray-900">{label}</h2>
                <span className="text-sm font-semibold text-gray-900">{fmt.format(total)}</span>
              </div>
              <div className="divide-y divide-gray-50">
                {items.map((b) => {
                  const amount = Number(b.plannedAmount ?? 0);
                  const share = pct(amount, total);
                  return (
                    <div key={b.id} className="px-5 py-3 flex items-center gap-4">
                      <span className="text-xs font-mono text-gray-300 w-6 shrink-0">{b.category}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-gray-800 truncate">{b.description}</p>
                        <div className="mt-1.5 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                          <div
                            className={`h-full ${color} rounded-full`}
                            style={{ width: `${share}%` }}
                          />
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-sm font-semibold text-gray-900 whitespace-nowrap">
                          {fmt.format(amount)}
                        </p>
                        <p className="text-xs text-gray-400">{share}%</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
