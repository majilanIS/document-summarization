"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { generateSummary, getDocument } from "@/lib/api";
import {
  LENGTHS,
  fileType,
  formatBytes,
  formatNumber,
  formatSeconds,
  lengthInfo,
  wordCount,
} from "@/lib/format";
import {
  ArrowLeftIcon,
  CheckIcon,
  ClockIcon,
  CopyIcon,
  DownloadIcon,
  FileTextIcon,
  ListIcon,
  SparklesIcon,
  TimerIcon,
} from "@/components/icons";
import ChatPanel from "@/components/ChatPanel";
import FeedbackForm from "@/components/FeedbackForm";
import {
  readingMinutes,
  structureSummary,
  summaryToText,
} from "@/lib/summary";
import {
  Card,
  ErrorBanner,
  LoadingBlock,
  Spinner,
  buttonPrimary,
  buttonSecondary,
} from "@/components/ui";

export default function SummaryView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const docId = searchParams.get("doc");
  const summaryId = searchParams.get("summary");

  // { docId, document } or { docId, error }; stale while docId changes.
  const [result, setResult] = useState(null);
  const [generating, setGenerating] = useState(null);
  const [generateError, setGenerateError] = useState("");
  // "points" (bullets per part) or "paragraphs"
  const [view, setView] = useState("points");

  useEffect(() => {
    if (!docId) return;
    let ignore = false;

    getDocument(docId)
      .then((document) => {
        if (!ignore) setResult({ docId, document });
      })
      .catch((err) => {
        if (!ignore) setResult({ docId, error: err.message });
      });

    return () => {
      ignore = true;
    };
  }, [docId]);

  if (!docId) {
    return (
      <Shell>
        <ErrorBanner message="No document selected." />
      </Shell>
    );
  }

  if (result?.docId !== docId) {
    return (
      <Shell>
        <LoadingBlock label="Loading summary…" />
      </Shell>
    );
  }

  if (result.error) {
    return (
      <Shell>
        <ErrorBanner message={result.error} />
      </Shell>
    );
  }

  const { document } = result;
  const summaries = document.summaries;
  const summary =
    summaries.find((s) => s.id === summaryId) ?? summaries.at(-1) ?? null;

  function showSummary(id) {
    router.replace(`/summary?doc=${docId}&summary=${id}`, { scroll: false });
  }

  async function handleLength(length) {
    // Reuse the newest existing summary of that length.
    const existing = summaries.findLast((s) => s.length === length);
    if (existing) {
      showSummary(existing.id);
      return;
    }

    setGenerating(length);
    setGenerateError("");
    try {
      const created = await generateSummary(docId, length);
      setResult((prev) => ({
        ...prev,
        document: {
          ...prev.document,
          summaries: [...prev.document.summaries, created],
        },
      }));
      showSummary(created.id);
    } catch (err) {
      setGenerateError(err.message);
    } finally {
      setGenerating(null);
    }
  }

  return (
    <Shell>
      <DocumentHeader document={document} summary={summary} view={view} />

      {summary ? (
        <>
          <SummaryCard
            summary={summary}
            documentWords={document.word_count}
            view={view}
            onViewChange={setView}
          />
          <LengthSwitcher
            current={summary.length}
            generating={generating}
            onSelect={handleLength}
          />
          <ErrorBanner message={generateError} />
          <FeedbackForm key={summary.id} summaryId={summary.id} />
          <ChatPanel
            key={docId}
            documentId={docId}
            filename={document.filename}
          />
        </>
      ) : (
        <Card className="p-6">
          <p className="text-sm text-ink">
            This document doesn&apos;t have a summary yet.
          </p>
          <div className="mt-4">
            <LengthSwitcher
              current={null}
              generating={generating}
              onSelect={handleLength}
            />
          </div>
          <div className="mt-4">
            <ErrorBanner message={generateError} />
          </div>
        </Card>
      )}
    </Shell>
  );
}

function Shell({ children }) {
  return (
    <div className="mx-auto max-w-5xl px-4 py-6 md:px-8 md:py-8">
      <Link
        href="/"
        className="mb-5 inline-flex items-center gap-2 text-sm font-medium text-primary hover:text-primary-hover"
      >
        <ArrowLeftIcon className="size-4" />
        Back to Upload
      </Link>
      <div className="flex flex-col gap-5">{children}</div>
    </div>
  );
}

function DocumentHeader({ document, summary, view }) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(timer);
  }, [copied]);

  // Copy and download in the same layout as shown on screen.
  function summaryText() {
    return summaryToText(structureSummary(summary.text), view);
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(summaryText());
      setCopied(true);
    } catch {
      // Clipboard can be blocked (e.g. insecure context); nothing to do.
    }
  }

  function download() {
    const base = document.filename.replace(/\.[^.]+$/, "");
    const content = `Summary of ${document.filename} (${lengthInfo(summary.length).label})\n\n${summaryText()}\n`;
    const url = URL.createObjectURL(
      new Blob([content], { type: "text/plain;charset=utf-8" })
    );
    const link = Object.assign(window.document.createElement("a"), {
      href: url,
      download: `${base}-summary.txt`,
    });
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Card className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
      <span className="grid size-12 shrink-0 place-items-center rounded-xl bg-primary-soft text-primary">
        <FileTextIcon className="size-6" />
      </span>
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-lg font-semibold text-ink">
          {document.filename}
        </h1>
        <p className="mt-0.5 text-xs text-muted">
          {formatBytes(document.file_size)}
          <span className="mx-2">•</span>
          {fileType(document.filename)}
          <span className="mx-2">•</span>
          {formatNumber(document.char_count)} characters
        </p>
      </div>
      {summary && (
        <div className="flex gap-2">
          <button type="button" onClick={download} className={buttonPrimary}>
            <DownloadIcon className="size-4" />
            Download Summary
          </button>
          <button type="button" onClick={copy} className={buttonSecondary}>
            {copied ? (
              <CheckIcon className="size-4 text-success" />
            ) : (
              <CopyIcon className="size-4" />
            )}
            <span aria-live="polite">{copied ? "Copied" : "Copy"}</span>
          </button>
        </div>
      )}
    </Card>
  );
}

function SummaryCard({ summary, documentWords, view, onViewChange }) {
  const info = lengthInfo(summary.length);
  const words = wordCount(summary.text);
  const sections = structureSummary(summary.text);
  const share = documentWords ? Math.round((words / documentWords) * 100) : 0;
  const pointCount = sections.reduce((n, s) => n + s.sentences.length, 0);

  return (
    <Card className="bg-primary-soft/40 p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-3 text-base font-semibold text-ink">
          <span className="grid size-8 place-items-center rounded-lg bg-primary-soft text-primary">
            <ListIcon className="size-[18px]" />
          </span>
          Generated Summary
        </h2>
        <ViewToggle view={view} onChange={onViewChange} />
      </div>

      <ul className="mb-4 flex flex-wrap gap-2 text-xs">
        <StatChip>
          <span className="font-semibold text-primary">{info.label}</span>
        </StatChip>
        <StatChip>
          {formatNumber(words)} of {formatNumber(documentWords)} words ({share}%)
        </StatChip>
        <StatChip>
          <ClockIcon className="size-3.5" />~{readingMinutes(words)} min read
        </StatChip>
        <StatChip>
          {sections.length > 1 ? `${sections.length} parts · ` : ""}
          {pointCount} key {pointCount === 1 ? "point" : "points"}
        </StatChip>
        {summary.grounding !== null && summary.grounding !== undefined && (
          <StatChip title="Share of checks passed when this summary was verified against the document: its evidence quotes must appear in the document, and so must every number it gives.">
            <CheckIcon
              className={`size-3.5 ${summary.grounding >= 0.9 ? "text-success" : "text-danger"}`}
            />
            {Math.round(summary.grounding * 100)}% verified against document
          </StatChip>
        )}
        {summary.candidates > 1 && (
          <StatChip
            title={`For each part, the reward model trained on your feedback picked the best of ${summary.candidates} candidate summaries. Reward score: ${summary.reward?.toFixed(2) ?? "–"}`}
          >
            <SparklesIcon className="size-3.5 text-primary" />
            Best of {summary.candidates} · feedback-tuned
          </StatChip>
        )}
      </ul>

      <div className="rounded-lg border border-line bg-surface px-5 py-5">
        {view === "points" ? (
          <KeyPoints sections={sections} />
        ) : (
          <div className="flex flex-col gap-4">
            {sections.map((section, i) => (
              <p key={i} className="text-[15px] leading-7 text-ink-soft">
                {section.text}
              </p>
            ))}
          </div>
        )}
      </div>

      <p className="mt-4 flex items-center justify-end gap-2 text-xs text-muted">
        <TimerIcon className="size-4" />
        Generated in: {formatSeconds(summary.duration_ms)}
      </p>
    </Card>
  );
}

function ViewToggle({ view, onChange }) {
  const options = [
    { value: "points", label: "Key points" },
    { value: "paragraphs", label: "Paragraphs" },
  ];

  return (
    <div
      role="group"
      aria-label="Summary layout"
      className="inline-flex rounded-lg border border-line bg-surface p-0.5"
    >
      {options.map((option) => {
        const active = option.value === view;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary ${
              active ? "bg-primary text-white" : "text-ink-soft hover:bg-canvas"
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function StatChip({ children, title }) {
  return (
    <li
      title={title}
      className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 text-ink-soft"
    >
      {children}
    </li>
  );
}

// Each part of the document as a numbered step, its sentences as bullets.
function KeyPoints({ sections }) {
  if (sections.length === 1) {
    return <PointList sentences={sections[0].sentences} />;
  }

  return (
    <ol className="flex flex-col">
      {sections.map((section, i) => (
        <li key={i} className="relative flex gap-4 pb-6 last:pb-0">
          {i < sections.length - 1 && (
            <span
              aria-hidden="true"
              className="absolute top-8 bottom-0 left-[13px] w-0.5 bg-primary-line"
            />
          )}
          <span className="relative grid size-7 shrink-0 place-items-center rounded-full bg-primary text-xs font-semibold text-white">
            {i + 1}
          </span>
          <div className="min-w-0 flex-1 pt-0.5">
            <h3 className="mb-2 text-xs font-semibold tracking-wide text-muted uppercase">
              Part {i + 1}
            </h3>
            <PointList sentences={section.sentences} />
          </div>
        </li>
      ))}
    </ol>
  );
}

function PointList({ sentences }) {
  return (
    <ul className="flex flex-col gap-2.5">
      {sentences.map((sentence, i) => (
        <li key={i} className="flex gap-3 text-[15px] leading-7 text-ink-soft">
          <span
            aria-hidden="true"
            className="mt-[11px] size-1.5 shrink-0 rounded-full bg-primary"
          />
          <span>{sentence}</span>
        </li>
      ))}
    </ul>
  );
}

function LengthSwitcher({ current, generating, onSelect }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="mr-1 text-sm text-muted">
        {current ? "Try another length:" : "Generate a summary:"}
      </span>
      {LENGTHS.map((option) => {
        const active = option.value === current;
        const busy = generating === option.value;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onSelect(option.value)}
            disabled={active || generating !== null}
            aria-pressed={active}
            className={`inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-xs font-medium transition-colors disabled:cursor-not-allowed ${
              active
                ? "border-primary bg-primary-soft text-primary"
                : "border-line bg-surface text-ink-soft hover:border-primary-line disabled:opacity-60"
            }`}
          >
            {busy && <Spinner className="size-3.5 text-primary" />}
            {option.label}
          </button>
        );
      })}
      {generating && (
        <span className="text-xs text-muted" aria-live="polite">
          Generating… this can take a minute.
        </span>
      )}
    </div>
  );
}
