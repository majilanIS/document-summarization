"use client";

import { useEffect, useRef, useState } from "react";
import { clearChat, getChat, rateChatMessage, sendChatMessage } from "@/lib/api";
import {
  AlertIcon,
  BotIcon,
  SendIcon,
  ThumbsDownIcon,
  ThumbsUpIcon,
  TrashIcon,
  UserIcon,
} from "@/components/icons";
import { Card, ErrorBanner, Spinner, buttonSecondary } from "@/components/ui";

const SUGGESTIONS = [
  "What is the main point of this document?",
  "What are the key findings or conclusions?",
  "Who is this document written for?",
  "What evidence or numbers does it give?",
];

// What the answer is credited to in the chat.
const ENGINES = {
  gemini: "Chekole",
  local: "Chekole (offline)",
};

// Chat about the document after its summary, so the reader can keep
// asking instead of stopping at the summary. Mount with key={documentId}.
export default function ChatPanel({ documentId, filename }) {
  const [messages, setMessages] = useState(null);
  const [input, setInput] = useState("");
  // The question being answered, shown until the reply arrives.
  const [pending, setPending] = useState(null);
  const [error, setError] = useState("");
  const listRef = useRef(null);

  useEffect(() => {
    let ignore = false;

    getChat(documentId)
      .then((history) => {
        if (!ignore) setMessages(history);
      })
      .catch((err) => {
        if (!ignore) {
          setMessages([]);
          setError(err.message);
        }
      });

    return () => {
      ignore = true;
    };
  }, [documentId]);

  // Keep the newest message in view (scrolls the list, not the page).
  useEffect(() => {
    const list = listRef.current;
    if (list) list.scrollTop = list.scrollHeight;
  }, [messages, pending]);

  async function ask(text) {
    const question = text.trim();
    if (!question || pending) return;

    setPending(question);
    setInput("");
    setError("");
    try {
      const reply = await sendChatMessage(documentId, question);
      setMessages((prev) => [...prev, reply.question, reply.answer]);
    } catch (err) {
      setError(err.message);
      // Give the question back so it can be sent again.
      setInput(question);
    } finally {
      setPending(null);
    }
  }

  async function rate(message, value) {
    // Clicking the active thumb again removes the rating.
    const rating = message.rating === value ? null : value;
    try {
      const updated = await rateChatMessage(message.id, rating);
      setMessages((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
    } catch (err) {
      setError(err.message);
    }
  }

  async function clear() {
    try {
      await clearChat(documentId);
      setMessages([]);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }

  function handleKeyDown(e) {
    // Enter sends, Shift+Enter adds a line.
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      ask(input);
    }
  }

  const empty = messages?.length === 0 && !pending;

  return (
    <Card className="flex flex-col">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
        <div>
          <h2 className="flex items-center gap-3 text-base font-semibold text-ink">
            <span className="grid size-8 place-items-center rounded-lg bg-primary-soft text-primary">
              <BotIcon className="size-[18px]" />
            </span>
            Ask about this document
          </h2>
          <p className="mt-1 text-xs text-muted sm:pl-11">
            Answers come from {filename}, with the passages they are based on.
          </p>
        </div>
        {messages?.length > 0 && (
          <button
            type="button"
            onClick={clear}
            disabled={pending !== null}
            className={`${buttonSecondary} px-3 py-1.5 text-xs`}
          >
            <TrashIcon className="size-3.5" />
            Clear chat
          </button>
        )}
      </div>

      <div
        ref={listRef}
        aria-live="polite"
        className="flex max-h-[32rem] min-h-40 flex-col gap-4 overflow-y-auto px-5 py-5"
      >
        {messages === null && (
          <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted">
            <Spinner className="size-4 text-primary" />
            Loading chat…
          </div>
        )}

        {empty && (
          <div className="flex flex-col items-start gap-3">
            <p className="text-sm text-ink-soft">
              Want to know more than the summary says? Ask anything about the
              document, or start with one of these:
            </p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => ask(s)}
                  className="rounded-full border border-line bg-surface px-3.5 py-1.5 text-left text-xs text-ink-soft transition-colors hover:border-primary-line hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages?.map((m) =>
          m.role === "user" ? (
            <UserBubble key={m.id} text={m.content} />
          ) : (
            <AnswerBubble key={m.id} message={m} onRate={rate} />
          )
        )}

        {pending && (
          <>
            <UserBubble text={pending} />
            <div className="flex items-center gap-2 text-sm text-muted">
              <Avatar />
              <Spinner className="size-4 text-primary" />
              Reading the document…
            </div>
          </>
        )}
      </div>

      <div className="border-t border-line px-5 py-4">
        {error && (
          <div className="mb-3">
            <ErrorBanner message={error} />
          </div>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(input);
          }}
          className="flex items-end gap-2"
        >
          <label htmlFor="chat-input" className="sr-only">
            Your question
          </label>
          <textarea
            id="chat-input"
            rows={1}
            value={input}
            maxLength={2000}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about the document…"
            className="field-sizing-content max-h-32 min-h-11 flex-1 resize-none rounded-lg border border-line bg-surface px-3.5 py-2.5 text-sm text-ink placeholder:text-muted focus:border-primary focus:outline-none"
          />
          <button
            type="submit"
            disabled={!input.trim() || pending !== null}
            aria-label="Send"
            className="grid size-11 shrink-0 place-items-center rounded-lg bg-primary text-white transition-colors hover:bg-primary-hover focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50"
          >
            {pending ? <Spinner className="size-4" /> : <SendIcon className="size-4" />}
          </button>
        </form>
        <p className="mt-2 text-xs text-muted">
          Enter to send, Shift+Enter for a new line. Answers can be wrong, so
          check the sources.
        </p>
      </div>
    </Card>
  );
}

function Avatar() {
  return (
    <span className="grid size-7 shrink-0 place-items-center rounded-full bg-primary-soft text-primary">
      <BotIcon className="size-4" />
    </span>
  );
}

function UserBubble({ text }) {
  return (
    <div className="flex justify-end gap-2">
      <p className="max-w-[85%] rounded-2xl rounded-tr-sm bg-primary px-4 py-2.5 text-sm leading-6 whitespace-pre-wrap text-white">
        {text}
      </p>
      <span className="grid size-7 shrink-0 place-items-center rounded-full bg-canvas text-muted">
        <UserIcon className="size-4" />
      </span>
    </div>
  );
}

function AnswerBubble({ message, onRate }) {
  // Source the reader is looking at, highlighted in the list.
  const [activeSource, setActiveSource] = useState(null);
  const details = message.details;
  const quotes = message.sources.filter((s) => s.kind === "quote");
  const passages = message.sources.filter((s) => s.kind !== "quote");

  function showSource(number) {
    setActiveSource(number);
    window.document
      .getElementById(sourceId(message.id, number))
      ?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  return (
    <div className="flex gap-2">
      <Avatar />
      <div className="min-w-0 max-w-[90%] flex-1">
        <div className="rounded-2xl rounded-tl-sm border border-line bg-surface px-4 py-3 text-sm leading-6 text-ink-soft">
          {details ? (
            <StructuredAnswer
              details={details}
              activeSource={activeSource}
              onCite={showSource}
            />
          ) : (
            <p className="whitespace-pre-wrap">{message.content}</p>
          )}
        </div>

        {quotes.length > 0 && (
          <div className="mt-2">
            <p className="mb-1.5 text-xs font-semibold text-muted">
              From the document
            </p>
            <ol className="flex flex-col gap-1.5">
              {quotes.map((s, i) => {
                const number = i + 1;
                const active = activeSource === number;
                return (
                  <li
                    key={i}
                    id={sourceId(message.id, number)}
                    onMouseEnter={() => setActiveSource(number)}
                    onMouseLeave={() => setActiveSource(null)}
                    className={`flex gap-2.5 rounded-lg border px-3 py-2 text-xs leading-5 transition-colors ${
                      active
                        ? "border-primary bg-primary-soft text-ink"
                        : "border-line bg-canvas text-ink-soft"
                    }`}
                  >
                    <CitationBadge number={number} active={active} />
                    <q className="italic">{s.text}</q>
                  </li>
                );
              })}
            </ol>
          </div>
        )}

        {passages.length > 0 && (
          <details className="group mt-1.5 text-xs">
            <summary className="cursor-pointer text-muted select-none hover:text-primary">
              Based on {passages.length}{" "}
              {passages.length === 1 ? "passage" : "passages"}
            </summary>
            <ul className="mt-2 flex flex-col gap-2">
              {passages.map((s, i) => (
                <li
                  key={i}
                  className="border-l-2 border-primary-line pl-3 leading-5 text-ink-soft"
                >
                  {s.kind === "summary" && (
                    <span className="mr-1 font-semibold text-muted">From the summary:</span>
                  )}
                  {s.text}
                </li>
              ))}
            </ul>
          </details>
        )}

        <div className="mt-1.5 flex items-center gap-1 text-xs text-muted">
          {message.engine && <span className="mr-2">{ENGINES[message.engine] ?? message.engine}</span>}
          <RateButton
            active={message.rating === 1}
            label="Helpful"
            onClick={() => onRate(message, 1)}
          >
            <ThumbsUpIcon className="size-3.5" />
          </RateButton>
          <RateButton
            active={message.rating === -1}
            label="Not helpful"
            onClick={() => onRate(message, -1)}
          >
            <ThumbsDownIcon className="size-3.5" />
          </RateButton>
        </div>
      </div>
    </div>
  );
}

function sourceId(messageId, number) {
  return `source-${messageId}-${number}`;
}

// Direct answer first, then the key points, each pointing to its source.
function StructuredAnswer({ details, activeSource, onCite }) {
  return (
    <div className="flex flex-col gap-3">
      <p className="text-[15px] leading-7 font-medium text-ink">
        <RichText text={details.direct_answer} />
      </p>

      {details.points.length > 0 && (
        <ul className="flex flex-col gap-2 border-t border-line pt-3">
          {details.points.map((point, i) => (
            <li key={i} className="flex gap-2.5">
              <span
                aria-hidden="true"
                className="mt-[9px] size-1.5 shrink-0 rounded-full bg-primary"
              />
              <span>
                <RichText text={point.text} />
                {point.source && (
                  <button
                    type="button"
                    onClick={() => onCite(point.source)}
                    aria-label={`Show source ${point.source}`}
                    title="Show the passage this comes from"
                    className="ml-1.5 inline-block align-[1px] focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-primary"
                  >
                    <CitationBadge
                      number={point.source}
                      active={activeSource === point.source}
                    />
                  </button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}

      {details.not_covered && (
        <p className="flex gap-2 rounded-lg bg-canvas px-3 py-2 text-xs leading-5 text-ink-soft">
          <AlertIcon className="mt-0.5 size-3.5 shrink-0 text-muted" />
          <span>
            <span className="font-semibold text-ink">Not in the document: </span>
            {details.not_covered}
          </span>
        </p>
      )}

      {details.unverified && (
        <p className="flex gap-2 rounded-lg bg-danger-soft px-3 py-2 text-xs leading-5 text-danger">
          <AlertIcon className="mt-0.5 size-3.5 shrink-0" />
          Some figures in this answer couldn&apos;t be matched to the
          document&apos;s wording. Check them against the passages below.
        </p>
      )}
    </div>
  );
}

function CitationBadge({ number, active }) {
  return (
    <span
      className={`grid size-5 shrink-0 place-items-center rounded-md text-[11px] leading-none font-semibold transition-colors ${
        active ? "bg-primary text-white" : "bg-primary-soft text-primary hover:bg-primary hover:text-white"
      }`}
    >
      {number}
    </span>
  );
}

// Renders **bold** key terms; everything else as plain text.
function RichText({ text }) {
  return text.split(/(\*\*[^*]+\*\*)/).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4 ? (
      <strong key={i} className="font-semibold text-ink">
        {part.slice(2, -2)}
      </strong>
    ) : (
      part
    )
  );
}

function RateButton({ active, label, onClick, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      aria-label={label}
      title={label}
      className={`grid size-7 place-items-center rounded-md transition-colors focus-visible:outline-2 focus-visible:outline-primary ${
        active ? "bg-primary-soft text-primary" : "hover:bg-canvas hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}
