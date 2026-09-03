import Link from "next/link";

export default function NotFound() {
  return (
    <div style={{ textAlign: "center", padding: "60px 0" }}>
      <h1 className="page-title" style={{ fontSize: "3rem" }}>
        404
      </h1>
      <p className="muted">That passage could not be found.</p>
      <p>
        <Link className="btn primary" href="/">
          Browse the Bible
        </Link>
      </p>
    </div>
  );
}
