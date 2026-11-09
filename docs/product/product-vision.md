# Product Vision

**Document:** CHKR-PROD-001  
**Project:** Chikka Reborn  
**Version:** 1.0  
**Status:** Approved  
**Last Revised:** November 2026  

---

## Purpose

This document defines the enduring product vision for Chikka Reborn. It answers the question: *why does this product exist, and what world does it aim to create?* All product, design, and engineering decisions should be evaluated against this vision.

## Scope

Applies to all phases of Chikka Reborn development, from Phase 0 (Foundation) through Phase 6 (Production Hardening) and beyond.

---

## 1. The Origin Story

Chikka was a pioneering Filipino messaging platform launched in the early 2000s. At a time when internet access was far from universal, Chikka bridged the digital divide by allowing anyone with a computer and an internet connection to send messages directly to any mobile phone via SMS — and receive replies back. The recipient did not need a smartphone. They did not need the Chikka app. They just needed a phone.

For millions of Filipinos, Chikka was how families stayed connected across provinces, how friends communicated across socioeconomic divides, and how the internet became relevant to people who had never touched a keyboard.

Chikka discontinued its service in 2018.

This project is its resurrection.

> **Disclaimer:** Chikka Reborn is an independent, Chikka-inspired project. It is not an official continuation of the original Chikka service. It is not affiliated with, endorsed by, or licensed by the original owners or their telecom partners. All branding, design, and assets are original unless confirmed written permission has been obtained.

---

## 2. The Problem We Solve

### 2.1 The Communication Gap Persists

Despite smartphone proliferation, significant communication barriers remain in 2026:

- An estimated 1.8 billion people globally still use feature phones or basic SMS-capable handsets.
- Internet connectivity in rural and lower-income regions of Southeast Asia, Africa, and Latin America remains inconsistent and expensive.
- Existing messaging platforms — WhatsApp, Messenger, iMessage, Telegram — require both parties to have the same app and an internet connection.
- No mainstream platform today allows an internet user to seamlessly reach a mobile-only user without that user installing anything.

### 2.2 The Filipino Diaspora Dimension

The Philippines is one of the world's largest sources of overseas workers. Filipino diaspora communities span every continent. Communication between overseas workers and family members back home — many of whom rely on basic mobile phones — remains a daily challenge. The original Chikka addressed exactly this need. No equivalent solution has emerged since its closure.

### 2.3 Language and AI Barriers

Cross-border and cross-generational communication is complicated by language. Older relatives may not be fluent in English. Younger migrants may struggle with formal Filipino. AI-assisted translation and composition can reduce these friction points — but no existing platform integrates these tools with SMS reach.

---

## 3. The Vision Statement

> **"Everyone should be able to communicate, whether they have a smartphone, an internet connection, or just a basic mobile phone."**

Chikka Reborn is the platform that makes this true. It connects the connected with the not-yet-connected. It makes SMS accessible from a web browser. It makes the internet accessible from a basic handset. It uses AI to make communication easier across languages, tones, and contexts.

---

## 4. What We Are Building

Chikka Reborn is a **modern, globally accessible messaging platform** that combines:

1. **Internet-to-SMS messaging** — send a message from a browser to any mobile phone number, anywhere in the world.
2. **SMS-to-Internet messaging** — basic phone users reply via SMS; their replies appear in the platform in real time.
3. **Real-time Chikka-to-Chikka messaging** — instant messaging between registered platform users, delivered over WebSocket.
4. **AI-assisted communication** — smart replies, translation, rewriting, tone adjustment, summarisation, and SMS length optimisation, all requiring explicit user approval before sending.
5. **Multilingual communication** — the platform supports communication across languages through AI-powered translation.
6. **International SMS reach** — country-aware SMS capability, with honest display of what is and is not supported in each country.
7. **Classic and Modern interfaces** — a nostalgic interface that honours the original Chikka experience, and a contemporary chat interface for modern users.

---

## 5. What We Are Not Building

The following are explicitly out of scope — permanently or for the current version:

| Item | Status |
|---|---|
| Voice or video calling | Out of scope (this version) |
| Native iOS / Android apps | Out of scope (this version) |
| Group SMS / MMS | Out of scope (this version) |
| End-to-end SMS encryption | Permanently out of scope (SMS is unencrypted at the carrier level) |
| AI auto-sending without user approval | **Permanently prohibited** |
| Social features (public feeds, reactions) | Out of scope (this version) |
| Official Chikka branding or licensing | Pending — requires IP confirmation |

---

## 6. Core Design Principles

These principles guide every product, design, and technical decision:

### Honesty First
The platform never misrepresents capability. If a country does not support two-way SMS, the UI says so. If a message is simulated, it is labelled as simulated. If AI generated content, it is badged before sending. No capability is implied that does not exist.

### Accessibility for All
The platform is usable by people with basic phones, low-bandwidth connections, screen readers, and limited digital literacy. WCAG 2.1 AA compliance is a baseline requirement, not a bonus.

### AI as Assistant, Never Actor
The AI assistant exists to help users communicate better. It never sends a message on its own. Every transmission requires a deliberate human act. This is not a feature flag — it is a permanent architectural constraint.

### Nostalgic Authenticity
Classic Mode pays homage to the original Chikka experience through original-inspired design. It does not reproduce licensed assets or imply official affiliation. It captures the spirit.

### SMS Integrity
The platform never reports a message as delivered unless the provider has confirmed handset delivery. It never silently falls back from live SMS to simulation. It never sends real SMS without explicit operator confirmation.

---

## 7. Strategic Context

This project is submitted to **Kiroween 2026** under the **RESURRECTION** category.

The Kiroween RESURRECTION category challenges builders to revive something that was lost — a technology, a platform, a capability — and reimagine it for today. Chikka Reborn is that: a direct, faithful resurrection of the original Chikka concept, rebuilt on modern infrastructure with AI enhancement and global reach.

---

## 8. Success Definition

Chikka Reborn succeeds when:

1. An internet user in Toronto can send a message to a basic phone user in Pampanga, and the recipient can reply back — all through Chikka Reborn.
2. A Filipino grandmother without a smartphone receives a message from her grandchild abroad and can respond with a standard SMS.
3. A user who never spoke the recipient's language can compose a translated message with AI assistance, review it, approve it, and send it — in under 60 seconds.
4. An administrator can switch the platform from simulation mode to live SMS mode through a single, human-approved configuration change.
5. Every message status shown to a user reflects reality.

---

## 9. Revision History

| Version | Date | Author | Notes |
|---|---|---|---|
| 1.0 | November 2026 | Kiro (Principal Architect) | Initial approved vision |
