"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getFeedbackStats, listFeedback } from "@/lib/api";
import { ASPECTS, aspectLabel, formatDate, lengthInfo } from "@/lib/format";
import { ChatHeartIcon, StarIcon } from "@/components/icons";
import {
  Card,
  ErrorBanner,
  LoadingBlock,
  PageHeader,
  buttonPrimary,
} from "@/components/ui";

export default function FeedbackOverview() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let ignore = false;

    Promise.all([getFeedbackStats(), listFeedback()])
      .then(([stats, recent]) => {
        if (!ignore) {
          setData({ stats, recent });
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

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 md:px-8 md:py-12">
      <PageHeader
        title="Feedback"
        subtitle="How people rated the generated summaries."
      />

      <div className="flex flex-col gap-5">
        <ErrorBanner message={error} />
        {!data && !error && <LoadingBlock />}
        {data && <Overview stats={data.stats} recent={data.recent} />}
      </div>
    </div>
  );
}

function Overview({ stats, recent }) {
  if (stats.total_feedback === 0) {
    return (
      <Card className="flex flex-col items-center px-6 py-14 text-center">
        <ChatHeartIcon className="mb-3 size-10 text-primary" />
        <p className="text-sm font-medium text-ink">No feedback yet</p>
        <p className="mt-1 text-sm text-muted">
          Rate a summary to see it here.
        </p>
        <Link href="/" className={`${buttonPrimary} mt-5`}>
          Summarize a Document
        </Link>
      </Card>
    );
  }

  // Weighted average across models.
  const rated = stats.models.reduce((sum, m) => sum + m.ratings, 0);
  const average = rated
    ? stats.models.reduce((sum, m) => sum + (m.average_rating ?? 0) * m.ratings, 0) /
      rated
    : null;

  const aspectCounts = ASPECTS.map((a) => ({
    ...a,
    count: stats.aspects[a.value] ?? 0,
  }));
  const topAspect = [...aspectCounts].sort((a, b) => b.count - a.count)[0];

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatTile label="Total feedback" value={stats.total_feedback.toLocaleString("en-US")} />
        <StatTile
          label="Average rating"
          value={average === null ? "–" : `${average.toFixed(1)} / 5`}
        />
        <StatTile
          label="Most liked"
          value={topAspect.count ? topAspect.label : "–"}
        />
      </div>

      <AspectBars aspects={aspectCounts} total={stats.total_feedback} />

      <Card>
        <h2 className="border-b border-line px-5 py-4 text-sm font-semibold text-ink">
          Recent feedback
        </h2>
        <ul className="divide-y divide-line">
          {recent.map((f) => (
            <li key={f.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3.5">
              <div className="min-w-0 flex-1">
                <Link
                  href={`/summary?doc=${f.document_id}${f.summary_id ? `&summary=${f.summary_id}` : ""}`}
                  className="block truncate text-sm font-medium text-ink hover:text-primary"
                >
                  {f.filename}
                </Link>
                <p className="mt-0.5 text-xs text-muted">
                  {f.length && `${lengthInfo(f.length).label} summary · `}
                  {formatDate(f.created_at)}
                </p>
              </div>
              {f.aspects.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {f.aspects.map((a) => (
                    <span key={a} className="rounded-full bg-canvas px-2.5 py-0.5 text-xs text-ink-soft">
                      {aspectLabel(a)}
                    </span>
                  ))}
                </div>
              )}
              {f.rating !== null && <Stars rating={f.rating} />}
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}

function StatTile({ label, value }) {
  return (
    <Card className="px-5 py-4">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-ink">{value}</p>
    </Card>
  );
}

function AspectBars({ aspects, total }) {
  const max = Math.max(1, ...aspects.map((a) => a.count));

  return (
    <Card className="p-5">
      <h2 className="text-sm font-semibold text-ink">What people liked</h2>
      <p className="mt-0.5 text-xs text-muted">
        Times each aspect was ticked
      </p>
      <dl className="mt-4 flex flex-col gap-3">
        {aspects.map((a) => {
          const share = total ? Math.round((a.count / total) * 100) : 0;
          return (
            <div
              key={a.value}
              className="grid grid-cols-[6.5rem_1fr_2.5rem] items-center gap-3"
              title={`${a.label}: ${a.count} (${share}% of all feedback)`}
            >
              <dt className="text-sm text-ink-soft">{a.label}</dt>
              <dd className="h-2.5 rounded-r bg-primary-soft">
                <div
                  className="h-full rounded-r bg-primary"
                  style={{ width: `${(a.count / max) * 100}%` }}
                />
              </dd>
              <dd className="text-right text-sm tabular-nums text-ink">{a.count}</dd>
            </div>
          );
        })}
      </dl>
    </Card>
  );
}

function Stars({ rating }) {
  return (
    <span className="flex items-center gap-0.5 text-primary" aria-label={`${rating} out of 5`} role="img">
      {[1, 2, 3, 4, 5].map((v) => (
        <StarIcon
          key={v}
          className={`size-4 ${v <= rating ? "" : "text-line"}`}
          fill={v <= rating ? "currentColor" : "none"}
        />
      ))}
    </span>
  );
}
