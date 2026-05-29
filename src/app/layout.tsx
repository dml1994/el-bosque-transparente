import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://el-bosque-transparente.vercel.app"),
  title: {
    default: "El Bosque Transparente",
    template: "%s | El Bosque Transparente",
  },
  description:
    "Portal de transparencia del Ayuntamiento de El Bosque (Cádiz). Consulta contratos públicos, retribuciones de cargos electos y presupuestos municipales con datos oficiales actualizados.",
  keywords: [
    "transparencia", "el bosque", "ayuntamiento", "contratos públicos",
    "presupuesto municipal", "sueldos concejales", "cádiz", "andalucía",
    "plataforma contratación", "datos abiertos",
  ],
  authors: [{ name: "El Bosque Transparente" }],
  creator: "El Bosque Transparente",
  openGraph: {
    type: "website",
    locale: "es_ES",
    url: "https://el-bosque-transparente.vercel.app",
    siteName: "El Bosque Transparente",
    title: "El Bosque Transparente — Transparencia municipal",
    description:
      "Contratos públicos, sueldos de cargos y presupuestos del Ayuntamiento de El Bosque. Datos oficiales actualizados diariamente.",
  },
  twitter: {
    card: "summary_large_image",
    title: "El Bosque Transparente",
    description:
      "Contratos públicos, sueldos y presupuestos del Ayuntamiento de El Bosque.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large" },
  },
  alternates: {
    canonical: "https://el-bosque-transparente.vercel.app",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className="flex flex-col min-h-screen">
        <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
            <a href="/" className="flex items-center gap-2.5">
              <div className="w-7 h-7 bg-brand-600 rounded-lg flex items-center justify-center shrink-0">
                <span className="text-white font-bold text-xs">EB</span>
              </div>
              <span className="font-semibold text-gray-900 text-sm">El Bosque Transparente</span>
            </a>
            <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-gray-600">
              <a href="/contratos"   className="hover:text-brand-600 transition-colors">Contratos</a>
              <a href="/sueldos"     className="hover:text-brand-600 transition-colors">Sueldos</a>
              <a href="/presupuesto" className="hover:text-brand-600 transition-colors">Presupuesto</a>
              <a href="/empresas"    className="hover:text-brand-600 transition-colors">Empresas</a>
            </nav>
          </div>
          {/* Nav móvil: barra inferior con las 4 secciones */}
          <nav className="md:hidden flex border-t border-gray-100">
            {[
              { href: "/contratos",   label: "Contratos"   },
              { href: "/empresas",    label: "Empresas"    },
              { href: "/sueldos",     label: "Sueldos"     },
              { href: "/presupuesto", label: "Presupuesto" },
            ].map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="flex-1 py-2.5 text-center text-xs font-medium text-gray-500 hover:text-brand-600 hover:bg-brand-50 transition-colors"
              >
                {item.label}
              </a>
            ))}
          </nav>
        </header>
        <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full">
          {children}
        </main>
        <footer className="mt-16 border-t border-gray-200 py-8 text-center text-sm text-gray-500">
          <p>Datos obtenidos de fuentes oficiales. Actualización automática diaria.</p>
          <p className="mt-1">
            <a href="https://contrataciondelestado.es" target="_blank" rel="noopener noreferrer" className="hover:underline">
              Plataforma de Contratación del Sector Público
            </a>
          </p>
        </footer>
      </body>
    </html>
  );
}
