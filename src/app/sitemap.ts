import type { MetadataRoute } from "next";

const BASE = "https://el-bosque-transparente.vercel.app";

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: BASE,                    lastModified: new Date(), changeFrequency: "daily",  priority: 1.0 },
    { url: `${BASE}/contratos`,     lastModified: new Date(), changeFrequency: "daily",  priority: 0.9 },
    { url: `${BASE}/empresas`,      lastModified: new Date(), changeFrequency: "weekly", priority: 0.8 },
    { url: `${BASE}/sueldos`,       lastModified: new Date(), changeFrequency: "yearly", priority: 0.7 },
    { url: `${BASE}/presupuesto`,   lastModified: new Date(), changeFrequency: "yearly", priority: 0.7 },
  ];
}
