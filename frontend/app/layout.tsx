import type { Metadata } from "next";
import { Archivo } from "next/font/google";
import "./globals.css";

// Display font for headings — modern grotesque, refined (WC2026 visual identity).
const archivo = Archivo({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Predictor del Mundial 2026",
  description:
    "Elegí dos selecciones y conocé las probabilidades del resultado, calculadas con modelos estadísticos sobre partidos reales.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className={`h-full antialiased ${archivo.variable}`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
