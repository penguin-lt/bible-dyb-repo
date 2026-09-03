import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { dataSourceLabel } from "@/src/lib/source";

export const metadata: Metadata = {
  title: "Selah Bible Reader",
  description: "Read scripture by book, chapter, and verse.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  let tag = "";
  try {
    tag = dataSourceLabel();
  } catch {
    tag = "Supabase (live)";
  }

  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <div className="container header-inner">
            <Link href="/" className="brand">
              Selah<span> </span>
              <small>Bible Reader</small>
            </Link>
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <span className="source-tag">{tag}</span>
              <form className="search-form" action="/search" method="get">
                <input
                  type="search"
                  name="q"
                  placeholder="Search verses…"
                  aria-label="Search verses"
                />
                <button type="submit">Search</button>
              </form>
            </div>
          </div>
        </header>
        <main className="container">{children}</main>
        <footer style={{ padding: "20px 0 40px", textAlign: "center" }}>
          <span className="muted" style={{ fontSize: "0.8rem" }}>
            {tag === "Supabase (live)"
              ? "Reading from your live Supabase project."
              : "Demo text: public-domain King James Version."}{" "}
            Built to read from your Supabase project.
          </span>
        </footer>
      </body>
    </html>
  );
}
