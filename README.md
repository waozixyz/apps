# Apps

Shared application launchers and verified portable app hosting for Ziran and
Kryon applications.

`apps/launcher` exports `AppLauncherScreen`: search with a clear action,
list/grid controls, favorite grouping and scrolling. The caller retains an
`AppLauncherState`, supplies titles and favorite flags, and implements the
`AppLauncherCards` callback for the filtered catalog indices. The result
includes layout bounds for native drag/drop and guide overlays. Hosts persist
view preferences and own their account, routing, storage and installation
effects.

The callback mounts the portable screen in `ui/apps.zi` through
`apps/controller`. It provides cards, working action menus, Properties,
update/rollback confirmations and all UI translations. Catalog actions are an
explicit capability list: a host only offers actions it can handle. Every
openable app also has an Open command in its menu.

Hosts customize the same cards through the catalog's `presentation` object.
Set `hide_sizes: true` for a simple launcher that shows app names and icons
without package sizes, in either list or grid mode. The native host exposes
the same option as `AppPresentation.hide_sizes`. The default keeps sizes
visible for apps not yet on the device. Installed apps never show a download
size; download progress remains visible in either presentation.

`AppPresentation.cover_grid` selects large, clickable title-screen artwork,
logos, and visible app titles in a responsive grid. There are no separate
launch buttons.
`image_class` applies the host's standard Image styles, including rounded
corners. The shared controller owns scrolling, menus and download dialogs;
hosts supply the same verified cover assets already used by the carousel.
Collections may declare `"presentation": {"mode": "covers"}` in their signed
catalog so every supported host presents the same dark cover library.
Each child's optional `bytes` value supplies its exact initial download size.

A card for an app not on the device shows a download symbol. It opens a
dialog with the package size and what the app may reach, and the dialog's
Download is the person's consent; it then follows the download to Open, or
to Try again when it failed. Hosts describe this per card with
`permissions` (`account`, `friends`, `audio`, `media`), `progress` (percent
while `downloading`) and `download_failed`.

A collection may declare children it does not pack, such as Arcade's games,
which are downloaded one by one. `AppPlatform.download` gives such a card's
state, `AppPlatform.fetch` installs or removes it without opening it, and
`AppPlatform.bundle` returns its downloaded bytes, which the host checks
against the catalog digest before every open.

An add-on declares its sibling `dependencies` in the same signed catalog.
Installation lists every missing package and its total size, and skips
dependencies already on the device. Read-only `resources` links reuse explicit
asset paths from those verified packages. Missing dependencies, cycles,
altered payloads and paths outside the declared app namespaces are rejected.
An add-on with `shared_code: true` also links its declared dependencies as
portable code libraries. Build it with Ziran's `--library` option against
those exact payloads; the base package uses `--retain` for additional entry
points the add-on needs. Verification happens on the preparation worker,
before guest code runs. Each instance keeps its own mutable state. Libraries'
assets remain behind the same explicit resource links, and their bytes count
toward the collection's memory limit.

A base app may export a few flat saved-record names in `shared_records`.
Only a direct, verified dependent in that signed catalog may read them through
`apps.records` with `{"operation":"get","app":"BASE_ID","record":"NAME"}`.
The reply contains `status` (`done`, `missing`, `rejected` or `unavailable`)
and `text` for a successful read. The host keeps the current account and
authority, applies its ordinary storage policy and bounds replies to 64 KiB.
This grants no writes, no undeclared records and no access through a mere
dependency declaration. Code libraries still keep independent mutable state.

Inbe and Werkzeug use this same exported launcher and portable controller.
App-specific title/account bars and navigation docks remain with their hosts.
Build the controller with the host's compiler and Kryon graph, review its
digest, and pin those exact bytes in the host. A mismatched controller must
fail validation; never substitute another screen silently.

`scripts/build-ui.py` builds the standalone package controller. The native
fixture exercises real card/menu/dialog behavior; the external-consumer test
verifies public package imports and launcher search/grouping.
