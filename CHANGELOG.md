# Changelog

## [Unreleased]

- Use Mesh release APIs and package imports without changing signed release messages or cached catalog formats.

- Offer each host only node releases it can run: the publisher checks each payload's ZX revision against the ledger, the remote catalog names its revision and oldest host interface, and the node's history keeps the newest release of every format, ZX revision and interface. Publish an optional signed WebAssembly variant of a node app for web hosts.

- Validate signed package sizes against checked integer ranges instead of a universal 64 MiB limit, and verify public payloads incrementally without weakening signatures or exact digests.

- Run add-ons on Ziran's one-format ZX: an add-on imports its base's modules and carries that code in its own bundle. `shared_code` and code-library loading are removed, and catalogs that name `shared_code` are rejected. Dependencies remain for resource links and shared records, and a running base's verified bundle is still leased once. Build with Ziran 0.5.0 and Kryon b45cc524.

- Build with Ziran 0e91eb43 (program format 62) and Kryon 99c934a0 (staged swipes, correction caret and image sizing); hosts on host_api 43 load the new controller.

- Expose exact retained bundle ownership and restore verified disk-cached children only when opened, so hosts can bound resident package memory safely.

- Show console covers on a drawn scenic pattern in both orientations, without game art behind the covers.
- Select a neighbouring console cover with a click or tap; activating the selected cover downloads it in place with a progress bar.
- Show the shared artwork title with Play for covers whose action is "title".

- Add nonmodal console launch progress and host Home navigation that preserves guest saves.

- Add an artwork-led console library with orientation-specific covers and a shared painted Dew/Profile HUD.
- Open verified editor add-ons from their games, retaining save identities, normal install consent and bounded shared-library ownership.
