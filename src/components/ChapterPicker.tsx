"use client";

import { useRouter } from "next/navigation";

export default function ChapterPicker({
  bookId,
  chapter,
  totalChapters,
}: {
  bookId: number;
  chapter: number;
  totalChapters: number;
}) {
  const router = useRouter();
  return (
    <select
      className="chapter-select"
      aria-label="Choose chapter"
      value={chapter}
      onChange={(e) =>
        router.push(`/read/${bookId}/${Number(e.target.value)}`)
      }
    >
      {Array.from({ length: totalChapters }, (_, i) => i + 1).map((n) => (
        <option key={n} value={n}>
          Chapter {n}
        </option>
      ))}
    </select>
  );
}
