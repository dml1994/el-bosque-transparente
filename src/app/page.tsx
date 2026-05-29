import { getContractStats } from "@/lib/contracts";
import { getCompanyStats } from "@/lib/companies";
import { getBudgetYears, getBudgetStats } from "@/lib/budget";
import { getSalaryYears, getSalaryStats } from "@/lib/salaries";

export const revalidate = 3600; // refresca la home cada hora

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "El Bosque Transparente",
  url: "https://el-bosque-transparente.vercel.app",
  description:
    "Portal de transparencia del Ayuntamiento de Ubrique con datos de contratos, sueldos y presupuesto.",
  about: {
    "@type": "GovernmentOrganization",
    name: "Ayuntamiento de Ubrique",
    url: "https://www.ubrique.es",
    address: {
      "@type": "PostalAddress",
      addressLocality: "Ubrique",
      addressRegion: "Cádiz",
      addressCountry: "ES",
      postalCode: "11600",
    },
  },
};

const eur = (n: number) =>
  new Intl.NumberFormat("es-ES", {
    style: "currency",
    currency: "EUR",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(n);

export default async function HomePage() {
  const [contractStats, companyStats, budgetYears, salaryYears] = await Promise.all([
    getContractStats(),
    getCompanyStats(),
    getBudgetYears(),
    getSalaryYears(),
  ]);

  const [budgetStats, salaryStats] = await Promise.all([
    budgetYears[0] ? getBudgetStats(budgetYears[0]) : null,
    salaryYears[0] ? getSalaryStats(salaryYears[0]) : null,
  ]);

  const kpis = [
    { value: Number(contractStats.total).toLocaleString("es-ES"), label: "contratos publicados",         href: "/contratos",   color: "text-blue-600"   },
    { value: eur(Number(contractStats.totalAmount)),               label: "total adjudicado",             href: "/contratos",   color: "text-emerald-600"},
    { value: companyStats.total.toLocaleString("es-ES"),          label: "empresas adjudicatarias",      href: "/empresas",    color: "text-violet-600" },
    { value: budgetStats ? eur(budgetStats.gastos) : "—",         label: `gastos ${budgetYears[0] ?? ""}`, href: "/presupuesto", color: "text-amber-600"  },
  ];

  const sections = [
    {
      href: "/contratos",
      title: "Contratos públicos",
      metric: `${Number(contractStats.total).toLocaleString("es-ES")} contratos · ${eur(Number(contractStats.totalAmount))}`,
      gradient: "from-blue-500 to-blue-700",
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
    },
    {
      href: "/empresas",
      title: "Empresas adjudicatarias",
      metric: `${companyStats.total.toLocaleString("es-ES")} empresas distintas`,
      gradient: "from-emerald-500 to-emerald-700",
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
        </svg>
      ),
    },
    {
      href: "/sueldos",
      title: "Sueldos de cargos",
      metric: salaryStats ? `${eur(Number(salaryStats.totalAmount))} en ${salaryYears[0]}` : "Ver datos",
      gradient: "from-violet-500 to-violet-700",
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
      ),
    },
    {
      href: "/presupuesto",
      title: "Presupuesto municipal",
      metric: budgetStats ? `${eur(budgetStats.gastos)} en ${budgetYears[0]}` : "Ver datos",
      gradient: "from-amber-500 to-orange-600",
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-5">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      {/* Hero */}
      <section className="relative bg-gradient-to-br from-brand-600 to-brand-900 rounded-2xl px-8 py-10 text-white overflow-hidden">
        <div className="absolute -top-16 -right-16 w-72 h-72 rounded-full bg-white/5" />
        <div className="absolute -bottom-12 -left-12 w-56 h-56 rounded-full bg-white/5" />
        <div className="relative z-10">
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">El Bosque Transparente</h1>
          <p className="text-brand-200 mt-2">
            Contratos, sueldos y presupuestos del Ayuntamiento de Ubrique.
          </p>
        </div>
      </section>

      {/* KPIs */}
      <section className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {kpis.map((k) => (
          <a
            key={k.label}
            href={k.href}
            className="bg-white rounded-2xl p-5 shadow-sm ring-1 ring-gray-100 hover:shadow-md hover:ring-gray-200 transition-all"
          >
            <p className={`text-3xl font-bold tracking-tight ${k.color}`}>{k.value}</p>
            <p className="text-xs text-gray-400 mt-1.5 leading-snug">{k.label}</p>
          </a>
        ))}
      </section>

      {/* Secciones */}
      <section className="grid grid-cols-2 gap-3">
        {sections.map((s) => (
          <a
            key={s.href}
            href={s.href}
            className={`relative bg-gradient-to-br ${s.gradient} rounded-2xl p-5 overflow-hidden text-white hover:brightness-110 hover:scale-[1.01] transition-all duration-200`}
          >
            <div className="absolute top-0 right-0 w-24 h-24 rounded-full bg-white/10 translate-x-8 -translate-y-8" />
            <div className="relative z-10 flex flex-col h-full gap-3">
              <div className="bg-white/20 rounded-xl w-10 h-10 flex items-center justify-center">
                {s.icon}
              </div>
              <div>
                <p className="font-semibold text-base leading-tight">{s.title}</p>
                <p className="text-white/70 text-xs mt-0.5">{s.metric}</p>
              </div>
            </div>
          </a>
        ))}
      </section>
    </div>
  );
}
