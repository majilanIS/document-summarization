"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { deleteDocument, listDocuments } from "@/lib/api";
import { fileType, formatBytes, formatDate, formatNumber } from "@/lib/format";
import { FileTextIcon, TrashIcon, UploadCloudIcon } from "@/components/icons";
import {
  Card,
  ErrorBanner,
  LoadingBlock,
  PageHeader,
  buttonPrimary,
} from "@/components/ui";

export default function HistoryList() {
  const [documents, setDocuments] = useState(null);
  const [error, setError] = useState("");

  // Effects re-run whenever this page becomes visible again,
  // so returning to History shows newly summarized documents.
  useEffect(() => {
    let ignore = false;

    listDocuments()
      .then((docs) => {
        if (!ignore) {
          setDocuments(docs);
          setError("");
        }
      })
      .catch((err) => {
        if (!ignore) setError(err.message);
      });

    return () => {
      ignore = true;
    };
  }, []);

  async function handleDelete(doc) {
    if (!window.confirm(`Delete "${doc.filename}" and its summaries?`)) return;

    try {
      await deleteDocument(doc.id);
      setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 md:px-8 md:py-12">
      <PageHeader
        title="History"
        subtitle="Documents you have uploaded and summarized."
      />

      <div className="flex flex-col gap-4">
        <ErrorBanner message={error} />

        {documents === null && !error && <LoadingBlock />}

        {documents?.length === 0 && (
          <Card className="flex flex-col items-center px-6 py-14 text-center">
            <UploadCloudIcon className="mb-3 size-10 text-primary" />
            <p className="text-sm font-medium text-ink">No documents yet</p>
            <p className="mt-1 text-sm text-muted">
              Upload a document to get your first summary.
            </p>
            <Link href="/" className={`${buttonPrimary} mt-5`}>
              Upload Document
            </Link>
          </Card>
        )}

        {documents?.length > 0 && (
          <Card>
            <ul className="divide-y divide-line">
              {documents.map((doc) => (
                <li key={doc.id} className="flex items-center gap-4 px-5 py-4">
                  <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-primary-soft text-primary">
                    <FileTextIcon className="size-5" />
                  </span>
                  <Link
                    href={`/summary?doc=${doc.id}${
                      doc.latest_summary_id ? `&summary=${doc.latest_summary_id}` : ""
                    }`}
                    className="min-w-0 flex-1 rounded focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary"
                  >
                    <p className="truncate text-sm font-medium text-ink hover:text-primary">
                      {doc.filename}
                    </p>
                    <p className="mt-0.5 text-xs text-muted">
                      {fileType(doc.filename)}
                      <span className="mx-1.5">•</span>
                      {formatBytes(doc.file_size)}
                      <span className="mx-1.5">•</span>
                      {formatNumber(doc.word_count)} words
                      <span className="mx-1.5">•</span>
                      {formatDate(doc.created_at)}
                    </p>
                  </Link>
                  <span
                    className={`hidden shrink-0 rounded-full px-2.5 py-1 text-xs font-medium sm:inline ${
                      doc.summary_count
                        ? "bg-primary-soft text-primary"
                        : "bg-canvas text-muted"
                    }`}
                  >
                    {doc.summary_count === 1
                      ? "1 summary"
                      : `${doc.summary_count} summaries`}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleDelete(doc)}
                    aria-label={`Delete ${doc.filename}`}
                    className="grid size-8 shrink-0 place-items-center rounded-md text-muted transition-colors hover:bg-danger-soft hover:text-danger"
                  >
                    <TrashIcon className="size-4" />
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </div>
  );
}
