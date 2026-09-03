import Link from "next/link";
import { searchVerses } from "@/src/lib/source";

export const dynamic = "force-dynamic";

export default async function SearchPage({
  searchParams,
}: {
  searchParams: { q?: string };
}) {
  const q = (searchParams.q ?? "").trim();
  let results: Awaited<ReturnType<typeof searchVerses>> = [];
  let error: string | null = null;

  if (q) {
    try {
      results = await searchVerses(q, 50);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    }
  }

  return (
    <>
      <h1 className="page-title">Search</h1>
      <p className="lead">
        {q ? (
          <>
            Results for <strong>“{q}”</strong> · {results.length} found
          </>
        ) : (
          "Type a phrase above to search the text."
        )}
      </p>

      {error && <div className="error-box">{error}</div>}

      {q && !error && (
        <ul className="result-list">
          {results.length === 0 && (
            <p className="muted">No verses matched your search.</p>
          )}
          {results.map((v, i) => (
            <li key={i}>
              <div className="ref">
                <Link href={`/read/${v.book}/${v.chapter}`}>
                  {v.bookName} {v.chapter}:{v.verse}
                </Link>
              </div>
              <div className="q">
                <Highlight text={v.text} q={q} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function Highlight({ text, q }: { text: string; q: string }) {
  const idx = text.toLowerCase().indexOf(q.toLowerCase());
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <mark>{text.slice(idx, idx + q.length)}</mark>
      {text.slice(idx + q.length)}
    </>
  );
}
