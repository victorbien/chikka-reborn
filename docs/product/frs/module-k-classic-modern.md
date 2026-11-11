# Module K — Classic and Modern Experience (`CLASSIC`)

Part of the [Functional Requirements Specification](../functional-requirements.md). Classic Mode is an independent, Chikka-inspired design; it must not reuse licensed logos, assets or trademarks without permission, and must say it is unofficial. Both modes share the same data, features and business logic; they differ in layout, theme and wording only. Safety labels (SIMULATED, SMS, AI-assisted, delivery status) are mandatory in both modes and cannot be themed away.

---

### FR-CLASSIC-001 — Mode Toggle

| Field | Detail |
|---|---|
| Module | K — Experience |
| User role | User |
| Priority / Phase | POST-MVP / 5 |
| Mode | Not provider-dependent |
| Description | Users switch between Classic and Modern modes. |
| Preconditions | Signed in. |
| Trigger | User selects a mode in Settings or the header menu. |
| Main workflow | 1) The user picks Classic or Modern. 2) The UI switches without a reload and without losing the current conversation or draft. 3) The choice is saved (FR-CLASSIC-006). |
| Alternative workflows | A) First-time users choose in onboarding (FR-AUTH-015). B) Keyboard shortcut for switching (optional). |
| Expected result | The same features in the chosen style. |
| Error scenarios | Save failure: the mode applies for the session with a retry notice. |
| Dependencies | FR-CLASSIC-002, FR-CLASSIC-003, FR-CLASSIC-006. |
| Acceptance criteria | AC1 Every MVP feature works in both modes. AC2 Switching keeps drafts and scroll position. AC3 The toggle is keyboard accessible and labelled. |

### FR-CLASSIC-002 — Classic Mode

| Field | Detail |
|---|---|
| Module | K — Experience |
| User role | User |
| Priority / Phase | POST-MVP / 5 |
| Mode | Not provider-dependent |
| Description | A nostalgic buddy-list interface that evokes the original service. |
| Preconditions | User chose Classic. |
| Trigger | Mode applied. |
| Main workflow | 1) A narrow buddy-list window with grouped contacts, presence icons, and status message. 2) Chat windows as panels with the classic timestamp format. 3) Original-inspired but newly created palette, typography and icons. 4) Classic wording for features where it does not obscure meaning. 5) Credits, SMS and settings are reachable from a menu bar. |
| Alternative workflows | A) Narrow screens: the buddy list and chat stack as views with a back control. |
| Expected result | A recognisable, affectionate homage that still works well. |
| Error scenarios | Missing asset: falls back to the Modern style for that element. |
| Dependencies | shadcn/ui theme tokens, FR-CLASSIC-007. |
| Acceptance criteria | AC1 No third-party trademarks or copied assets are used. AC2 An "independent, inspired project" notice appears in About. AC3 SIMULATED, SMS and status labels remain visible. AC4 Meets WCAG 2.1 AA. |

### FR-CLASSIC-003 — Modern Mode (Default)

| Field | Detail |
|---|---|
| Module | K — Experience |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | The default interface with a split-panel layout. |
| Preconditions | None. |
| Trigger | Default for all new users. |
| Main workflow | 1) Desktop: conversations and contacts at left, active conversation at right, optional details panel. 2) Mobile: single-column navigation with a bottom bar. 3) Built with shadcn/ui and Tailwind. |
| Alternative workflows | A) Collapsible side panels. |
| Expected result | A clean, familiar messaging experience. |
| Error scenarios | Not applicable. |
| Dependencies | FR-CLASSIC-005. |
| Acceptance criteria | AC1 It is the default until a user chooses otherwise. AC2 Fully usable from 320 px width. AC3 All four data states (loading, empty, error, success) implemented. |

### FR-CLASSIC-004 — Theme Switching

| Field | Detail |
|---|---|
| Module | K — Experience |
| User role | User |
| Priority / Phase | POST-MVP / 5 |
| Mode | Not provider-dependent |
| Description | Users choose light, dark or system theme for Modern Mode, and the Classic palette variants. |
| Preconditions | None. |
| Trigger | Theme control selected. |
| Main workflow | 1) Options: System (default), Light, Dark. 2) The theme applies instantly using CSS variables. 3) Classic Mode offers its own palette (classic blue; optional high-contrast). 4) The choice is saved. |
| Alternative workflows | A) System preference changes while "System" is selected: the app follows. |
| Expected result | Comfortable viewing. |
| Error scenarios | Not applicable. |
| Dependencies | FR-CLASSIC-006. |
| Acceptance criteria | AC1 Text contrast is at least 4.5:1 in every theme. AC2 No flash of the wrong theme on load. AC3 Status and warning labels are legible in every theme. |

### FR-CLASSIC-005 — Responsive Layouts

| Field | Detail |
|---|---|
| Module | K — Experience |
| User role | User |
| Priority / Phase | MVP / 1 |
| Mode | Not provider-dependent |
| Description | Both modes adapt to phone, tablet and desktop. |
| Preconditions | None. |
| Trigger | Viewport changes. |
| Main workflow | 1) Breakpoints: under 640 px single column, 640 to 1024 px two columns, above 1024 px three-pane where applicable. 2) Touch targets are at least 44 px. 3) The compose area stays visible with the on-screen keyboard. |
| Alternative workflows | A) Landscape phones use the two-column layout. |
| Expected result | Consistent usability on any device, including low-cost phones. |
| Error scenarios | Not applicable. |
| Dependencies | Tailwind breakpoints. |
| Acceptance criteria | AC1 No horizontal scrolling at 320 px. AC2 Verified in Playwright at three viewport sizes. AC3 Layouts respect reduced-motion preferences. |

### FR-CLASSIC-006 — Preference Persistence

| Field | Detail |
|---|---|
| Module | K — Experience |
| User role | User |
| Priority / Phase | MVP / 1 (mode and theme values added in Phase 5) |
| Mode | Not provider-dependent |
| Description | Mode, theme, language and display options persist across sessions and devices. |
| Preconditions | Signed in. |
| Trigger | User changes a display preference. |
| Main workflow | 1) The preference is saved to the profile. 2) It is cached locally for fast start-up and to avoid flashes. 3) On sign-in, the server value wins. |
| Alternative workflows | A) Signed-out visitors use a local-only preference. |
| Expected result | The interface looks the same wherever the user signs in. |
| Error scenarios | Server save failure: local value kept, retried later. |
| Dependencies | FR-AUTH-007. |
| Acceptance criteria | AC1 Preferences persist after logout and login. AC2 Server value overrides stale local values. AC3 Invalid stored values fall back to defaults. |

### FR-CLASSIC-007 — Accessibility Parity

| Field | Detail |
|---|---|
| Module | K — Experience |
| User role | User |
| Priority / Phase | POST-MVP / 5 |
| Mode | Not provider-dependent |
| Description | Classic Mode meets the same accessibility standard as Modern Mode. |
| Preconditions | None. |
| Trigger | Any Classic Mode screen. |
| Main workflow | 1) Semantic structure, labels, keyboard navigation and focus order are verified. 2) Icons have text alternatives. 3) Retro visuals do not reduce contrast or font size below limits. 4) Text can be resized to 200 percent. |
| Alternative workflows | A) A high-contrast Classic palette is available. |
| Expected result | Nostalgia without exclusion. |
| Error scenarios | Not applicable. |
| Dependencies | FR-CLASSIC-002. |
| Acceptance criteria | AC1 Automated accessibility checks pass for key screens in both modes. AC2 Manual keyboard walkthrough passes. AC3 Full WCAG conformance still requires expert manual testing with assistive technologies. |
