# Shared game HUD artwork

`profile.webp` and `dew.webp` are lossless WebP encodings of the existing
256 × 256 painted Shovey assets, with transparency preserved:

- Profile medallion: `waozixyz/games/shovey/assets/shovey/shop/profile.png`
- Dew jewel drop: `waozixyz/games/shovey/assets/shovey/shop/dew.png`

Source repository: https://github.com/waozixyz/shovey
These are reused project artwork, with no newly generated imagery.
Consumers stage these files under `assets/hud/`, or supply their own asset
paths through `AppGameHudProps.profile_image` and `dew_image`.
