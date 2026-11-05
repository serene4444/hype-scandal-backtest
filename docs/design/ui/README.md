# Hype vs. Scandal: UI design

The final UI design for the frontend. Each screen is a static HTML page: open any file in a browser and use the top navigation to move between screens. Numbers in brackets such as `[$ X]` are placeholders, and chart lines are sketches, not data.

These pages are a visual reference for building the React app in `/frontend`, not production code.

## Screens

| # | Screen | File | Requirements |
| --- | --- | --- | --- |
| 0 | Style guide | [style-guide.html](style-guide.html) | All |
| 1 | Welcome | [welcome.html](welcome.html) | FR1 |
| 2 | Log in | [login.html](login.html) | FR1 |
| 3 | Dashboard | [dashboard.html](dashboard.html) | FR7, FR8 |
| 4 | Run a backtest | [run-a-backtest.html](run-a-backtest.html) | FR2 |
| 5 | Results | [results.html](results.html) | FR3, FR4 |
| 6 | Strategy tournament | [strategy-tournament.html](strategy-tournament.html) | FR5 |
| 7 | ML model | [ml-model.html](ml-model.html) | FR6 |
| 8 | Settings | [settings.html](settings.html) | FR9 |
| 9 | Confirmation | [confirmation.html](confirmation.html) | FR5 |

Requirement IDs match the [design document](../design-document.md).

## Colors

| Token | Hex | Use | Contrast on background |
| --- | --- | --- | --- |
| background | `#0A0C0F` | Page | |
| panel | `#111419` | Cards, forms | |
| panel-raised | `#161A20` | Highlighted cards | |
| line | `#2A3038` | Borders, dividers | |
| control-border | `#3A414B` | Inputs, secondary buttons | |
| text | `#E6E8EB` | Main text, primary button fill | 16.0:1 |
| text-secondary | `#B4B9C0` | Supporting text | |
| text-muted | `#9BA1A9` | Labels, helper text | 7.5:1 |
| success | `#8CB8FF` | Success, info | 9.7:1 |
| error | `#FFAD70` | Errors, warnings | 10.7:1 |

Blue and orange replace green and red so color-blind users can tell success from error. Every status pairs its color with an icon and a word.

## Type

| Role | Font | Size |
| --- | --- | --- |
| Page title | Inter 500 | 34 to 44px |
| Section heading | Inter 500 | 22px |
| Body | Inter 400 | 15 to 17px |
| Numbers, tickers, tables | IBM Plex Mono 400 | 13 to 30px |
| Section labels | IBM Plex Mono 500, uppercase, 0.12em tracking | 12px |

Minimum text size is 12px.

## Shapes and spacing

- Corners: 2px on buttons, inputs, and cards.
- Buttons and inputs: at least 44px tall.
- Borders: 1px lines; 2px only for error fields and the focus ring.
- Focus ring: 2px `#8CB8FF` outline with a 3px offset.

## Chart marks

| Mark | Meaning |
| --- | --- |
| Solid white line | Your rule |
| Dashed gray line | Buy-and-hold |
| Dotted dark gray line | Monkeys |
| Up triangle | Buy |
| Down triangle | Sell |
| Hollow square | Event |

Lines differ by pattern and marks by shape, so the charts work without color.

## Accessibility checklist

- Every input has a visible label above it, with helper or error text tied to it.
- Errors appear next to the field, with an icon and plain words.
- Icon-only buttons (Settings) have an accessible name.
- Loading and success messages are announced as status updates.
- Settings include reduce motion, larger text, high contrast, and chart line patterns (on by default).
