"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { checkHealth, generateSummary, uploadDocument } from "@/lib/api";
import { LENGTHS, formatBytes, validateFile } from "@/lib/format";
import {
  ArrowRightIcon,
  CheckIcon,
  FileTextIcon,
  UploadCloudIcon,
  XIcon,
} from "@/components/icons";
import { Card, ErrorBanner, PageHeader, buttonPrimary } from "@/components/ui";

const STEPS = [
  { title: "Reading and extracting text", detail: "Parsing your document…" },
  { title: "Generating summary", detail: "Using AI model…" },
  { title: "Finalizing results", detail: "Almost done…" },
];

export default function UploadFlow() {
  const router = useRouter();
  const inputRef = useRef(null);

  const [file, setFile] = useState(null);
  const [length, setLength] = useState("medium");
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState("");
  const [processing, setProcessing] = useState(false);
  const [step, setStep] = useState(0);

  // Upload result for the current file, so a retry after a failed
  // summary doesn't upload the same file twice.
  const uploaded = useRef(null);
  const shouldReset = useRef(false);

  // Cache Components keeps this page mounted (hidden) after navigating to
  // the result. Reset it so "Upload" shows a fresh form when revisited.
  useLayoutEffect(() => {
    return () => {
      if (shouldReset.current) {
        shouldReset.current = false;
        uploaded.current = null;
        setFile(null);
        setProcessing(false);
        setStep(0);
        setError("");
      }
    };
  }, []);

  // Warn before closing the tab mid-summary.
  useEffect(() => {
    if (!processing) return;
    const warn = (e) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [processing]);

  function chooseFile(next) {
    if (!next) return;
    const problem = validateFile(next);
    if (problem) {
      setError(problem);
      return;
    }
    setError("");
    setFile(next);
    uploaded.current = null;
  }

  function removeFile() {
    setFile(null);
    uploaded.current = null;
    if (inputRef.current) inputRef.current.value = "";
  }

  async function handleGenerate() {
    if (!file || processing) return;

    setError("");
    setProcessing(true);
    setStep(0);

    try {
      let document = uploaded.current;
      if (!document) {
        document = await uploadDocument(file);
        uploaded.current = document;
      }

      setStep(1);
      const summary = await generateSummary(document.id, length);

      setStep(2);
      shouldReset.current = true;
      router.push(`/summary?doc=${document.id}&summary=${summary.id}`);
    } catch (err) {
      setError(err.message);
      setProcessing(false);
    }
  }

  if (processing) {
    return <ProcessingScreen step={step} />;
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 md:px-8 md:py-12">
      <PageHeader
        title="Upload Document"
        subtitle="Select a document and choose the summary length."
      />

      <div className="flex flex-col gap-6">
        <BackendStatus />

        <label
          onDragOver={(e) => {
            e.preventDefault();
            setDragActive(true);
          }}
          onDragLeave={(e) => {
            // Ignore leaving into a child element.
            if (!e.currentTarget.contains(e.relatedTarget)) setDragActive(false);
          }}
          onDrop={(e) => {
            e.preventDefault();
            setDragActive(false);
            chooseFile(e.dataTransfer.files?.[0]);
          }}
          className={`flex cursor-pointer flex-col items-center rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors focus-within:border-primary has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-primary ${
            dragActive
              ? "border-primary bg-primary-soft"
              : "border-line bg-surface hover:border-primary-line hover:bg-primary-soft/40"
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,.txt"
            className="sr-only"
            onChange={(e) => chooseFile(e.target.files?.[0])}
          />
          <UploadCloudIcon className="mb-4 size-11 text-primary" />
          <span className="text-sm font-semibold text-ink">
            Drag and drop your file here
          </span>
          <span className="mt-1 text-sm text-primary">or click to browse</span>
          <span className="mt-5 text-xs text-muted">
            Supported formats: PDF, DOCX, TXT
            <span className="mx-2 text-line">|</span>
            Max size: 10 MB
          </span>
        </label>

        {file && (
          <Card className="flex items-center gap-3 px-4 py-3">
            <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-primary-soft text-primary">
              <FileTextIcon className="size-5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-ink">{file.name}</p>
              <p className="text-xs text-muted">{formatBytes(file.size)}</p>
            </div>
            <button
              type="button"
              onClick={removeFile}
              aria-label={`Remove ${file.name}`}
              className="grid size-8 place-items-center rounded-md text-muted transition-colors hover:bg-canvas hover:text-ink"
            >
              <XIcon className="size-4" />
            </button>
          </Card>
        )}

        <ErrorBanner message={error} />

        <fieldset>
          <legend className="mb-3 text-sm font-semibold text-ink">
            Summary Length
          </legend>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {LENGTHS.map((option) => {
              const selected = option.value === length;
              return (
                <label
                  key={option.value}
                  className={`flex cursor-pointer items-start gap-3 rounded-xl border px-4 py-3.5 transition-colors has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-primary ${
                    selected
                      ? "border-primary bg-primary-soft"
                      : "border-line bg-surface hover:border-primary-line"
                  }`}
                >
                  <input
                    type="radio"
                    name="length"
                    value={option.value}
                    checked={selected}
                    onChange={() => setLength(option.value)}
                    className="sr-only"
                  />
                  <span
                    className={`mt-0.5 grid size-4 shrink-0 place-items-center rounded-full border ${
                      selected ? "border-primary bg-primary" : "border-muted/50"
                    }`}
                  >
                    {selected && <CheckIcon className="size-3 text-white" strokeWidth="3" />}
                  </span>
                  <span>
                    <span className="block text-sm font-medium text-ink">
                      {option.label}
                    </span>
                    <span className="block text-xs text-muted">
                      ~{option.percent}% of the text
                    </span>
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>

        <button
          type="button"
          onClick={handleGenerate}
          disabled={!file}
          className={`${buttonPrimary} w-full py-3`}
        >
          <ArrowRightIcon className="size-[18px]" />
          Generate Summary
        </button>
      </div>
    </div>
  );
}

// Warns up front when the backend can't be reached, instead of failing
// only after the user presses Generate.
function BackendStatus() {
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;

    checkHealth()
      .then(() => {
        if (!ignore) setError("");
      })
      .catch((err) => {
        if (!ignore) setError(err.message);
      });

    return () => {
      ignore = true;
    };
  }, []);

  return <ErrorBanner message={error} />;
}

function ProcessingScreen({ step }) {
  return (
    <div
      className="mx-auto flex max-w-xl flex-col items-center px-4 py-12 text-center md:py-20"
      aria-live="polite"
    >
      <div className="relative mb-8 grid size-36 place-items-center rounded-full bg-primary-soft">
        <svg viewBox="0 0 120 120" className="absolute inset-0 size-full animate-spin [animation-duration:1.6s]" aria-hidden="true">
          <circle cx="60" cy="60" r="54" fill="none" stroke="var(--primary-line)" strokeWidth="6" />
          <circle
            cx="60"
            cy="60"
            r="54"
            fill="none"
            stroke="var(--primary)"
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray="110 340"
          />
        </svg>
        <span className="grid size-16 place-items-center rounded-2xl bg-surface text-primary shadow-sm">
          <FileTextIcon className="size-8" />
        </span>
      </div>

      <h1 className="text-2xl font-semibold tracking-tight text-ink">
        Summarizing Your Document…
      </h1>
      <p className="mt-2 text-sm text-muted">
        This may take a few moments. Please don&apos;t close the page.
      </p>

      <ol className="mt-10 flex flex-col text-left">
        {STEPS.map((s, i) => {
          const state = i < step ? "done" : i === step ? "active" : "pending";
          return (
            <li key={s.title} className="relative flex gap-4 pb-8 last:pb-0">
              {i < STEPS.length - 1 && (
                <span
                  className={`absolute top-7 left-[11px] h-[calc(100%-1.75rem)] w-0.5 ${
                    i < step ? "bg-primary" : "bg-line"
                  }`}
                  aria-hidden="true"
                />
              )}
              <span
                className={`relative grid size-6 shrink-0 place-items-center rounded-full border-2 ${
                  state === "done"
                    ? "border-primary bg-primary text-white"
                    : state === "active"
                      ? "border-primary bg-surface"
                      : "border-line bg-surface"
                }`}
              >
                {state === "done" && <CheckIcon className="size-3.5" strokeWidth="3" />}
                {state === "active" && (
                  <span className="size-2 animate-pulse rounded-full bg-primary" />
                )}
              </span>
              <div>
                <p
                  className={`text-sm font-medium ${
                    state === "active" ? "text-primary" : state === "done" ? "text-ink" : "text-muted"
                  }`}
                >
                  {s.title}
                  <span className="sr-only">
                    {state === "done" ? " (done)" : state === "active" ? " (in progress)" : ""}
                  </span>
                </p>
                <p className="text-xs text-muted">{s.detail}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
