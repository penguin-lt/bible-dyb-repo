import Link from "next/link";
import { listBooks } from "@/src/lib/source";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const books = await listBooks();
  const ot = books.filter((b) => b.testament === "OT");
  const nt = books.filter((b) => b.testament === "NT");

  return (
    <>
      <h1 className="page-title">Scripture</h1>
      <p className="lead">
        Choose a book to begin reading by chapter.
      </p>

      <section className="t-section">
        <h2>Old Testament</h2>
        <div className="book-grid">
          {ot.map((b) => (
            <BookCard key={b.id} id={b.id} name={b.name} chapters={b.chapters} />
          ))}
        </div>
      </section>

      <section className="t-section">
        <h2>New Testament</h2>
        <div className="book-grid">
          {nt.map((b) => (
            <BookCard key={b.id} id={b.id} name={b.name} chapters={b.chapters} />
          ))}
        </div>
      </section>
    </>
  );
}

function BookCard({
  id,
  name,
  chapters,
}: {
  id: number;
  name: string;
  chapters: number;
}) {
  return (
    <Link href={`/read/${id}/1`} className="book-card">
      <div className="bname">{name}</div>
      <div className="bch">{chapters} chapters</div>
    </Link>
  );
}
