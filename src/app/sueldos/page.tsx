export const revalidate = 86400; // 24 horas (datos cambian raramente)


export const metadata = {
  title: "Sueldos de cargos públicos",
  description:
    "Retribuciones anuales del alcalde y concejales del Ayuntamiento de Ubrique. Datos oficiales del Ministerio de Hacienda (ISPA).",
  alternates: { canonical: "https://el-bosque-transparente.vercel.app/sueldos" },
  openGraph: {
    title: "Sueldos de cargos públicos — El Bosque Transparente",
    description: "Retribuciones del alcalde y concejales de Ubrique. Fuente: ISPA (Ministerio de Hacienda).",
    url: "https://el-bosque-transparente.vercel.app/sueldos",
  },
};

import { getSalaries, getSalaryYears, getSalaryStats } from "@/lib/salaries";

const fmt = new Intl.NumberFormat("es-ES", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

function dedicacion(position: string) {
  if (position.includes("(parcial)"))       return "Parcial";
  if (position.includes("(sin dedicación)")) return "Sin dedicación";
  return "Exclusiva";
}

function posLabel(position: string) {
  return position.replace(" (parcial)", "").replace(" (sin dedicación)", "");
}

const DED_BADGE: Record<string, string> = {
  "Exclusiva":      "bg-brand-50 text-brand-700",
  "Parcial":        "bg-yellow-50 text-yellow-700",
  "Sin dedicación": "bg-gray-100 text-gray-600",
};

type PageProps = { searchParams: Promise<{ year?: string }> };

export default async function SueldosPage({ searchParams }: PageProps) {
  const filters = await searchParams;

  const years = await getSalaryYears();
  const latestYear = years[0];
  const selectedYear = filters.year ? parseInt(filters.year, 10) : latestYear;

  const [rows, stats] = await Promise.all([
    getSalaries(selectedYear),
    getSalaryStats(selectedYear),
  ]);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Sueldos de cargos públicos</h1>
        <p className="text-sm text-gray-500 mt-1">
          Retribuciones anuales del alcalde y concejales. Fuente: ISPA (Ministerio de Hacienda).
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Cargos con retribución</p>
          <p className="text-xl md:text-2xl font-bold text-gray-900 mt-1">
            {Number(stats.total).toLocaleString("es-ES")}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Coste total {selectedYear}</p>
          <p className="text-xl md:text-2xl font-bold text-brand-600 mt-1">
            {fmt.format(Number(stats.totalAmount))}
          </p>
        </div>
      </div>

      {/* Selector de año */}
      {years.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {years.map((y) => (
            <a
              key={y}
              href={`/sueldos?year=${y}`}
              className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                selectedYear === y
                  ? "bg-brand-600 border-brand-600 text-white"
                  : "bg-white border-gray-200 text-gray-700 hover:border-brand-400"
              }`}
            >
              {y}
            </a>
          ))}
        </div>
      )}

      {rows.length === 0 ? (
        <div className="bg-white rounded-xl border border-gray-200 p-16 text-center">
          <p className="text-lg font-semibold text-gray-700">Sin datos de sueldos para {selectedYear}</p>
        </div>
      ) : (
        <>
          {/* Móvil: tarjetas */}
          <div className="md:hidden space-y-2">
            {rows.map((s) => {
              const ded = dedicacion(s.position);
              const label = posLabel(s.position);
              return (
                <div key={s.id} className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-medium text-gray-900 text-sm">{label}</p>
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium shrink-0 ${DED_BADGE[ded]}`}>
                      {ded}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {s.personName ?? <span className="italic">No disponible</span>}
                  </p>
                  <p className="text-lg font-bold text-gray-900 mt-2">
                    {s.total ? fmt.format(Number(s.total)) : "—"}
                  </p>
                </div>
              );
            })}
          </div>

          {/* Desktop: tabla */}
          <div className="hidden md:block bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Cargo</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Nombre</th>
                  <th className="text-right px-4 py-3 font-medium text-gray-600">Retribución anual</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Dedicación</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {rows.map((s) => {
                  const ded = dedicacion(s.position);
                  const label = posLabel(s.position);
                  return (
                    <tr key={s.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 font-medium text-gray-900">{label}</td>
                      <td className="px-4 py-3 text-gray-600">
                        {s.personName ?? <span className="text-gray-400 italic">No disponible</span>}
                      </td>
                      <td className="px-4 py-3 text-right font-semibold text-gray-900 whitespace-nowrap">
                        {s.total ? fmt.format(Number(s.total)) : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${DED_BADGE[ded]}`}>
                          {ded}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="px-4 py-3 border-t border-gray-100 bg-gray-50">
              <p className="text-xs text-gray-400">
                Datos ISPA {selectedYear} — Ministerio de Hacienda y Función Pública.
                {selectedYear === 2023 && " El año 2023 incluye dos períodos: mandato 2019 (hasta junio) y mandato 2023 (resto del año)."}
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
