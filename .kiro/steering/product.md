---
inclusion: always
---

# Product

Detailed specs: `docs/prd.md`, `docs/product/product-vision.md`, `docs/product/target-users.md`, `docs/product/user-personas.md`, `docs/product/feature-catalogue.md`, `docs/roadmap.md`.

## Purpose and Vision

Chikka Reborn is an independent, Chikka-inspired revival of the Filipino service that linked internet users with mobile phone users via SMS (discontinued 2018). It is not an official relaunch and is not affiliated with the original owners or telecom partners. Use original branding and assets only.

Vision: everyone can communicate, whether they have a smartphone, an internet connection, or only a basic mobile phone. Built for Kiroween 2026, RESURRECTION category.

## Target Audiences

- Internet users who want to reach people on basic phones.
- Basic-phone (SMS-only) users who reply and interact through the platform.
- Overseas Filipino workers and families messaging across countries.
- Nostalgic former Chikka users who want the classic experience.
- Administrators managing users, credits, and system health.

See `docs/product/user-personas.md` for personas.

## Original Chikka-Inspired Experience

- Buddy list with presence status.
- Instant chat between registered users.
- Web-to-SMS and SMS-to-web conversations in one thread.
- Classic Mode: nostalgic look and layout (Module K). Modern Mode is the default alternative.

## Modern AI-Enhanced Direction

AI assists but never acts alone: smart replies, translation, rewriting, tone adjustment, summaries, SMS length optimisation, and composition. All output is a suggestion the user approves. See `ai-guidelines.md`.

## MVP Boundaries

In scope (Phases 0-2): auth and profiles, contacts/buddy list, real-time Chikka-to-Chikka chat, internet-to-SMS and SMS-to-internet in simulation mode, delivery status tracking, country capability display.

Out of scope until later phases: AI features (3), credits/billing/admin (4), Classic Mode/i18n polish (5), production hardening (6). Live SMS requires explicit operator confirmation. Do not build ahead of the current phase. Phase list: `project-overview.md`.

## Product Principles

1. Inclusive: works for basic-phone users.
2. Honest: never claim delivery, free SMS, or universal two-way SMS without evidence.
3. User in control: no auto-send, ever.
4. Privacy first: collect and retain only what is needed.
5. Transparent costs: show segments and credit cost before sending.
6. Country-aware: capabilities differ per country, especially the Philippines.
7. Accessible and multilingual.
