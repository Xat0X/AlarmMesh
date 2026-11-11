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
