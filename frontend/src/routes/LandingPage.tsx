import { Link } from "react-router-dom";
import { ChannelBadge } from "@/components/shared/ChannelBadge";
import { Logo } from "@/components/shared/Logo";
import { buttonVariants } from "@/components/ui/button";
import { GhostMascot } from "@/features/landing/components/GhostMascot";
import { HISTORY, PURPOSE } from "@/features/landing/content";
import { paths } from "@/lib/paths";
import { cn } from "@/lib/utils";

const SECTION = "mx-auto w-full max-w-5xl px-4 py-12 sm:py-16";
const HEADING = "text-2xl font-bold sm:text-3xl";

function DemoConversation() {
  return (
    <div
      role="img"
      aria-label="Example conversation: a web message, and an SMS reply from a basic phone. Both are simulated."
      className="w-full max-w-sm space-y-3 rounded-panel border border-border bg-surface p-4 bevel"
    >
      <div className="flex flex-col items-end gap-1">
        <ChannelBadge channel="internet" />
        <p
          data-bubble="out"
          className="rounded-bubble bg-bubble-out px-3 py-2 text-sm text-bubble-out-fg"
        >
          hey, are you still alive? 👻
        </p>
      </div>
      <div className="flex flex-col items-start gap-1">
        <ChannelBadge channel="sms-inbound" smsMode="simulated" />
        <p
          data-bubble="in"
          className="rounded-bubble bg-bubble-in px-3 py-2 text-sm text-bubble-in-fg"
        >
          barely. typing from a Nokia in the afterlife
        </p>
      </div>
      <p className="text-xs text-fg-muted">Example only. Nothing here was sent.</p>
    </div>
  );
}

/** Public home for visitors who are not signed in. Signed-in users see the app home instead. */
export function LandingPage() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-border">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-2 px-4 py-3">
          <Logo size="md" />
          <nav aria-label="Account" className="flex items-center gap-2">
            <Link to={paths.signIn} className={buttonVariants({ variant: "ghost", size: "sm" })}>
              Sign in
            </Link>
            <Link to={paths.register} className={buttonVariants({ size: "sm" })}>
              Create account
            </Link>
          </nav>
        </div>
      </header>

      <main id="main-content" tabIndex={-1}>
        <section aria-labelledby="hero-heading" className={cn(SECTION, "grid gap-8 md:grid-cols-2")}>
          <div className="flex flex-col justify-center gap-4">
            <p className="text-sm font-semibold uppercase tracking-wide text-accent">
              Kiroween 2026 · Resurrection
            </p>
            <h1 id="hero-heading" className="text-4xl font-extrabold leading-tight sm:text-5xl">
              The messenger that refused to die.
            </h1>
            <p className="text-lg text-fg-muted">
              Chikka let people chat from a computer with friends who only had a basic mobile phone.
              It closed in 2018. We dug it up, dusted it off, and gave it a pulse.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link to={paths.register} className={buttonVariants()}>
                Join the séance
              </Link>
              <Link to={paths.signIn} className={buttonVariants({ variant: "secondary" })}>
                I already have an account
              </Link>
            </div>
          </div>
          <div className="flex flex-col items-center justify-center gap-6">
            <GhostMascot />
          </div>
        </section>

        <section aria-labelledby="what-heading" className={cn(SECTION, "grid gap-8 md:grid-cols-2")}>
          <div className="space-y-3">
            <h2 id="what-heading" className={HEADING}>
              What is Chikka Reborn?
            </h2>
            <p className="text-fg-muted">
              A web messenger where one conversation can include people on the internet and people on
              plain text messages. Chat with other users instantly. Text a phone from your browser.
              When they reply by SMS, the answer shows up in the same thread.
            </p>
            <p className="text-fg-muted">
              You can switch between Modern Mode and Classic Mode, a nostalgic look for people who
              remember the original.
            </p>
          </div>
          <div className="flex justify-center md:justify-end">
            <DemoConversation />
          </div>
        </section>

        <section aria-labelledby="history-heading" className={SECTION}>
          <h2 id="history-heading" className={HEADING}>
            A short, slightly spooky history
          </h2>
          <ol className="mt-6 space-y-4 border-l-2 border-border pl-4">
            {HISTORY.map((entry) => (
              <li key={entry.year} className="relative">
                <span
                  aria-hidden
                  className="absolute -left-[1.4rem] top-1.5 size-2.5 rounded-full bg-accent"
                />
                <p className="text-sm font-semibold text-accent">{entry.year}</p>
                <h3 className="font-semibold">{entry.title}</h3>
                <p className="text-fg-muted">{entry.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section aria-labelledby="purpose-heading" className={SECTION}>
          <h2 id="purpose-heading" className={HEADING}>
            Why bring it back?
          </h2>
          <blockquote className="mt-3 border-l-4 border-accent pl-4 text-lg italic text-fg-muted">
            Everyone should be able to communicate, whether they have a smartphone, an internet
            connection, or just a basic mobile phone.
          </blockquote>
          <ul className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {PURPOSE.map(({ title, body, Icon }) => (
              <li key={title} className="rounded-panel border border-border bg-surface p-4 bevel">
                <Icon aria-hidden className="mb-2 size-6 text-accent" />
                <h3 className="font-semibold">{title}</h3>
                <p className="mt-1 text-sm text-fg-muted">{body}</p>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="honest-heading" className={SECTION}>
          <div className="rounded-panel border border-border bg-surface-raised p-5 bevel">
            <h2 id="honest-heading" className="text-xl font-bold">
              Honest ghost disclosure
            </h2>
            <p className="mt-2 text-fg-muted">
              Right now SMS runs in simulation mode. No real text messages are sent, nothing costs
              money, and every simulated message is labelled SIMULATED. Real sending is built but
              needs an operator to switch it on deliberately.
            </p>
          </div>
        </section>

        <section aria-labelledby="cta-heading" className={cn(SECTION, "text-center")}>
          <h2 id="cta-heading" className={HEADING}>
            Ready to be haunted by friends again?
          </h2>
          <div className="mt-5 flex flex-wrap justify-center gap-3">
            <Link to={paths.register} className={buttonVariants()}>
              Create an account
            </Link>
            <Link to={paths.signIn} className={buttonVariants({ variant: "secondary" })}>
              Sign in
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-border">
        <p className="mx-auto max-w-5xl px-4 py-6 text-center text-xs text-fg-muted">
          Independent, Chikka-inspired project. Not an official relaunch and not affiliated with or
          endorsed by the original service, its owners or any carrier. Chikka names and trademarks
          belong to their respective owners.
        </p>
      </footer>
    </div>
  );
}
