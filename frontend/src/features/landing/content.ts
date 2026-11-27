import { Bot, Globe, MessageCircle, ShieldCheck, Smartphone, Users, type LucideIcon } from "lucide-react";

export interface TimelineEntry {
  year: string;
  title: string;
  body: string;
}

/** Facts: Chikka release and carrier connections per public sources; closure announced for March 2018. */
export const HISTORY: readonly TimelineEntry[] = [
  {
    year: "2000",
    title: "A messenger for people with and without computers",
    body: "Chikka Philippines releases Chikka Text Messenger. You type on a computer. Your friend reads it as a text on an ordinary mobile phone.",
  },
  {
    year: "2001 to 2004",
    title: "The networks plug in",
    body: "Connections to Smart (2001), Globe (2002) and Sun Cellular (2004) put the service within reach of most Filipino phone users.",
  },
  {
    year: "The boom years",
    title: "Everybody had a buddy list",
    body: "Students, families and overseas workers used it to stay in touch cheaply. Replying by text from a basic phone just worked.",
  },
  {
    year: "2018",
    title: "The lights go out",
    body: "Smartphones and chat apps took over, and the service announced it would close. A lot of people lost a small piece of their youth.",
  },
  {
    year: "2026",
    title: "Something stirs",
    body: "Chikka Reborn is built for Kiroween 2026, in the Resurrection category. Same idea, new body, honest about what it can and cannot do.",
  },
];

export interface PurposeEntry {
  title: string;
  body: string;
  Icon: LucideIcon;
}

export const PURPOSE: readonly PurposeEntry[] = [
  {
    title: "Reach a basic phone from a browser",
    body: "Send a message from the web. The other person reads it as an ordinary text. No app, no data plan, no smartphone.",
    Icon: Smartphone,
  },
  {
    title: "Let SMS users answer back",
    body: "Replies from a basic phone land in the same conversation as your chat messages.",
    Icon: MessageCircle,
  },
  {
    title: "Buddy list and instant chat",
    body: "Add friends by username, see who is around, and chat in real time with other Chikka users.",
    Icon: Users,
  },
  {
    title: "Country-aware, not country-blind",
    body: "Text messaging works differently in each country. We show what is supported before you send, and never promise free or universal two-way SMS.",
    Icon: Globe,
  },
  {
    title: "An assistant that only suggests",
    body: "Smart replies, translation and tone help are drafts. Nothing is ever sent until you press send.",
    Icon: Bot,
  },
  {
    title: "Honest delivery status",
    body: "Accepted is not delivered. We only say delivered when the network confirms it, and we label simulated messages SIMULATED.",
    Icon: ShieldCheck,
  },
];
