# AlarmMesh branding

The SVG and PNG files in this directory are the user-supplied artwork,
preserved byte for byte. These replace the earlier generated design concepts.

- `alarmmesh-icon.svg` and the square PNG exports: application/integration icon.
- `alarmmesh-favicon.svg` and its small PNG exports: simplified favicon.
- `alarmmesh-logo-light.*`: dark lettering for light backgrounds.
- `alarmmesh-logo-dark.*`: white lettering for dark backgrounds.

## Home Assistant assets

`custom_components/alarmmesh/brand/` contains the packaged images:

| File | Source | Size |
| --- | --- | --- |
| `icon.png` | icon-256 PNG, unchanged | 256 x 256 |
| `icon@2x.png` | icon-512 PNG, unchanged | 512 x 512 |
| `logo.png` / `logo@2x.png` | light logo PNG | height 256 / 512 |
| `dark_logo.png` / `dark_logo@2x.png` | dark logo PNG | height 256 / 512 |

Only the packaged logos have their transparent outer margin trimmed and are
resized proportionally with Lanczos sampling. The artwork and wording remain
unchanged. The same icon works on both backgrounds, so no duplicate dark icon
is needed. Favicons are retained for future web use; no frontend is added.

Home Assistant supports local brand images since 2026.3:
https://contributors.home-assistant.io/core/integrations/brands/

The supplied tagline describes the brand direction. The current integration
still provides read-only smoke and source-availability summaries; these images
do not add alarm interconnection, siren control, or notifications.

Adding these files locally does not update an existing Home Assistant install.
Delivery through an integration update and verification in its UI remain separate.

## Reproduction and review (2026-11-12)

No original SVG/PNG or packaged image was changed for this review. The two icons
are byte-identical copies of `alarmmesh-icon-256.png` and `alarmmesh-icon-512.png`.
Both original logo PNGs are 2080 x 520 RGBA. Their alpha bounding box is
`(40, 40, 1771, 480)`. For each theme, crop to that box, resize the crop with
Lanczos to height 256 or 512, and round the proportional width. This yields
1007 x 256 and 2014 x 512. An in-memory Pillow reproduction matched every
packaged logo pixel; the originals remain the source of truth.

Equivalent recipe, using Pillow already present in the existing HA development
environment (illustration only; no generation is needed for a normal checkout):

```python
from PIL import Image

with Image.open("assets/branding/alarmmesh-logo-light.png") as source:
    cropped = source.crop(source.getchannel("A").getbbox())
    height = 256  # 512 for @2x; use the dark source for dark_logo variants
    width = round(cropped.width * height / cropped.height)
    packaged = cropped.resize((width, height), Image.Resampling.LANCZOS)
```

The current [official image rules](https://contributors.home-assistant.io/core/integrations/brands/)
were checked on 2026-11-12. The six filenames, dimensions, landscape proportions,
transparency and trimmed bounds pass the packaging tests. The single icon is
used on both backgrounds. README uses relative `<picture>` sources for the
supplied light/dark logos and descriptive fallback alt text; no remote image,
font or script is added.

`tests/test_branding.py` checks actual authenticated HA fixture responses against
the local PNG bytes with placeholders disabled. This proves technical serving on
the pinned baseline, not visually correct rendering in a signed-in UI. The new
light/dark HA UI inspection is **NOT PERFORMED**, because browser controls were
blocked; see [review results](../../docs/review-results.md).
