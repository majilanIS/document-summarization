import { Suspense } from "react";
import SummaryView from "@/components/SummaryView";
import { LoadingBlock } from "@/components/ui";

export const metadata = {
  title: "Summary",
};

// SummaryView reads ?doc= and ?summary= with useSearchParams, which needs
// a Suspense boundary so the rest of the page can be prerendered.
export default function SummaryPage() {
  return (
    <Suspense fallback={<LoadingBlock label="Loading summary…" />}>
      <SummaryView />
    </Suspense>
  );
}
