#!/usr/bin/env node
/**
 * Validates the bundled demo dataset: 66 books, sane chapter/verse counts,
 * non-empty text. Run:  npm run check:data
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const booksDir = path.join(root, "demo-data", "books");
const index = JSON.parse(
  fs.readFileSync(path.join(root, "demo-data", "index.json"), "utf-8")
);

if (index.length !== 66) {
  console.error(`Expected 66 books, got ${index.length}`);
  process.exit(1);
}

let verseCount = 0;
let bookFiles = 0;
const seenNames = new Set();
let errors = 0;

for (const b of index) {
  const file = path.join(booksDir, `${String(b.n).padStart(2, "0")}.json`);
  if (!fs.existsSync(file)) {
    console.error(`Missing file for ${b.name}: ${file}`);
    errors++;
    continue;
  }
  if (seenNames.has(b.name)) {
    console.error(`Duplicate book name: ${b.name}`);
    errors++;
  }
  seenNames.add(b.name);

  const data = JSON.parse(fs.readFileSync(file, "utf-8"));
  const chs = data.chapters;
  if (chs.length !== b.chapters) {
    console.error(
      `${b.name}: declared ${b.chapters} chapters, file has ${chs.length}`
    );
    errors++;
  }
  for (let c = 0; c < chs.length; c++) {
    const verses = chs[c];
    if (!Array.isArray(verses) || verses.length === 0) {
      console.error(`${b.name} ch ${c + 1}: no verses`);
      errors++;
    }
    for (const v of verses) {
      if (typeof v !== "string" || v.trim() === "") {
        console.error(`${b.name} ch ${c + 1}: empty verse text`);
        errors++;
      } else {
        verseCount++;
      }
    }
  }
  bookFiles++;
}

console.log(
  `OK: ${bookFiles} book files, ${index.length} books indexed, ${verseCount} verses.`
);
if (errors) {
  console.error(`${errors} problem(s) found.`);
  process.exit(1);
}
console.log("All checks passed.");
