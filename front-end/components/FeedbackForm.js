"use client";

import { useState } from "react";
import { sendFeedback } from "@/lib/api";
import { ASPECTS } from "@/lib/format";
import {
  ChatHeartIcon,
  CheckCircleIcon,
  CheckIcon,
  StarIcon,
} from "@/components/icons";
import { Card, ErrorBanner, Spinner, buttonPrimary } from "@/components/ui";

export default function FeedbackForm({ summaryId }) {
  const [rating, setRating] = useState(0);
  const [hovered, setHovered] = useState(0);
  const [aspects, setAspects] = useState([]);
  const [status, setStatus] = useState("idle"); // idle | sending | sent
  const [error, setError] = useState("");

  function toggleAspect(value) {
    setAspects((prev) =>
      prev.includes(value) ? prev.filter((a) => a !== value) : [...prev, value]
    );
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!rating) return;

    setStatus("sending");
    setError("");
    try {
      await sendFeedback({ summaryId, rating, aspects });
      setStatus("sent");
    } catch (err) {
      setError(err.message);
      setStatus("idle");
    }
  }

  if (status === "sent") {
    return (
      <Card className="flex items-center gap-4 p-5">
        <span className="grid size-10 place-items-center rounded-full bg-success-soft text-success">
          <CheckCircleIcon className="size-5" />
        </span>
        <div>
          <p className="text-sm font-semibold text-ink">Thanks for your feedback!</p>
          <p className="text-xs text-muted">
            It helps us improve the quality of future summaries.
          </p>
        </div>
      </Card>
    );
  }

  const shown = hovered || rating;

  return (
    <Card className="p-5">
      <form
        onSubmit={handleSubmit}
        className="flex flex-col gap-6 lg:flex-row lg:items-center"
      >
        <div className="lg:flex-1">
          <h2 className="flex items-center gap-3 text-base font-semibold text-ink">
            <span className="grid size-8 place-items-center rounded-lg bg-primary-soft text-primary">
              <ChatHeartIcon className="size-[18px]" />
            </span>
            Was this summary helpful?
          </h2>
          <p className="mt-1 text-xs text-muted sm:pl-11">
            Your feedback helps us improve the quality of future summaries.
          </p>

          <div
            role="radiogroup"
            aria-label="Rating"
            className="mt-4 flex gap-2 sm:pl-11"
            onMouseLeave={() => setHovered(0)}
          >
            {[1, 2, 3, 4, 5].map((value) => {
              const filled = value <= shown;
              return (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={rating === value}
                  aria-label={`${value} out of 5`}
                  onClick={() => setRating(value)}
                  onMouseEnter={() => setHovered(value)}
                  className={`flex h-16 w-14 flex-col items-center justify-center gap-1 rounded-lg border text-xs transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary ${
                    filled
                      ? "border-primary bg-primary-soft text-primary"
                      : "border-line bg-surface text-muted hover:border-primary-line"
                  }`}
                >
                  <StarIcon
                    className="size-5"
                    fill={filled ? "currentColor" : "none"}
                  />
                  {value}
                </button>
              );
            })}
          </div>
        </div>

        <div className="border-line lg:border-l lg:pl-8">
          <p className="text-xs font-semibold text-ink">
            What did you like? <span className="font-normal text-muted">(Optional)</span>
          </p>
          <div className="mt-3 grid grid-cols-2 gap-x-8 gap-y-3">
            {ASPECTS.map(({ value, label }) => {
              const checked = aspects.includes(value);
              return (
                <label
                  key={value}
                  className="flex cursor-pointer items-center gap-2 text-sm text-ink-soft has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-primary"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleAspect(value)}
                    className="sr-only"
                  />
                  <span
                    className={`grid size-4 place-items-center rounded border ${
                      checked ? "border-primary bg-primary text-white" : "border-muted/50 bg-surface"
                    }`}
                  >
                    {checked && <CheckIcon className="size-3" strokeWidth="3" />}
                  </span>
                  {label}
                </label>
              );
            })}
          </div>
        </div>

        <div className="flex flex-col gap-2 lg:w-52">
          <button
            type="submit"
            disabled={!rating || status === "sending"}
            className={`${buttonPrimary} w-full py-3`}
          >
            {status === "sending" ? (
              <Spinner className="size-4" />
            ) : (
              <CheckCircleIcon className="size-[18px]" />
            )}
            Submit Feedback
          </button>
          {!rating && (
            <p className="text-center text-xs text-muted">Choose a rating first</p>
          )}
        </div>
      </form>

      {error && (
        <div className="mt-4">
          <ErrorBanner message={error} />
        </div>
      )}
    </Card>
  );
}
