export const revalidate = 3600; // 1 hora en CDN


export const metadata = {
  title: "Contratos públicos",
  description:
    "Consulta todos los contratos públicos del Ayuntamiento de Ubrique. Datos de la Plataforma de Contratación del Sector Público, actualizados diariamente.",
  alternates: { canonical: "https://el-bosque-transparente.vercel.app/contratos" },
  openGraph: {
    title: "Contratos públicos — El Bosque Transparente",
    description: "Contratos del Ayuntamiento de Ubrique con importes, adjudicatarias y fechas. Fuente oficial PCSP.",
    url: "https://el-bosque-transparente.vercel.app/contratos",
  },
};

import { Suspense } from "react";
import {
  getContracts,
  getContractStats,
  getYearStats,
  getDistinctTypes,
  labelContractType,
  type ContractsFilter,
} from "@/lib/contracts";
import ContractsFilters from "./ContractsFilters";
import Pagination from "@/components/Pagination";

const fmt = new Intl.NumberFormat("es-ES", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

function companyUrl(awardedTo: string | null, awardedToNif: string | null): string | null {
  if (!awardedTo) return null;
  const key = awardedToNif ?? awardedTo.trim().toUpperCase().replace(/[^A-Z0-9 ]/g, "");
  return `/empresas/${encodeURIComponent(key)}`;
}

const fmtDate = (d: Date | null) =>
  d ? new Date(d).toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" }) : "—";

const STATUS_BADGE: Record<string, string> = {
  awarded:     "bg-green-100 text-green-800",
  published:   "bg-blue-100 text-blue-800",
  cancelled:   "bg-red-100 text-red-800",
  in_progress: "bg-yellow-100 text-yellow-800",
};

const STATUS_LABEL: Record<string, string> = {
  awarded:     "Adjudicado",
  published:   "Publicado",
  cancelled:   "Cancelado",
  in_progress: "En tramitación",
};

type PageProps = { searchParams: Promise<ContractsFilter> };

export default async function ContratosPage({ searchParams }: PageProps) {
  const filters = await searchParams;

  const [{ rows, total, page, totalPages }, stats, yearStats, typesCodes] =
    await Promise.all([
      getContracts(filters),
      getContractStats(),
      getYearStats(),
      getDistinctTypes(),
    ]);

  const types = typesCodes.map((code) => ({ code, label: labelContractType(code) }));

  return (
    <div className="space-y-5">
      {/* Cabecera */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Contratos públicos</h1>
        <p className="text-sm text-gray-500 mt-1">
          Plataforma de Contratación del Sector Público · Actualización diaria
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Total contratos</p>
          <p className="text-xl md:text-2xl font-bold text-gray-900 mt-1">
            {Number(stats.total).toLocaleString("es-ES")}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Importe total</p>
          <p className="text-xl md:text-2xl font-bold text-brand-600 mt-1">
            {fmt.format(Number(stats.totalAmount))}
          </p>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-4 col-span-2 md:col-span-1">
          <p className="text-xs text-gray-500 uppercase tracking-wide">Última actualización</p>
          <p className="text-base font-semibold text-gray-700 mt-1">
            {stats.lastUpdated
              ? new Date(stats.lastUpdated).toLocaleDateString("es-ES", { day: "2-digit", month: "long", year: "numeric" })
              : "—"}
          </p>
        </div>
      </div>

      {/* Selector de año */}
      <div>
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">Filtrar por año</p>
        {/* Móvil: píldoras compactas */}
        <div className="flex flex-wrap gap-2 md:hidden">
          {yearStats.map((stat) => {
            const isActive = filters.year === String(stat.year);
            const params = new URLSearchParams({
              ...(filters.q     ? { q:    filters.q    } : {}),
              ...(filters.type  ? { type: filters.type } : {}),
              ...(filters.sort  ? { sort: filters.sort } : {}),
              ...(filters.order ? { order: filters.order } : {}),
              ...(isActive ? {} : { year: String(stat.year) }),
            });
            return (
              <a
                key={stat.year}
                href={`/contratos?${params.toString()}`}
                className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-brand-600 border-brand-600 text-white"
                    : "bg-white border-gray-200 text-gray-700 hover:border-brand-400"
                }`}
              >
                {stat.year}
              </a>
            );
          })}
        </div>
        {/* Desktop: tarjetas con importe */}
        <div className="hidden md:flex flex-wrap gap-3">
          {yearStats.map((stat) => {
            const isActive = filters.year === String(stat.year);
            const params = new URLSearchParams({
              ...(filters.q     ? { q:    filters.q    } : {}),
              ...(filters.type  ? { type: filters.type } : {}),
              ...(filters.sort  ? { sort: filters.sort } : {}),
              ...(filters.order ? { order: filters.order } : {}),
              ...(isActive ? {} : { year: String(stat.year) }),
            });
            return (
              <a
                key={stat.year}
                href={`/contratos?${params.toString()}`}
                className={`rounded-xl border px-5 py-3 text-center transition-colors min-w-[110px] ${
                  isActive
                    ? "bg-brand-600 border-brand-600 text-white shadow-sm"
                    : "bg-white border-gray-200 text-gray-800 hover:border-brand-400 hover:bg-brand-50"
                }`}
              >
                <p className="text-xl font-bold">{stat.year}</p>
                <p className={`text-sm font-medium mt-0.5 ${isActive ? "text-white/80" : "text-brand-600"}`}>
                  {fmt.format(stat.amount)}
                </p>
                <p className={`text-xs mt-0.5 ${isActive ? "text-white/60" : "text-gray-400"}`}>
                  {stat.total} contrato{stat.total !== 1 ? "s" : ""}
                </p>
              </a>
            );
          })}
        </div>
      </div>

      {/* Banner filtro por empresa */}
      {filters.adjudicataria && (
        <div className="flex items-center gap-3 bg-brand-50 border border-brand-200 rounded-xl px-4 py-3">
          <span className="text-sm text-brand-800 truncate">
            Contratos de <strong>{filters.adjudicataria}</strong>
          </span>
          <a href="/contratos" className="ml-auto text-xs text-brand-600 hover:underline whitespace-nowrap shrink-0">
            Quitar ✕
          </a>
        </div>
      )}

      {/* Filtros */}
      <Suspense fallback={null}>
        <ContractsFilters types={types} />
      </Suspense>

      {/* Resultados count */}
      <div className="text-sm text-gray-500">
        {total === 0 ? (
          "No se encontraron contratos con los filtros aplicados."
        ) : (
          <>
            <span className="font-medium text-gray-900">{total.toLocaleString("es-ES")}</span>{" "}
            contrato{total !== 1 ? "s" : ""} encontrado{total !== 1 ? "s" : ""}
          </>
        )}
      </div>

      {rows.length > 0 && (
        <>
          {/* Móvil: tarjetas */}
          <div className="md:hidden space-y-3">
            {rows.map((c) => (
              <div key={c.id} className="bg-white rounded-xl border border-gray-200 p-4">
                <div className="flex items-start justify-between gap-2 mb-2">
                  <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium shrink-0 ${STATUS_BADGE[c.status ?? "published"] ?? "bg-gray-100 text-gray-700"}`}>
                    {STATUS_LABEL[c.status ?? "published"] ?? c.status}
                  </span>
                  <span className="text-sm font-bold text-gray-900 whitespace-nowrap">
                    {c.amount ? fmt.format(Number(c.amount)) : "—"}
                  </span>
                </div>
                <p className="font-medium text-gray-900 text-sm leading-snug">{c.title}</p>
                {c.awardedTo ? (
                  <a
                    href={companyUrl(c.awardedTo, c.awardedToNif) ?? "#"}
                    className="text-xs text-brand-600 hover:underline mt-1 block truncate"
                  >
                    {c.awardedTo}
                  </a>
                ) : (
                  <span className="text-xs text-gray-400 italic mt-1 block">Sin adjudicar</span>
                )}
                <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                  <span>{fmtDate(c.publishedDate)}</span>
                  <span>{labelContractType(c.contractType)}</span>
                  {c.sourceUrl && (
                    <a href={c.sourceUrl} target="_blank" rel="noopener noreferrer" className="ml-auto text-brand-600 hover:underline">
                      Ver en PCSP ↗
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Desktop: tabla */}
          <div className="hidden md:block bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium text-gray-400 text-xs w-8">ID</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600 w-[35%]">Título</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600 w-[28%]">Adjudicataria</th>
                    <th className="text-right px-4 py-3 font-medium text-gray-600 w-[10%]">Importe</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600 w-[9%]">Tipo</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600 w-[9%]">Fecha</th>
                    <th className="text-left px-4 py-3 font-medium text-gray-600 w-[9%]">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {rows.map((c) => (
                    <tr key={c.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 text-xs text-gray-300 font-mono">{c.id}</td>
                      <td className="px-4 py-3">
                        <p className="font-medium text-gray-900 line-clamp-2 leading-snug">{c.title}</p>
                        {c.sourceUrl && (
                          <a href={c.sourceUrl} target="_blank" rel="noopener noreferrer" className="text-xs text-brand-600 hover:underline mt-0.5 inline-block">
                            Ver en PCSP ↗
                          </a>
                        )}
                      </td>
                      <td className="px-4 py-3 text-gray-700">
                        {c.awardedTo ? (
                          <a href={companyUrl(c.awardedTo, c.awardedToNif) ?? "#"} className="hover:text-brand-600 transition-colors">
                            {c.awardedTo}
                          </a>
                        ) : (
                          <span className="text-gray-400 italic">Sin adjudicar</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right font-semibold text-gray-900 whitespace-nowrap">
                        {c.amount ? fmt.format(Number(c.amount)) : "—"}
                      </td>
                      <td className="px-4 py-3 text-gray-600">{labelContractType(c.contractType)}</td>
                      <td className="px-4 py-3 text-gray-500 whitespace-nowrap">{fmtDate(c.publishedDate)}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[c.status ?? "published"] ?? "bg-gray-100 text-gray-700"}`}>
                          {STATUS_LABEL[c.status ?? "published"] ?? c.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {totalPages > 1 && <Pagination page={page} totalPages={totalPages} />}
    </div>
  );
}
