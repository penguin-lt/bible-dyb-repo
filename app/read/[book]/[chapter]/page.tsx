import Link from "next/link";
import { notFound } from "next/navigation";
import ChapterPicker from "@/src/components/ChapterPicker";
import { listBooks, getChapter } from "@/src/lib/source";
import type { BookMeta } from "@/src/lib/types";

type Params = { params: { book: string; chapter: string } };

export const dynamic = "force-dynamic";

export default async function ReaderPage({ params }: Params) {
  const bookId = Number(params.book);
  const chapter = Number(params.chapter);
  if (!Number.isFinite(bookId) || !Number.isFinite(chapter)) notFound();

  const [books, chapterData] = await Promise.all([
    listBooks(),
    getChapter(bookId, chapter).catch(() => null),
  ]);

  if (!chapterData) notFound();
  const book = chapterData.book;

  const nav = buildNav(books, book, chapter);

  return (
    <>
      <div className="reader-head">
        <h1>
          {book.name} {chapter}
        </h1>
      </div>

      <div className="reader-tools">
        {nav.prev ? (
          <Link className="btn" href={`/read/${nav.prev.book}/${nav.prev.chap}`}>
            ← {nav.prev.bookName}
            {nav.prev.sameBook ? "" : ` ${nav.prev.chap}`}
          </Link>
        ) : (
          <span className="btn" style={{ pointerEvents: "none", opacity: 0.4 }}>
            ← Start
          </span>
        )}

        <ChapterPicker
          bookId={book.id}
          chapter={chapter}
          totalChapters={book.chapters}
        />

        {nav.next ? (
          <Link className="btn" href={`/read/${nav.next.book}/${nav.next.chap}`}>
            {nav.next.sameBook ? "" : `${nav.next.bookName} `}
            {nav.next.chap} →
          </Link>
        ) : (
          <span className="btn" style={{ pointerEvents: "none", opacity: 0.4 }}>
            End →
          </span>
        )}

        <Link className="btn primary" href={`/read/${book.id}/1`}>
          {book.name} 1
        </Link>
      </div>

      <article className="passage">
        {chapterData.verses.map((v) => (
          <span className="v" key={v.verse}>
            <sup className="verse-ref">{v.verse}</sup>
            {v.text}{" "}
          </span>
        ))}
      </article>
    </>
  );
}

function buildNav(
  books: BookMeta[],
  book: BookMeta,
  chapter: number
): {
  prev: { book: number; chap: number; bookName: string; sameBook: boolean } | null;
  next: { book: number; chap: number; bookName: string; sameBook: boolean } | null;
} {
  const prevChap = chapter - 1;
  let prev =
    prevChap >= 1
      ? { book: book.id, chap: prevChap, bookName: book.name, sameBook: true }
      : null;
  if (!prev) {
    const prevBook = books.find((b) => b.id === book.id - 1);
    if (prevBook) prev = { book: prevBook.id, chap: prevBook.chapters, bookName: prevBook.name, sameBook: false };
  }

  const nextChap = chapter + 1;
  let next =
    nextChap <= book.chapters
      ? { book: book.id, chap: nextChap, bookName: book.name, sameBook: true }
      : null;
  if (!next) {
    const nextBook = books.find((b) => b.id === book.id + 1);
    if (nextBook) next = { book: nextBook.id, chap: 1, bookName: nextBook.name, sameBook: false };
  }

  return { prev, next };
}
