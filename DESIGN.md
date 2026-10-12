---
name: Ticket Hygiene
description: The notifier's live traffic, seen as light through frosted glass.
colors:
  ok: "#3dd6c3"
  wait: "#f2a541"
  alert: "#ff4d5e"
  alert-ink: "#ff8a95"
  on-alert: "#1a0508"
  on-ok: "#04201c"
  clean: "#eaf0ff"
  ground: "#0b1020"
  ground-deep: "#070b17"
  glass: "rgba(26, 34, 54, 0.44)"
  glass-strong: "rgba(28, 37, 60, 0.72)"
  glass-hover: "rgba(40, 51, 80, 0.5)"
  edge: "rgba(234, 240, 255, 0.09)"
  edge-strong: "rgba(234, 240, 255, 0.18)"
  ink: "#eaf0ff"
  ink-2: "#c9d2ea"
  ink-3: "#9aa6c4"
  ink-4: "#7d89ab"
  ok-day: "#0c9484"
  wait-day: "#b86e06"
  alert-day: "#e0253a"
  alert-ink-day: "#c41d31"
  on-alert-day: "#ffffff"
  clean-day: "#6a7899"
  ground-day: "#eef1f6"
  ground-deep-day: "#e2e7f0"
  glass-day: "rgba(255, 255, 255, 0.56)"
  glass-strong-day: "rgba(255, 255, 255, 0.82)"
  glass-hover-day: "rgba(255, 255, 255, 0.75)"
  edge-day: "rgba(18, 24, 38, 0.09)"
  edge-strong-day: "rgba(18, 24, 38, 0.18)"
  ink-day: "#121826"
  ink-2-day: "#2b3550"
  ink-3-day: "#46536f"
  ink-4-day: "#5a6684"
typography:
  display:
    fontFamily: "Red Hat Text Variable, system-ui, sans-serif"
    fontSize: "34px"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.03em"
  headline:
    fontFamily: "Red Hat Text Variable, system-ui, sans-serif"
    fontSize: "26px"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.02em"
  title:
    fontFamily: "Red Hat Text Variable, system-ui, sans-serif"
    fontSize: "17px"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "-0.01em"
  title-pane:
    fontFamily: "Red Hat Text Variable, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.5
  body:
    fontFamily: "Red Hat Text Variable, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  body-sm:
    fontFamily: "Red Hat Text Variable, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Red Hat Text Variable, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.5
  label-rail:
    fontFamily: "Red Hat Text Variable, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 500
    lineHeight: 1.5
  data:
    fontFamily: "Red Hat Mono Variable, ui-monospace, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "\"tnum\" 1"
rounded:
  pane: "18px"
  inset: "14px"
  control: "12px"
  compact: "10px"
  tag: "6px"
  pill: "16px"
spacing:
  gutter: "32px"
  gutter-sm: "16px"
  page-top: "24px"
  page-bottom: "48px"
  pane-gap: "20px"
  pane-y: "20px"
  pane-x: "22px"
  row-y: "12px"
  control-gap: "8px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    rounded: "{rounded.control}"
    padding: "0 18px"
    height: "40px"
  button-glass:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 18px"
    height: "40px"
  button-glass-hover:
    backgroundColor: "{colors.glass-hover}"
    textColor: "{colors.ink}"
  button-verdict-correct-pressed:
    backgroundColor: "{colors.ok}"
    textColor: "{colors.on-ok}"
    rounded: "{rounded.control}"
    height: "40px"
  button-verdict-false-alarm-pressed:
    backgroundColor: "{colors.alert}"
    textColor: "{colors.on-alert}"
    rounded: "{rounded.control}"
    height: "40px"
  icon-button:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.compact}"
    padding: "0 10px"
    height: "34px"
  select:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.compact}"
    padding: "0 32px 0 12px"
    height: "34px"
  chip:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.ink-3}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.pill}"
    padding: "0 12px"
    height: "32px"
  chip-selected:
    textColor: "{colors.ink}"
  input:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "10px 14px"
  pane:
    backgroundColor: "{colors.glass}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pane}"
    padding: "20px 22px"
  tooltip:
    backgroundColor: "{colors.glass-strong}"
    textColor: "{colors.ink}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.control}"
    padding: "12px 14px"
    width: "300px"
  rail-item:
    textColor: "{colors.ink-3}"
    typography: "{typography.label-rail}"
    rounded: "{rounded.control}"
    padding: "9px 0 7px"
    width: "60px"
  rail-item-active:
    textColor: "{colors.ink}"
  count-badge:
    backgroundColor: "{colors.alert}"
    textColor: "{colors.on-alert}"
    rounded: "9px"
    padding: "0 5px"
    height: "18px"
---

# Design System: Ticket Hygiene

## Overview

**Creative North Star: "Long Exposure"**

Night-shift city light trails seen through frosted glass. The notifier's real traffic (every check, every alert from the last hour) moves behind the interface as light: a passing light per check, a red tail-light streak per alert. The glass exists because something real moves behind it; panes blur a defocused field drawn from the same live data as the river, so the background is never decoration.

The system is a working monitor, not a showcase. Density is moderate: a 76px rail, a 64px header, a 236px river, then glass panes, lists and tables in 13-14px type. One family, Red Hat Text, carries everything; its mono cut appears only for data. Night (dark) and day haze (light) share every token name; only the values change, and the day theme dims the glow rather than removing it.

Colour is spent on state, never on chrome. The interface itself is ink on glass; the only saturated colour on screen is a light that means something.

**Key Characteristics:**
- Frosted glass panes (26px blur, 140% saturate) over a live, defocused field of the notifier's own traffic.
- Four lights carry all meaning: headlight white (clean), teal (ok, live), sodium amber (waiting, uncertain, error), tail-light red (alert).
- One typeface family; mono only for times, IDs, axis ticks, scores and key hints.
- Hairline edges instead of dividers with weight; depth from blur and a single soft drop shadow.
- Motion is the data moving: 5s linear drift, blurred arrival that settles, and nothing animates under reduced motion.

## Colors

A blue-black night (or cool grey day haze) of ink and glass, with four signal lights as the only colour.

### Primary
- **Live Teal** (ok; ok-day in light): the light of a check that passed and of the system being alive. The breathing live dot, the focus ring and caret, the "correct" verdict, the ok zone of the score bar, and the tint in the avatar and text selection.

### Secondary
- **Sodium Amber** (wait; wait-day in light): waiting, uncertain, skipped and errored checks in the traffic; the stale live dot; the "stale" health word; the warn banner.

### Tertiary
- **Tail-Light Red** (alert; alert-day in light): alerts. Streaks in the river, alert pips and lights, the unreviewed count badge, the "false alarm" verdict, the alert zone of the score bar.
- **Tail-Light Ink** (alert-ink; alert-ink-day): the readable red for text (alert counts in captions, false-alarm stamps, error lines, the "down" health word).
- **On Red** (on-alert; on-alert-day) and **On Teal** (on-ok): text set on a filled red or teal surface.

### Neutral
- **Night Ground / Day Haze** (ground, ground-deep; ground-day, ground-deep-day): the page beneath the field. ground-deep is reserved for recessed wells.
- **Frosted Glass** (glass, glass-strong, glass-hover and day equivalents): every pane, control and the rail. glass-strong is for surfaces that float over moving content (tooltip, sticky feed head); glass-hover is the hover wash on rows and buttons.
- **Hairline Edge** (edge, edge-strong and day equivalents): 1px borders and row dividers; edge-strong for hover borders, key hints and the timeline spine.
- **Ink ramp** (ink, ink-2, ink-3, ink-4 and day equivalents): ink for primary text and filled primary buttons; ink-2 for secondary body and control text; ink-3 for supporting copy and captions; ink-4 for timestamps, meta and placeholders.
- **Headlight** (clean; clean-day): the colour of a clean, unremarkable check. White at night; in day haze it drops to slate so it still reads against a pale ground.

### Named Rules
**The Tail-Light Rule.** In the traffic (river, field, feed, trace, mark) red means an alert and nothing else; errors in the traffic are amber. Outside the traffic, the red family appears only where the associate must act: an unreviewed count, a false-alarm verdict, the notifier down, a failed load.

**The Lights-Are-States Rule.** Saturated colour appears only as a signal light or the text that names it. Chrome, navigation and headings stay ink on glass; the primary button is filled with ink, not with a hue.

**The Shared-Name Rule.** Night and day define the same token names. A new surface uses tokens, never a theme-specific literal, so the switch changes every value at once.

## Typography

**Display Font:** Red Hat Text Variable (with system-ui, sans-serif)
**Body Font:** Red Hat Text Variable (with system-ui, sans-serif)
**Label/Mono Font:** Red Hat Mono Variable (with ui-monospace, monospace), tabular numerals

**Character:** One humanist sans at every level, tightened slightly with size; a mono cut of the same family appears only where a reader compares digits.

### Hierarchy
- **Display** (600, 34px, 1.15, -0.03em): the single status word in the notifier health pane ("Healthy", "Stopped"). One per screen at most.
- **Headline** (600, 26px, 1.25, -0.02em): page heads and the alert-detail title. The sign-in card uses the same treatment at 24px.
- **Title** (600, 17px, -0.01em): the product name in the header.
- **Title, pane** (600, 14px): pane and feed heads; the verdict box head goes to 15px.
- **Body** (400, 14px, 1.5): default text, inputs, quoted replies. Long reasons sit at 15px in ink-2 with a 72ch measure; quotes cap at 80ch.
- **Body, small** (400-500, 13px): rows, chips, controls, table cells, captions.
- **Label** (500, 12px): meta, table heads, fact labels, time aside; colour ink-3 or ink-4, sentence case.
- **Label, rail** (500, 11px): rail item labels and lane labels.
- **Data** (Red Hat Mono, 12px or inherited, tabular): times, ticket IDs, axis ticks, the score marker, key hints.

### Named Rules
**The One Family Rule.** Red Hat Text and its mono cut only. No second display face.

**The Mono-Is-Data Rule.** Mono is set on times, IDs, ticket numbers, axis ticks, scores and key hints, never on prose, labels or headings. Labels stay sentence case; there is no uppercase tracking anywhere in the system.

## Layout

A fixed glass rail (76px) on the left, a sticky 64px header with the scope controls, then content on a 32px gutter. The Live view runs a full-width 236px river (one lane per theme check, a 150px label column, an hour of time) and below it a three-pane grid (1.3fr / 1fr / 0.8fr, 20px gaps) followed by a full-width feed with a sticky glass head that docks under the header. Pages pad 24px top, 32px sides, 48px bottom, with a 1560px max width. Alert detail is a two-column grid (1.35fr content, 0.65fr sticky verdict box, minimum 320px).

Rhythm is built from 8, 12, 14, 20 and 32: 12px vertical padding on list rows, 20px by 22px inside panes, 8px between chips and control groups. Lists separate rows with hairlines, not gaps.

At 1180px the panes fall to two columns (the last spans both), the detail grid stacks and the verdict box un-sticks, and facts go to two columns. At 760px the rail becomes a 64px bottom bar, the gutter drops to 16px, the header hides the product name and secondary controls, river lane labels hide, panes stack, and feed rows reflow into a time/pip/rule line above a two-line summary.

## Elevation & Depth

Depth comes from blur first and shadow second. Every raised surface is translucent glass with a backdrop blur, so its depth is read through the defocused lights behind it; one soft, long, low drop shadow lifts panes off the field. The day theme keeps the same structure with a lighter, bluer shadow and glow scaled to 0.55. Status lights carry their own glow (a coloured halo scaled by the theme's glow factor), which is the system's only other shadow use.

### Shadow Vocabulary
- **Pane lift, night** (`box-shadow: 0 24px 48px -24px rgba(0, 0, 0, 0.7)`): glass panes, tooltips.
- **Pane lift, day** (`box-shadow: 0 24px 48px -28px rgba(30, 40, 70, 0.35)`): the same role in day haze.
- **Light halo** (`box-shadow: 0 0 10px <signal colour>`, multiplied by the glow factor): live dots, pips, feed and trace markers.
- **Score marker ring** (`box-shadow: 0 0 0 5px ink at 18%, 0 0 18px ink`): the probability marker on the score bar.

### Named Rules
**The Something-Behind-The-Glass Rule.** Glass is only used over the live field. If a surface has nothing moving behind it, it does not need more blur; the field supplies the reason for the material.

**The Blur Ladder Rule.** Panes blur 26px (with 140% saturate), the rail 22px, tooltips and the sticky feed head 20px, the header 18px over a 55% ground wash.

## Shapes

Soft, consistent rounding that shrinks with size: panes 18px, inset wells (quotes, banners) 14px, buttons, inputs, tooltips and rail items 12px, selects, icon buttons and hover rows 10px, tags 6px, key hints 5px. Chips and the theme switch are half-height pills. Lights, dots, pips, avatars and the switch knob are circles; streaks and trails are rounded bars that fade from transparent into their colour, as an exposure would. Borders are always 1px hairlines; the focus ring is 2px teal, offset 2px, 8px radius.

## Components

### Buttons
Quiet glass by default; colour only when a button records a verdict.
- **Shape:** gently rounded (12px), 40px tall, 18px side padding, weight 600, icon gap 8px.
- **Primary:** ink fill with ground-coloured text and no border; hover mixes 12% teal into the ink. Used once per surface (sign in).
- **Glass (default):** glass fill, edge-strong border, ink text; hover to glass-hover; active nudges down 1px; disabled at 50% opacity.
- **Verdict pair:** "Correct" and "False alarm" sit as equal glass buttons until pressed, then fill teal (with on-ok text) or red (with on-alert text). Each carries its key hint.
- **Icon button:** 34px glass square or short pill (10px radius), ink-2 icon, hover to ink with edge-strong border.

### Chips
- **Style:** 32px glass pills, 1px edge border, ink-3 13px/500 text, with an optional ink-4 tabular count.
- **State:** hover lifts text to ink and the border to edge-strong; pressed fills with ink at 12% and keeps edge-strong. Used as single-select filter groups and in the feed head's "Decisions / Everything" switch.

### Cards / Containers
- **Corner Style:** 18px.
- **Background:** glass with 26px blur and 140% saturate.
- **Shadow Strategy:** pane lift (see Elevation & Depth).
- **Border:** 1px edge.
- **Internal Padding:** 20px by 22px; tables inside glass pad 6px by 10px and let cell padding (12px) do the work.

### Inputs / Fields
- **Style:** glass fill, 1px edge, 12px radius, 14px body text, 10px by 14px padding; placeholders in ink-4; teal caret.
- **Focus:** the border turns teal; no glow.
- **Search:** 38px tall with a 16px ink-4 icon inset 12px. **Select:** 34px, 10px radius, custom chevron, ink-2 text brightening to ink on hover.

### Navigation
A 76px glass rail with the mark at the top and six items (icon 19px at 1.75 stroke over an 11px label). Items are 60px wide, 12px radius, ink-3; hover to ink on glass-hover; the current page sits on ink at 10%. The Review item carries a red count badge. Below 760px the rail becomes a bottom bar of equal-width items.

### The Live River (signature)
Six hairline lanes, one per theme check, across the last hour. Each finished check is a soft radial light (12-14px, blurred 4.5px) coloured by outcome, with a 28px trail behind it; each alert is a 20px red light at the head of a 110px streak. Lights slide left on a 5s linear transition; new ones arrive from an 18px blur at 2.2x scale and settle (1.6s, cubic-bezier(0.16, 1, 0.3, 1)). Hover or focus sharpens a light to 0.5px blur at 1.5x and opens a glass tooltip; click opens its ticket. A dashed edge-strong marker shows when the notifier started.

### The Field
The same hour of traffic, defocused across the whole window behind the panes: merged bokeh discs (16-80px, 8-14px blur, 12-22% opacity, scaled by glow). The sign-in gate shows a still frame of the same field, with two far streaks.

### Trace Timeline
A 1px edge-strong spine with 15px ring markers (ground fill, 2px border in the step's signal colour, glow halo). Each step has a bold head, a mono time and ink-3 body; raw payloads open in a recessed 10px-radius mono well.

### Score Bar
A 10px track split into translucent red (0-40%), amber (40-60%) and teal (60-100%) zones, with an 18px ink marker carrying a mono percentage above it.

### Verdict Stamp
Verdicts stay on the alert as a list of lines: a 6px-radius outlined tag in teal (correct) or red ink (false alarm), the name and time. Superseded verdicts are struck through in ink-4.

## Do's and Don'ts

### Do:
- **Do** colour every light with the outcome mapping: clean for a quiet check, ok for a passed one, wait for skipped, uncertain or errored, alert for alerts only.
- **Do** put every raised surface on glass (glass, 1px edge, 18px radius for panes) over the live field.
- **Do** set times, IDs and numbers in Red Hat Mono with tabular numerals, and everything else in Red Hat Text.
- **Do** scale every glow by the theme's glow factor (1 at night, 0.55 by day) so day haze stays calm.
- **Do** guard every animation with prefers-reduced-motion; the river and field stop drifting, arrivals and shimmer stop.
- **Do** keep the primary action an ink-filled button, not a coloured one.

### Don't:
- **Don't** use red in the traffic for anything but an alert; errors in the traffic are amber.
- **Don't** place lights that don't stand for real traffic. The gate's still field is the one stand-in, because there is no data before sign-in.
- **Don't** add a second typeface or set prose, labels or headings in mono.
- **Don't** use opaque cards, heavy borders or hard shadows; depth is blur plus the one soft pane lift.
- **Don't** write a theme-specific colour literal into a component; define the token in both themes.
