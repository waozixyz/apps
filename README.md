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

A portable node/2 app may request `kryon/frame_snapshot` and call
`CaptureFrameInput` during its frame. Apps forwards that exact hosted capability
to Kryon's widget-host boundary, which returns only the snapshot published for
the active frame session; inactive and foreign-session calls fail closed.

Portable node/2 and app/1 apps can use `kryon/Media`'s `MediaAudio` for packed
asset effects and looping music. Apps recognizes the actual
`media_audio.MediaAudioHost` capability, including its package-qualified name,
through Kryon's existing widget dispatcher. Every operation requires the
platform's existing `AppSoundHost` audio permission for that verified node;
widget access or permission for legacy Media/video services grants no asset
audio. Denied calls return `Denied` with no capability bits or playback
position. Legacy Media services retain their existing dispatch and permission
policy.

The native consumer installs its provider once on its owning thread with
`MediaAudioUseRaylib()` from `kryon/media_audio_raylib`. Without a provider,
authorized calls return `Unsupported`; device/browser results retain Kryon's
`Unavailable`/`Suspended` semantics. Apps supplies each actual `HostedApp.audio`
owner and `AppHostAudioRead` to `WidgetHostAudioCall`, using the active node's
verified bundle and explicit catalog resource links. Inherited code-library
assets alone grant no audio reads. Paths cannot name host files or network
URLs; Kryon bounds each asset to 8 MiB and each owner to 16 independent voices.
The packed borrow lasts until `AppHostCollect`; providers own decoded/copied
bytes before later reuse. Nodes sharing an outer Session keep separate voices
and readers. The permission gate applies to the full MediaAudio capability,
including per-voice `Pause`/`Resume`, `Status`, and bounded PCM operations
supported by the installed provider. Capability bits 16/32/64 advertise asset
pause/resume, asset-music position, and PCM pause/resume. `Status` returns
`has_position: bool` and `position_seconds: float64`; only an available provider
playhead sets `has_position`. Paused music freezes its position. PCM has no
position or drained counter; paused streams retain their bounded copied blocks
and report `writable = false`. Guests retain scheduling and synthesis policy.

`WidgetHostEnd` only ends dispatch; music survives frames. Node retirement
revokes audio immediately, before renderer/preparation storage is collected.
`HostedAppClose` and successful `HostedAppRestart` also release voices; failed
restart preserves the working instance. Account replacement uses the existing
save/`AppHostStop`/`AppHostStart` lifecycle. If a native consumer changes an
account, resource policy, or audio authority in place, it must first call
`AppHostAudioReset(host)` on the owning thread, while owner storage is still
alive. That hook resets all live instances/controllers and revokes a decoder
already in flight; Apps cannot infer changes hidden inside platform context.
Each run also revokes voices when `AppSoundHost` permission is withdrawn.

Portable node/2 and app/1 guests may request the zero-argument bool capabilities
`app_context:DocumentStorageReadyHost` and `app_context:DocumentFlushHost`.
The platform must explicitly allow each named capability and provide
`AppPlatform.documents(context, node) -> *AppFiles`, returning only that verified
node's existing authorized private namespace (or null). Apps never derives a
path, chooses an account, initializes browser storage, or grants a permission.
Calls from an inactive instance and denied calls return false; malformed or
foreign-module calls are rejected. No guest argument can select another node.

Readiness uses Kryon's `AppFilesReady`; a successful write alone does not
acknowledge browser persistence. Flush uses `AppFilesFlush`, waits for any
previous snapshot and then a fresh acknowledged snapshot, with Kryon's
15-second browser deadline. Later writes remain pending. Browser storage must
already be hydrated on the shared `/kryon-apps` mount; staging paths outside
that mount cannot claim durability. Native writes sync bytes and parent
directories. A failed flush neither reloads memory nor retries implicitly.

The provider owns the AppFiles and must keep it alive on the owning thread
until the yielding call returns. Call `AppFilesClose` before changing its
namespace, account, or authority; never overwrite live root/lock fields. Apps
rechecks namespace generation, account epoch, active instance, permission and
provider after acknowledgement. A revoked transaction returns false even if
its backing transaction later completes. The running VM cannot be reentered,
and collection retains a busy retired runtime until its call returns.

Inbe and Werkzeug use this same exported launcher and portable controller.
App-specific title/account bars and navigation docks remain with their hosts.
Build the controller with the host's compiler and Kryon graph, review its
digest, and pin those exact bytes in the host. A mismatched controller must
fail validation; never substitute another screen silently.

`scripts/build-ui.py` builds the standalone package controller. The native
fixture exercises real card/menu/dialog behavior; the external-consumer test
verifies public package imports and launcher search/grouping.

## Unreleased

- `apps/connection` provides an origin-bound public node connection choice and
  a shared consent notice. Reading or drawing the notice starts no requests.
  Hosts keep cached apps usable offline and may revoke transfers at any time.
- `apps/remote_catalog` loads a signed collection independently of its native
  host. The host supplies the reviewed publisher key, app identity, API policy
  and minimum release sequence. Fetching requires an explicit allow call;
  signatures, compatibility, byte limits, digest and catalog shape are checked
  before the saved snapshot changes. Hosts stop the former root before
  collecting its bytes, retain per-app saves, and keep their reviewed controller.

- Align the published dependency graph on Kryon `ee9d204548295e6c6900939ba1120efe44659e79`
  and Ziran `3f6234e9a181cdad20fac4fad1d1afb1b8ccf054` (ZX27). Consumers
  must resolve the same Kryon revision for shared Session, Rectangle and Color
  values, and rebuild portable hosts and bundles together for ZX27.

- Host document readiness and acknowledged flush through explicit per-node
  private AppFiles authority. `python3 tests/document_host_test.py /path/to/libziran.a`
  runs real app/1 and node/2 guests; add `--browser-runtime /path/to/wasm/libziran.a`
  for disposable headless IDBFS persistence, hydration failure and revocation.
- Pin published Kryon asset audio and host it through Apps' existing audio
  permission, verified resources and per-instance lifetime.
- Retry separate collection art after a refused request, failed transfer or bad
  copy, one transfer at a time and waiting 1 s, doubling to 60 s, between attempts.
  `python3 tests/art_host_test.py /path/to/libziran.a` serves a real HTTP failure,
  then decodes the recovered art's pixels without a display.
- `RAYLIB_A=/path/to/libraylib.a python3 tests/audio_host_test.py /path/to/libziran.a`
  exercises real hosted guests with dummy/no-provider and private null-device
  Raylib hosts. Run `tests/native_fixture.py`, `tests/consumer_test.py` and
  `tests/tree_test.sh` with the same resolved compiler/runtime graph too.
