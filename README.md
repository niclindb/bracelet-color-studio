# Bracelet Color Studio

A small Flask web app for recoloring friendship bracelet patterns from [braceletbook.com](https://www.braceletbook.com/). Load a pattern by its design number, change any of its colors, and try generated palettes to see how the bracelet looks before you pick your floss.

**Live app:** https://bracelet-color-studio-lindberg-dev-projects.vercel.app/

## Features

- **Load any normal pattern by number.** Enter a braceletbook.com design number and the app fetches its pattern and preview SVGs, with the watermark text removed.
- **Pattern editor.** Each color in the pattern gets a card with a color picker and a hex field. Changes update the knot diagram and the bracelet preview live.
- **Drag to swap colors.** Drag one color card onto another to swap their positions in the pattern. Dragging works with mouse and touch.
- **Smart Palette.** Opens a palette generator sized to the number of colors in the current pattern. Pick or type a base color, or hit **Shuffle** for a random one, and the app builds palettes from it in five groups:
  - **Harmony:** Analogous, Complementary, Split-Complementary, Triadic, Tetradic / Square, Double Split-Complementary
  - **Tone & Lightness:** Monochromatic, Tinted (toward white), Shadowed (toward black)
  - **Temperature:** Warm, Cool, Warm–Cool Split
  - **Gradient** (anchored to your color): Sunset, Ocean, Forest, Fire
  - **Perceptual:** Balanced LCH, High Contrast, Pastel, Jewel Tones, Earthy / Natural

  Filter tabs show one group at a time. Click a swatch to copy its hex code, or click **Apply →** to send that palette back to the pattern editor.
- **DMC floss matching.** Turn on **Use DMC colors only** to snap every generated color to the nearest of the 454 DMC embroidery floss colors in `dmc_dict.py`. When an applied color is a DMC color, the editor shows its DMC floss number next to the color.

## Setup

You need Python 3 and internet access, since patterns are fetched from braceletbook.com and the palette page loads [chroma.js](https://gka.github.io/chroma.js/) from a CDN.

```bash
git clone https://github.com/niclindb/bracelet-color-studio.git
cd bracelet-color-studio
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running

```bash
flask --app app run
```

Then open http://127.0.0.1:5000. Running `python app.py` also works.

To run the tests:

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Usage

1. Open the [live app](https://bracelet-color-studio-lindberg-dev-projects.vercel.app/) (or your local server). On the home page, enter a design number (for example `1024`) and click **Initialize Design**.
2. In the **Pattern Editor**, change colors with the pickers or hex fields. Drag cards, or use the ◀ ▶ buttons, to rearrange colors. Each card shows the matching DMC floss number, or the closest one (≈). The URL updates as you edit, and **Copy Link** copies it.
3. Click **Smart Palette** to generate palettes. It starts from a random base color; pick your own or hit **Shuffle**. Each palette is shown on your bracelet. Optionally turn on **Use DMC colors only**, and click **Apply →** on a palette you like.
4. You land back in the editor with that palette applied. The URL keeps the colors (`/design/<number>?hex_codes=...`), so you can bookmark or share it.
5. Click **Change Design** in the editor to go back and load a different pattern.

## Routes

| Route | Method | What it does |
| --- | --- | --- |
| `/` | GET | Home page with the design number form |
| `/submit-design` | POST | Redirects to `/design/<design_number>` |
| `/design/<design_number>` | GET | Pattern editor. Optional `hex_codes` query (comma-separated hex without `#`) presets the colors in order |
| `/design/<design_number>/palette` | GET | Smart Palette page. `n` sets the number of colors; `hex_codes` carries the editor's current colors for the Back link |
| `/generate-colors/<num_colors>` | GET, POST | Old Smart Palette URL; redirects to the new one |

## Project structure

```
app.py                 Flask routes and the braceletbook.com SVG fetching
dmc_dict.py            Hex → DMC floss number lookup table
requirements.txt       Python dependencies (pinned)
requirements-dev.txt   Adds pytest for running tests
tests/                 Route tests (braceletbook.com is mocked)
templates/index.html   Home page
templates/design.html  Pattern editor
templates/colors.html  Smart Palette generator
static/favicon.png     Favicon
```

## Notes

- Patterns and artwork belong to braceletbook.com and their authors. This app only fetches them for personal recoloring.
- If a design number can't be loaded, the home page shows an error. Only "normal" patterns are supported.
- The palette generator was inspired by [Muzli Colors](https://colors.muz.li/).
