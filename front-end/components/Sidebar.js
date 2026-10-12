"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  FeedbackIcon,
  HistoryIcon,
  HomeIcon,
  Logo,
  UserIcon,
} from "@/components/icons";

const NAV = [
  { href: "/", label: "Upload", icon: HomeIcon, match: ["/"] },
  { href: "/history", label: "History", icon: HistoryIcon, match: ["/history"] },
  // The summary result page is where feedback is given, so it lights up Feedback.
  {
    href: "/feedback",
    label: "Feedback",
    icon: FeedbackIcon,
    match: ["/feedback", "/summary"],
  },
];

function NavLinks({ pathname, compact = false }) {
  return NAV.map(({ href, label, icon: Icon, match }) => {
    const active = match.includes(pathname);
    return (
      <Link
        key={href}
        href={href}
        aria-current={active ? "page" : undefined}
        className={`flex items-center gap-3 rounded-lg text-sm font-medium transition-colors ${
          compact ? "px-3 py-2" : "px-3.5 py-2.5"
        } ${
          active
            ? "bg-primary text-white"
            : "text-sidebar-ink hover:bg-sidebar-hover hover:text-white"
        }`}
      >
        <Icon className="size-[18px] shrink-0" />
        <span className={compact ? "sr-only sm:not-sr-only" : ""}>{label}</span>
      </Link>
    );
  });
}

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <>
      {/* Desktop */}
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col bg-sidebar px-4 py-6 md:flex">
        <Link href="/" className="mb-8 flex items-center gap-3 px-2">
          <Logo />
          <span className="text-[15px] font-semibold text-white">
            DocSummarizer
          </span>
        </Link>

        <nav className="flex flex-col gap-1.5" aria-label="Main">
          <NavLinks pathname={pathname} />
        </nav>

        <div className="mt-auto flex items-center gap-3 px-2">
          <span className="grid size-9 place-items-center rounded-full bg-sidebar-hover text-sidebar-ink">
            <UserIcon className="size-[18px]" />
          </span>
          <div className="leading-tight">
            <p className="text-sm font-medium text-white">Guest</p>
            <p className="text-xs text-sidebar-ink">No sign-in needed</p>
          </div>
        </div>
      </aside>

      {/* Mobile */}
      <header className="sticky top-0 z-10 flex items-center justify-between gap-2 bg-sidebar px-4 py-3 md:hidden">
        <Link href="/" className="flex items-center gap-2">
          <Logo className="size-7" />
          <span className="text-sm font-semibold text-white">DocSummarizer</span>
        </Link>
        <nav className="flex gap-1" aria-label="Main">
          <NavLinks pathname={pathname} compact />
        </nav>
      </header>
    </>
  );
}
