import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "El Bosque Transparente — Portal de transparencia municipal";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: 1200,
          height: 630,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px",
          background: "linear-gradient(135deg, #1d4ed8 0%, #1e3a8a 100%)",
          fontFamily: "sans-serif",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Círculos decorativos */}
        <div
          style={{
            position: "absolute",
            top: -120,
            right: -120,
            width: 480,
            height: 480,
            borderRadius: "50%",
            background: "rgba(255,255,255,0.06)",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: -80,
            left: -80,
            width: 320,
            height: 320,
            borderRadius: "50%",
            background: "rgba(255,255,255,0.04)",
          }}
        />

        {/* Logo */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 20,
            marginBottom: 48,
          }}
        >
          <div
            style={{
              width: 64,
              height: 64,
              background: "white",
              borderRadius: 16,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#2563eb",
              fontWeight: 800,
              fontSize: 22,
            }}
          >
            UT
          </div>
          <span style={{ color: "rgba(255,255,255,0.85)", fontSize: 28, fontWeight: 600 }}>
            El Bosque Transparente
          </span>
        </div>

        {/* Título */}
        <h1
          style={{
            color: "white",
            fontSize: 64,
            fontWeight: 800,
            lineHeight: 1.1,
            margin: 0,
            letterSpacing: "-1px",
          }}
        >
          Transparencia municipal
          <br />
          al alcance de todos
        </h1>

        {/* Subtítulo */}
        <p
          style={{
            color: "rgba(255,255,255,0.7)",
            fontSize: 28,
            marginTop: 24,
            marginBottom: 0,
            lineHeight: 1.4,
          }}
        >
          Contratos públicos · Sueldos · Presupuesto
        </p>
      </div>
    ),
    { ...size }
  );
}
