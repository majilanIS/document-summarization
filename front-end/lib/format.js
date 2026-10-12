export const SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".txt"];
// Keep in sync with MAX_UPLOAD_BYTES in back-end/app/api/documents.py.
export const MAX_FILE_BYTES = 100 * 1024 * 1024;

// Summary size is a share of the document's length (see the back-end's
// LENGTH_RATIOS), so longer documents get longer summaries.
export const LENGTHS = [
  { value: "short", label: "Short", percent: 10 },
  { value: "medium", label: "Medium", percent: 20 },
  { value: "detailed", label: "Detailed", percent: 30 },
];

export const ASPECTS = [
  { value: "accuracy", label: "Accuracy" },
  { value: "clarity", label: "Clarity" },
  { value: "coverage", label: "Coverage" },
  { value: "conciseness", label: "Conciseness" },
];

export function lengthInfo(value) {
  return LENGTHS.find((l) => l.value === value) ?? LENGTHS[1];
}

export function aspectLabel(value) {
  return ASPECTS.find((a) => a.value === value)?.label ?? value;
}

export function fileExtension(filename) {
  const dot = filename.lastIndexOf(".");
  return dot === -1 ? "" : filename.slice(dot).toLowerCase();
}

export function fileType(filename) {
  return fileExtension(filename).slice(1).toUpperCase() || "FILE";
}

/** Returns an error message, or null when the file can be uploaded. */
export function validateFile(file) {
  if (!SUPPORTED_EXTENSIONS.includes(fileExtension(file.name))) {
    return "Unsupported file type. Use a PDF, DOCX or TXT file.";
  }
  if (file.size > MAX_FILE_BYTES) {
    return "File is larger than 100 MB.";
  }
  if (file.size === 0) {
    return "File is empty.";
  }
  return null;
}

export function formatBytes(bytes) {
  if (!bytes) return "0 KB";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatNumber(n) {
  return n.toLocaleString("en-US");
}

export function formatSeconds(ms) {
  return `${(ms / 1000).toFixed(1)} seconds`;
}

export function formatDate(iso) {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function wordCount(text) {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}
