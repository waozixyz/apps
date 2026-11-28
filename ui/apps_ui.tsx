import { SwipeArea } from "kryon/tsx/joystick";
// Typed UI composition. Native state and effects remain in apps.zi.
import * as NativeButton from "kryon/button";
import * as NativeCarousel from "kryon/carousel";
import * as NativeImage from "kryon/image";
import * as NativeJoystick from "kryon/joystick";
import * as NativeModal from "kryon/modal";
import * as NativeScroll from "kryon/scroll";
import * as NativeText from "kryon/text";
import * as NativeTextField from "kryon/text_field";
import * as NativeRules from "protocol";
import * as State from "apps";
import { AppCoversPalette } from "appearance";
import {
    APP_DOWNLOAD,
    APP_REORDER,
    AppCard,
    AppsAct,
    AppsCardAt,
    AppsIconAt,
    AppsCardPresent,
    AppsActionProps,
    AppsConsoleDownload,
    AppsConsoleDownloads,
    AppsConsoleOpen,
    AppsConsolePending,
    AppsDownloadOpen,
    AppsFind,
    AppsMenuItem,
    AppsPermissionFlag,
    AppsPermissionGranted,
    AppsPermissionLabel,
    AppsPropertiesClose,
    AppsPropertiesOpen,
    AppsPropertiesSave,
    AppsReadCatalog,
    AppsReplaceText,
    AppsResponse,
    AppsSceneryStart,
    AppsSize,
    AppsSupported,
    AppsTitleOpen,
    AppsVersionEqual,
    NewActions,
    NewByteBuffer,
    NewCoverItems,
    NewFrames,
    NewItems,
    NewItems1NativeCarouselCarouselItem,
    NewLabel,
    NewListSize,
    NewMarkers,
    NewSize,
    NewSizeText,
    NewSnapshot,
    NewText,
    NewVisible
} from "apps";
import {
    AppBounds,
    AppDark,
    AppFieldInput,
    AppFont,
    AppKey,
    AppKeyboard,
    AppScale,
    AppService,
    AppSession
} from "kryon/app_context";
import { ButtonEmphasis, ButtonTone, ContentAlignment, IconPlacement } from "kryon/control_props";
import { Color } from "kryon/drawing_props";
import { Rectangle } from "kryon/geometry";
import { PointInBounds } from "kryon/input_protocol";
import { Session } from "kryon/session";
import { TextAlign } from "kryon/text_align";
import { ResolvedModal } from "kryon/tsx/modal";
import { ActionModal } from "kryon/tsx/action_modal";
import { Scroll } from "kryon/tsx/scroll";
import { Box } from "kryon/tsx/box";
import { Button } from "kryon/tsx/button";
import { Carousel } from "kryon/tsx/carousel";
import { ContextMenu } from "kryon/tsx/context_menu";
import { Image } from "kryon/tsx/image";
import { LoadingIndicator } from "kryon/tsx/loading_indicator";
import { Text } from "kryon/tsx/text";
import { ControlledTextField } from "kryon/tsx/text_field";
import { WidgetPaletteUse } from "kryon/widget_palette";
import { CopyCString } from "std/c_string";
import { TextUntilNul } from "std/text_buffer";
import { TextHasSuffix } from "std/text_tools";
import { Vec } from "std/vec";
import { AppsLabel } from "words";

export function AppsMenuView(session: Session, scale: float32, language: string): void {
    let card = AppsFind(State.menu_id);
    if (!AppsCardPresent(card) || card.disabled) {
        nativeSet(State.menu_id, 0n, u8(0n));
        return;
    }
    let items = NewItems();
    let count: s32 = s32(0);
    if (card.update_available) {
        AppsMenuItem(
            nativeSlice(items),
            nativeRef(count),
            card,
            NativeRules.APPS_UPDATE,
            language,
            "update"
        );
    }
    AppsMenuItem(
        nativeSlice(items),
        nativeRef(count),
        card,
        NativeRules.APPS_OPEN,
        language,
        "open"
    );
    AppsMenuItem(
        nativeSlice(items),
        nativeRef(count),
        card,
        card.installed ? NativeRules.APPS_UNINSTALL : NativeRules.APPS_INSTALL,
        language,
        card.installed ? "uninstall" : "install"
    );
    AppsMenuItem(
        nativeSlice(items),
        nativeRef(count),
        card,
        card.favorite ? NativeRules.APPS_UNPIN : NativeRules.APPS_PIN,
        language,
        card.favorite ? "unpin" : "pin",
        !card.installed
    );
    AppsMenuItem(
        nativeSlice(items),
        nativeRef(count),
        card,
        NativeRules.APPS_INSTALL_TO_LAUNCHER,
        language,
        card.launcher === 1n
            ? "prompt_pending"
            : card.launcher === 2n
              ? "launcher_installed"
              : "install_to_launcher",
        !card.installed || card.launcher !== 0n
    );
    if (card.history_count > 0n) {
        AppsMenuItem(
            nativeSlice(items),
            nativeRef(count),
            card,
            NativeRules.APPS_ROLLBACK,
            language,
            "rollback"
        );
    }
    AppsMenuItem(
        nativeSlice(items),
        nativeRef(count),
        card,
        NativeRules.APPS_PROPERTIES,
        language,
        "properties"
    );
    if (count === 0n) {
        nativeSet(State.menu_id, 0n, u8(0n));
        return;
    }
    let menu = (
        <ContextMenu
            session={session}
            props={{
                key: u64(7n),
                open: true,
                x: State.menu_x,
                y: State.menu_y,
                scale: scale,
                escape: AppKey() === 256n || AppKey() === 27n
            }}
            items={nativeSlice(items, 0n, count)}
        />
    );
    if (menu.activated_id === NativeRules.APPS_UPDATE) {
        State.dialog_id = card.id;
        State.dialog = 1n;
        State.dialog_target = card.available;
    } else if (menu.activated_id === NativeRules.APPS_ROLLBACK) {
        State.dialog_id = card.id;
        State.dialog = 2n;
    } else if (menu.activated_id === NativeRules.APPS_PROPERTIES) {
        AppsPropertiesOpen(card);
    } else if (menu.activated_id === NativeRules.APPS_OPEN && State.cover_grid) {
        AppsConsoleOpen(card);
    } else if (menu.activated_id > 0n) {
        let operation =
            menu.activated_id === NativeRules.APPS_OPEN
                ? "open"
                : menu.activated_id === NativeRules.APPS_INSTALL
                  ? "install"
                  : menu.activated_id === NativeRules.APPS_UNINSTALL
                    ? "uninstall"
                    : menu.activated_id === NativeRules.APPS_PIN
                      ? "pin"
                      : menu.activated_id === NativeRules.APPS_UNPIN
                        ? "unpin"
                        : "install_to_launcher";
        AppsAct(operation, card.id);
    }
    if (!menu.open) {
        nativeSet(State.menu_id, 0n, u8(0n));
    }
}

export function AppsPropertiesView(
    session: Session,
    card: NativeRef<AppCard>,
    scale: float32,
    language: string,
    font: s32
): void {
    let gap = 12.0 * scale;
    let line = 20.0 * scale;
    let control = 44.0 * scale;
    let cell_width = 48.0 * scale;
    let cell_height = 44.0 * scale;
    let count = s32(State.icon_choices.count);
    let content_height = line + 4.0 * scale + control + gap + control;
    if (count > 0n) {
        content_height =
            content_height +
            (line + 4.0 * scale + float32((count + 7n) / 8n) * cell_height + 8.0 * scale + gap);
    }
    const frame = ResolvedModal({
        session: session,
        props: {
            key: u64(12n),
            title: AppsLabel(language, "properties"),
            width: s32(440.0 * scale),
            height: s32(content_height + 74.0 * scale),
            scale: scale
        },
        children: (frame: NativeModal.ModalFrameResult): void => {
            let area = frame.layout.content;
            let x = area.x;
            let y = area.y;
            let width = area.width;
            let bottom = area.y + area.height;
            <Text
                session={session}
                props={{
                    key: u64(13n),
                    bounds: { x: x, y: y, width: width, height: line },
                    text: AppsLabel(language, "name"),
                    size: font,
                    wrap: NativeText.Wrap.TextWrapEllipsis
                }}
            />;
            y = y + (line + 4.0 * scale);
            let placeholder = TextUntilNul(nativeSlice(card.original_title));
            if (placeholder === "") {
                placeholder = TextUntilNul(nativeSlice(card.title));
            }
            let snapshot = NewSnapshot();
            for (let byte = s64(0n); byte < snapshot.count; byte += s64(1)) {
                nativeSet(snapshot, byte, nativeAt(State.properties_title, byte));
            }
            let field: NativeTextField.Props = {
                key: u64(14n),
                bounds: { x: x, y: y, width: width, height: control },
                value: TextUntilNul(nativeSlice(snapshot)),
                label: AppsLabel(language, "name"),
                placeholder: placeholder,
                cursor: State.properties_cursor,
                anchor: State.properties_anchor,
                scroll_x: State.properties_scroll_x,
                focused: State.properties_focused,
                scale: scale,
                max_bytes: s32(State.properties_title.count) - 1n
            };
            if (State.properties_focused) {
                field.input = AppFieldInput();
            }
            let edited = <ControlledTextField session={session} props={field} />;
            if (edited.edit.changed) {
                AppsReplaceText(
                    nativeSlice(State.properties_title),
                    edited.edit.start,
                    edited.edit.end,
                    edited.edit.replacement
                );
            }
            State.properties_cursor = edited.cursor;
            State.properties_anchor = edited.anchor;
            State.properties_scroll_x = edited.scroll_x;
            State.properties_focused = edited.focused && !edited.escaped;
            AppKeyboard(State.properties_focused);
            y = y + (control + gap);
            if (count > 0n) {
                <Text
                    session={session}
                    props={{
                        key: u64(15n),
                        bounds: { x: x, y: y, width: width, height: line },
                        text: AppsLabel(language, "icon"),
                        size: font,
                        wrap: NativeText.Wrap.TextWrapEllipsis
                    }}
                />;
                y = y + (line + 4.0 * scale);
                let columns = s32(width / cell_width);
                if (columns < 1n) {
                    columns = 1n;
                }
                let rows = (count + columns - 1n) / columns;
                let visible = bottom - control - gap - y;
                if (visible < cell_height) {
                    visible = cell_height;
                }
                const grid = Scroll({
                    session: session,
                    props: {
                        key: u64(16n),
                        bounds: { x: x, y: y, width: width, height: visible },
                        scale: scale,
                        content_height: s32(float32(rows) * cell_height + 8.0 * scale),
                        scroll_offset: State.icon_scroll
                    },
                    children: (grid: NativeScroll.ScrollResult): void => {
                        State.icon_scroll = grid.scroll_offset;

                        for (let index = s32(0n); index < count; index += s32(1)) {
                            let choice = AppsIconAt(index);
                            let chosen =
                                TextUntilNul(nativeSlice(choice.id)) ===
                                TextUntilNul(nativeSlice(State.properties_icon));
                            const choice_label = TextUntilNul(nativeSlice(choice.id));
                            let default_label = TextUntilNul(nativeSlice(card.original_title));
                            if (default_label.count === 0n) {
                                default_label = TextUntilNul(nativeSlice(card.title));
                            }
                            const label = choice_label.count > 0n ? choice_label : default_label;
                            let icon: NativeButton.Props = {
                                key: u64(100n + index),
                                label: label,
                                icon_only: true,
                                circle: true,
                                icon_shape: TextUntilNul(nativeSlice(choice.shape)),
                                selected: chosen,
                                image: {
                                    asset_path: TextUntilNul(nativeSlice(choice.image)),
                                    alt_text: label
                                },
                                bounds: {
                                    x:
                                        grid.content.x +
                                        float32(index % columns) * cell_width +
                                        4.0 * scale,
                                    y:
                                        grid.content.y +
                                        float32(index / columns) * cell_height +
                                        4.0 * scale,
                                    width: 40.0 * scale,
                                    height: 40.0 * scale
                                },
                                tone: chosen
                                    ? ButtonTone.ButtonToneAccent
                                    : ButtonTone.ButtonToneNeutral,
                                emphasis: chosen
                                    ? ButtonEmphasis.ButtonEmphasisFilled
                                    : ButtonEmphasis.ButtonEmphasisSoft
                            };
                            if ((<Button session={session} props={icon} />)) {
                                State.properties_icon = choice.id;
                            }
                        }
                    }
                });
                if (!grid.opened) {
                    State.icon_scroll = grid.scroll_offset;
                }
            }
            let button_width = (width - gap) * 0.5;
            if (button_width > 160.0 * scale) {
                button_width = 160.0 * scale;
            }
            let save = (
                <Button
                    session={session}
                    props={{
                        key: u64(17n),
                        label: AppsLabel(language, "save"),
                        bounds: {
                            x: x + width - button_width,
                            y: bottom - control,
                            width: button_width,
                            height: control
                        },
                        tone: ButtonTone.ButtonToneAccent,
                        emphasis: ButtonEmphasis.ButtonEmphasisFilled
                    }}
                />
            );
            let cancel = (
                <Button
                    session={session}
                    props={{
                        key: u64(18n),
                        label: AppsLabel(language, "cancel"),
                        bounds: {
                            x: x + width - button_width * 2.0 - gap,
                            y: bottom - control,
                            width: button_width,
                            height: control
                        },
                        emphasis: ButtonEmphasis.ButtonEmphasisGhost
                    }}
                />
            );
            if (cancel) {
                AppsPropertiesClose();
            } else if (save || edited.committed) {
                AppsPropertiesSave(card);
                AppsPropertiesClose();
            }
        }
    });
    if (frame.dismissed) {
        AppsPropertiesClose();
    }
}

export function AppsDownloadView(
    session: Session,
    card: NativeRef<AppCard>,
    scale: float32,
    language: string,
    font: s32
): void {
    let opening = State.download_fresh;
    State.download_fresh = false;
    if (
        !State.download_started &&
        ((card.on_device && card.installed) || !AppsSupported(card, NativeRules.APPS_INSTALL))
    ) {
        AppsPropertiesClose();
        return;
    }
    if (State.download_started && card.on_device) {
        if (!card.installed) {
            if (!State.download_installing) {
                AppsAct("install", card.id);
                State.download_installing = true;
            } else if (TextUntilNul(nativeSlice(State.status)) === "rejected") {
                AppsPropertiesClose();
            }
            return;
        }
        AppsPropertiesClose();
        if (State.cover_grid && TextUntilNul(nativeSlice(card.cover.action)) === "title") {
            AppsTitleOpen(card);
        } else {
            AppsAct("open", card.id);
        }
        return;
    }
    let gap = 12.0 * scale;
    let line = 24.0 * scale;
    let control = 44.0 * scale;
    let icon_size = 48.0 * scale;
    let bar = 10.0 * scale;
    State.download_frames = State.download_frames + 1n;
    let asking = !State.download_started && !card.downloading && !card.download_failed;
    let size_text = NewSizeText();
    let has_size = AppsSize(card.bytes, nativeSlice(size_text));
    let permission_count: s32 = s32(0);
    for (let bit = u32(0n); bit <= 3n; bit += u32(1)) {
        if (AppsPermissionGranted(card.permissions, AppsPermissionFlag(bit))) {
            permission_count = permission_count + 1n;
        }
    }
    let editor_addon = TextHasSuffix(TextUntilNul(nativeSlice(card.id)), "-editor");
    let content_height = icon_size + gap + control;
    if (editor_addon) {
        content_height = content_height + (line * 3.0 + gap);
    }
    if (card.download_count > 1n) {
        content_height = content_height + (float32(card.download_count) * line + gap);
    }
    if (asking && permission_count > 0n) {
        content_height = content_height + (line + float32(permission_count) * line + gap);
    }
    if (card.downloading || (State.download_started && !card.on_device && !card.download_failed)) {
        content_height = content_height + (bar + gap);
    }
    let area: Rectangle = {};
    if (State.cover_grid) {
        let viewport = AppBounds();
        let art =
            viewport.width > viewport.height
                ? TextUntilNul(nativeSlice(card.cover.landscape))
                : TextUntilNul(nativeSlice(card.cover.portrait));
        if (art === "") {
            art = TextUntilNul(nativeSlice(card.preview));
        }
        <Image
            session={session}
            props={{
                key: u64(50030n),
                bounds: viewport,
                asset_path: art,
                alt_text: TextUntilNul(nativeSlice(card.title)),
                fit: NativeImage.ImageFit.ImageFitCover,
                smooth: true
            }}
        />;
        <Box
            session={session}
            props={{
                key: u64(50031n),
                bounds: viewport,
                fill: { r: 5n, g: 13n, b: 20n, a: 35n },
                fill_bottom: { r: 5n, g: 13n, b: 20n, a: 245n },
                has_fill_bottom: true
            }}
        />;
        let width = viewport.width - 48.0 * scale;
        if (width > 560.0 * scale) {
            width = 560.0 * scale;
        }
        area = {
            x: viewport.x + (viewport.width - width) * 0.5,
            y: viewport.y + viewport.height - content_height - 36.0 * scale,
            width: width,
            height: content_height
        };
        if (area.y < viewport.y + 120.0 * scale) {
            area.y = viewport.y + 120.0 * scale;
        }
        <Text
            session={session}
            props={{
                key: u64(50032n),
                bounds: { x: area.x, y: area.y - 64.0 * scale, width: width, height: 52.0 * scale },
                text: TextUntilNul(nativeSlice(card.title)),
                size: font + 18n,
                wrap: NativeText.Wrap.TextWrapEllipsis
            }}
        />;
        if (
            (
                <Button
                    session={session}
                    props={{
                        key: u64(50033n),
                        bounds: {
                            x: viewport.x + 12.0 * scale,
                            y: viewport.y + 12.0 * scale,
                            width: 108.0 * scale,
                            height: 48.0 * scale
                        },
                        label: AppsLabel(language, "back"),
                        icon_shape: "S2rr:M15 18L9 12L15 6",
                        emphasis: ButtonEmphasis.ButtonEmphasisSoft
                    }}
                />
            )
        ) {
            AppsPropertiesClose();
            return;
        }
        AppsDownloadContents(
            session,
            card,
            scale,
            language,
            font,
            area,
            gap,
            line,
            control,
            icon_size,
            bar,
            asking,
            has_size,
            TextUntilNul(nativeSlice(size_text)),
            permission_count,
            editor_addon
        );
    } else {
        const frame = ResolvedModal({
            session: session,
            props: {
                key: u64(19n),
                title: TextUntilNul(nativeSlice(card.title)),
                width: s32(440.0 * scale),
                height: s32(content_height + 74.0 * scale),
                scale: scale,
                dismiss_disabled: opening
            },
            children: (frame: NativeModal.ModalFrameResult): void => {
                AppsDownloadContents(
                    session,
                    card,
                    scale,
                    language,
                    font,
                    frame.layout.content,
                    gap,
                    line,
                    control,
                    icon_size,
                    bar,
                    asking,
                    has_size,
                    TextUntilNul(nativeSlice(size_text)),
                    permission_count,
                    editor_addon
                );
            }
        });
        if (frame.dismissed) {
            AppsPropertiesClose();
        }
    }
}

function AppsDownloadContents(
    session: Session,
    card: NativeRef<AppCard>,
    scale: float32,
    language: string,
    font: s32,
    area: Rectangle,
    gap: float32,
    line: float32,
    control: float32,
    icon_size: float32,
    bar: float32,
    asking: boolean,
    has_size: boolean,
    size_label: string,
    permission_count: s32,
    editor_addon: boolean
): void {
    let x = area.x;
    let y = area.y;
    let width = area.width;
    let bottom = area.y + area.height;
    <Button
        session={session}
        props={{
            key: u64(20n),
            label: TextUntilNul(nativeSlice(card.title)),
            icon_only: true,
            icon_shape: TextUntilNul(nativeSlice(card.icon_shape)),
            image: {
                asset_path: TextUntilNul(nativeSlice(card.icon)),
                alt_text: TextUntilNul(nativeSlice(card.title))
            },
            bounds: { x: x, y: y, width: icon_size, height: icon_size },
            emphasis: ButtonEmphasis.ButtonEmphasisSoft
        }}
    />;
    let state: Vec<u8> = NewByteBuffer();
    if (card.on_device) {
        BuilderPrint(nativeRef(state), "%", AppsLabel(language, "ready"));
    } else if (card.download_failed) {
        BuilderPrint(nativeRef(state), "%", AppsLabel(language, "download_failed"));
    } else if (card.downloading && card.progress >= 0n) {
        BuilderPrint(nativeRef(state), "% %", AppsLabel(language, "downloading"), card.progress);
        BuilderPrint(nativeRef(state), "%", "%");
    } else if (card.downloading) {
        BuilderPrint(nativeRef(state), "%", AppsLabel(language, "downloading"));
    } else if (State.download_started) {
        BuilderPrint(nativeRef(state), "%", AppsLabel(language, "download_waiting"));
    } else if (has_size) {
        BuilderPrint(nativeRef(state), "%: %", AppsLabel(language, "download_size"), size_label);
    } else {
        BuilderPrint(nativeRef(state), "%", AppsLabel(language, "download"));
    }
    CopyCString(TextView(VecSlice(state, 0n, state.count)), nativeSlice(State.dialog_message));
    VecFree(state);
    <Text
        session={session}
        props={{
            key: u64(21n),
            text: TextUntilNul(nativeSlice(State.dialog_message)),
            size: font + 2n,
            bounds: {
                x: x + icon_size + gap,
                y: y,
                width: width - icon_size - gap,
                height: icon_size
            },
            wrap: NativeText.Wrap.TextWrapEllipsis,
            vertical_align: TextAlign.TextAlignCenter
        }}
    />;
    y = y + (icon_size + gap);
    if (editor_addon) {
        <Text
            session={session}
            props={{
                key: u64(29n),
                text: AppsLabel(language, "editor_addon"),
                size: font,
                bounds: { x: x, y: y, width: width, height: line * 3.0 },
                wrap: NativeText.Wrap.TextWrapAuto
            }}
        />;
        y = y + (line * 3.0 + gap);
    }
    if (card.download_count > 1n) {
        let item = card.downloads;
        for (let index = s32(0n); index < card.download_count; index += s32(1)) {
            let size = NewSize();
            let label: Vec<u8> = NewByteBuffer();
            BuilderPrint(nativeRef(label), "%", TextUntilNul(nativeSlice(item.title)));
            if (item.dependency) {
                BuilderPrint(nativeRef(label), " (%)", AppsLabel(language, "download_dependency"));
            }
            if (AppsSize(item.bytes, nativeSlice(size))) {
                BuilderPrint(nativeRef(label), " · %", TextUntilNul(nativeSlice(size)));
            }
            let text = NewText();
            CopyCString(TextView(VecSlice(label, 0n, label.count)), nativeSlice(text));
            VecFree(label);
            <Text
                session={session}
                props={{
                    key: u64(100n) + u64(index),
                    bounds: { x: x, y: y, width: width, height: line },
                    text: TextUntilNul(nativeSlice(text)),
                    size: font,
                    wrap: NativeText.Wrap.TextWrapEllipsis
                }}
            />;
            y = y + line;
            item = item.next;
        }
        y = y + gap;
    }
    if (asking && permission_count > 0n) {
        <Text
            session={session}
            props={{
                key: u64(22n),
                bounds: { x: x, y: y, width: width, height: line },
                text: AppsLabel(language, "app_can"),
                size: font,
                wrap: NativeText.Wrap.TextWrapEllipsis
            }}
        />;
        y = y + line;
        for (let bit = u32(0n); bit <= 3n; bit += u32(1)) {
            let flag = AppsPermissionFlag(bit);
            if (!AppsPermissionGranted(card.permissions, flag)) {
                continue;
            }
            let bullet: Vec<u8> = NewByteBuffer();
            BuilderPrint(nativeRef(bullet), "•  %", AppsLabel(language, AppsPermissionLabel(flag)));
            let label = NewLabel();
            CopyCString(TextView(VecSlice(bullet, 0n, bullet.count)), nativeSlice(label));
            VecFree(bullet);
            <Text
                session={session}
                props={{
                    key: u64(23n) + u64(bit),
                    bounds: { x: x + 8.0 * scale, y: y, width: width - 8.0 * scale, height: line },
                    text: TextUntilNul(nativeSlice(label)),
                    size: font,
                    wrap: NativeText.Wrap.TextWrapEllipsis
                }}
            />;
            y = y + line;
        }
        y = y + gap;
    }
    if (card.downloading || (State.download_started && !card.on_device && !card.download_failed)) {
        let track: Rectangle = { x: x, y: y, width: width, height: bar };
        if (card.downloading && card.progress >= 0n) {
            <Box
                session={session}
                props={{
                    key: u64(28n),
                    bounds: track,
                    radius: bar * 0.5,
                    fill: AppDark()
                        ? { r: 58n, g: 74n, b: 68n, a: 255n }
                        : { r: 221n, g: 232n, b: 226n, a: 255n }
                }}
            />;
            let fill = track;
            fill.width = (width * float32(card.progress)) / 100.0;
            if (fill.width >= bar) {
                <Box
                    session={session}
                    props={{
                        key: u64(29n),
                        bounds: fill,
                        radius: bar * 0.5,
                        fill: { r: 46n, g: 125n, b: 74n, a: 255n }
                    }}
                />;
            }
        } else {
            <LoadingIndicator
                session={session}
                props={{
                    key: u64(29n),
                    bounds: { x: x, y: y - bar, width: width, height: bar * 3.0 },
                    now: float64(State.download_frames) / 60.0,
                    scale: scale
                }}
            />;
        }
        y = y + (bar + gap);
    }
    let button_width = (width - gap) * 0.5;
    if (button_width > 160.0 * scale) {
        button_width = 160.0 * scale;
    }
    let primary: Rectangle = {
        x: x + width - button_width,
        y: bottom - control,
        width: button_width,
        height: control
    };
    let secondary: Rectangle = {
        x: x + width - button_width * 2.0 - gap,
        y: bottom - control,
        width: button_width,
        height: control
    };
    if (asking || card.download_failed || card.on_device) {
        let label = "download";
        if (card.on_device) {
            label = card.installed ? "open" : "install";
        } else if (card.download_failed) {
            label = "try_again";
        }
        let go = (
            <Button
                session={session}
                props={{
                    key: u64(30n),
                    label: AppsLabel(language, label),
                    bounds: primary,
                    tone: ButtonTone.ButtonToneAccent,
                    emphasis: ButtonEmphasis.ButtonEmphasisFilled,
                    disabled: !AppsSupported(
                        card,
                        card.on_device && card.installed
                            ? NativeRules.APPS_OPEN
                            : NativeRules.APPS_INSTALL
                    )
                }}
            />
        );
        let close = (
            <Button
                session={session}
                props={{
                    key: u64(31n),
                    bounds: secondary,
                    label: AppsLabel(language, asking ? "cancel" : "close"),
                    emphasis: ButtonEmphasis.ButtonEmphasisGhost
                }}
            />
        );
        if (close) {
            AppsPropertiesClose();
        } else if (go && card.on_device && card.installed) {
            AppsAct("open", card.id);
            AppsPropertiesClose();
        } else if (go) {
            AppsAct("install", card.id);
            State.download_started = true;
            State.download_installing = false;
            State.download_frames = 0n;
        }
        return;
    }
    let hide = (
        <Button
            session={session}
            props={{
                key: u64(32n),
                label: AppsLabel(language, "hide"),
                bounds: primary,
                emphasis: ButtonEmphasis.ButtonEmphasisSoft
            }}
        />
    );
    if (hide) {
        AppsPropertiesClose();
    }
}

export function AppsDialogView(
    session: Session,
    scale: float32,
    language: string,
    font: s32
): void {
    if (State.dialog === 0n) {
        return;
    }
    let card = AppsFind(State.dialog_id);
    if (
        !AppsCardPresent(card) ||
        card.disabled ||
        (!State.download_fresh &&
            (AppKey() === 256n || AppKey() === 27n || (State.cover_grid && AppKey() === 290n)))
    ) {
        AppsPropertiesClose();
        return;
    }
    if (State.dialog === 5n) {
        AppsDownloadView(session, card, scale, language, font);
        return;
    }
    if (State.dialog === 4n) {
        if (!AppsSupported(card, NativeRules.APPS_PROPERTIES)) {
            AppsPropertiesClose();
            return;
        }
        AppsPropertiesView(session, card, scale, language, font);
        return;
    }
    if (
        (State.dialog === 1n && !AppsSupported(card, NativeRules.APPS_UPDATE)) ||
        (State.dialog >= 2n && !AppsSupported(card, NativeRules.APPS_ROLLBACK))
    ) {
        State.dialog = 0n;
        return;
    }
    let message: Vec<u8> = NewByteBuffer();
    BuilderPrint(
        nativeRef(message),
        "%\n%: %",
        TextUntilNul(nativeSlice(card.title)),
        AppsLabel(language, "current_version"),
        TextUntilNul(nativeSlice(card.current_version))
    );
    let actions = NewActions();
    let count: s32 = s32(0);
    let valid: boolean = false;
    if (State.dialog === 2n) {
        BuilderPrint(nativeRef(message), "\n%", AppsLabel(language, "choose_version"));
        for (let index = s32(0n); index < card.history_count; index += s32(1)) {
            nativeSet(actions, count, {
                label: TextUntilNul(nativeSlice(nativeAt(card.history, index).version)),
                emphasis: ButtonEmphasis.ButtonEmphasisSoft
            });
            count = count + 1n;
        }
    } else {
        let label = State.dialog === 1n ? "available_version" : "restore_version";
        BuilderPrint(
            nativeRef(message),
            "\n%: %",
            AppsLabel(language, label),
            TextUntilNul(nativeSlice(State.dialog_target.version))
        );
        if (State.dialog === 1n) {
            valid =
                card.update_available &&
                AppsVersionEqual(nativeRef(card.available), nativeRef(State.dialog_target));
        } else {
            for (let index = s32(0n); index < card.history_count; index += s32(1)) {
                if (
                    AppsVersionEqual(
                        nativeRef(nativeAt(card.history, index)),
                        nativeRef(State.dialog_target)
                    )
                ) {
                    valid = true;
                }
            }
        }
        nativeSet(actions, count, {
            label: AppsLabel(language, State.dialog === 1n ? "update" : "rollback"),
            tone: ButtonTone.ButtonToneAccent,
            emphasis: ButtonEmphasis.ButtonEmphasisFilled,
            disabled: !valid
        });
        count = count + 1n;
    }
    nativeSet(actions, count, {
        label: AppsLabel(language, "cancel"),
        emphasis: ButtonEmphasis.ButtonEmphasisGhost
    });
    count = count + 1n;
    CopyCString(TextView(VecSlice(message, 0n, message.count)), nativeSlice(State.dialog_message));
    VecFree(message);
    let result = ActionModal({
        session: session,
        props: {
            key: u64(8n + State.dialog),
            title: AppsLabel(language, State.dialog === 1n ? "update" : "rollback"),
            message: TextUntilNul(nativeSlice(State.dialog_message)),
            scale: scale,
            max_width: 440n
        },
        actions: nativeSlice(actions, 0n, count)
    });
    if (result.action < 0n || result.action === count) {
        State.dialog = 0n;
    } else if (result.action > 0n) {
        if (State.dialog === 2n) {
            State.dialog_target = nativeAt(card.history, result.action - 1n);
            State.dialog = 3n;
        } else if (valid) {
            AppsAct(State.dialog === 1n ? "update" : "rollback", card.id, State.dialog_target);
            State.dialog = 0n;
        }
    }
}

export function AppsTitleView(
    session: Session,
    bounds: Rectangle,
    scale: float32,
    language: string
): void {
    let card = AppsFind(State.title_id);
    if (!AppsCardPresent(card) || card.disabled) {
        nativeSet(State.title_id, 0n, 0n);
        return;
    }
    let items = NewItems1NativeCarouselCarouselItem();
    let action = TextUntilNul(nativeSlice(card.cover.action));
    nativeSet(items, 0n, {
        label: TextUntilNul(nativeSlice(card.title)),
        portrait:
            nativeAt(card.cover.portrait, 0n) !== 0n
                ? TextUntilNul(nativeSlice(card.cover.portrait))
                : TextUntilNul(nativeSlice(card.preview)),
        landscape: TextUntilNul(nativeSlice(card.cover.landscape)),
        logo: TextUntilNul(nativeSlice(card.cover.logo)),
        caption: TextUntilNul(nativeSlice(card.cover.caption)),
        action: AppsLabel(language, action === "title" ? "play" : action !== "" ? action : "open"),
        disabled:
            State.dialog !== 0n ||
            State.title_fresh ||
            card.disabled ||
            (action === "buy"
                ? !AppsSupported(card, NativeRules.APPS_INSTALL)
                : !AppsSupported(card, NativeRules.APPS_OPEN) &&
                  !(
                      (!card.on_device || !card.installed) &&
                      AppsSupported(card, NativeRules.APPS_INSTALL)
                  ))
    });
    State.cover_time = State.cover_time + 1.0 / 60.0;
    let entered = (
        <Carousel
            session={session}
            props={{
                key: u64(50000n),
                bounds: bounds,
                logo_max_width: State.cover_logo_width,
                logo_top: State.cover_logo_top,
                label: TextUntilNul(nativeSlice(card.title)),
                now: State.cover_time,
                key_pressed: State.title_fresh || State.dialog !== 0n ? 0n : AppKey(),
                scale: scale,
                dark: AppDark(),
                previous_label: AppsLabel(language, "previous"),
                next_label: AppsLabel(language, "next")
            }}
            items={nativeSlice(items)}
            state={nativeRef(State.title_state)}
        />
    );
    State.title_fresh = false;
    if (entered >= 0n) {
        if ((!card.on_device || !card.installed) && AppsSupported(card, NativeRules.APPS_INSTALL)) {
            AppsDownloadOpen(card);
        } else {
            AppsAct("open", card.id);
            nativeSet(State.title_id, 0n, 0n);
        }
    }
    if (
        AppKey() === 256n ||
        AppKey() === 27n ||
        AppKey() === 290n || (
            <Button
                session={session}
                props={{
                    key: u64(2n),
                    label: AppsLabel(language, "back"),
                    bounds: {
                        x: bounds.x + 12.0 * scale,
                        y: bounds.y + 12.0 * scale,
                        width: 84.0 * scale,
                        height: 44.0 * scale
                    },
                    emphasis: ButtonEmphasis.ButtonEmphasisSoft
                }}
            />
        )
    ) {
        nativeSet(State.title_id, 0n, 0n);
    }
    AppsDialogView(session, scale, language, AppFont());
}

export function AppsSceneryCircleView(
    session: Session,
    key: u64,
    x: float32,
    y: float32,
    radius: float32,
    fill: Color
): void {
    <Box
        session={session}
        props={{
            key: key,
            bounds: { x: x - radius, y: y - radius, width: radius * 2.0, height: radius * 2.0 },
            radius: radius,
            fill: fill
        }}
    />;
}

export function AppsSceneryView(
    session: Session,
    bounds: Rectangle,
    scale: float32,
    position: float32
): void {
    <Box
        session={session}
        props={{
            key: u64(50400n),
            bounds: bounds,
            fill: { r: 17n, g: 42n, b: 66n, a: 255n },
            fill_bottom: { r: 58n, g: 124n, b: 122n, a: 255n },
            has_fill_bottom: true
        }}
    />;
    let moon_x = bounds.x + bounds.width * 0.17;
    let moon_y = bounds.y + bounds.height * 0.2;
    for (let ring = s32(0n); ring <= 2n; ring += s32(1)) {
        AppsSceneryCircleView(
            session,
            u64(50401n + ring),
            moon_x,
            moon_y,
            float32(96n - ring * 22n) * scale,
            { r: 255n, g: 230n, b: 184n, a: u8(9n + ring * 5n) }
        );
    }
    AppsSceneryCircleView(session, u64(50404n), moon_x, moon_y, 30.0 * scale, {
        r: 255n,
        g: 236n,
        b: 196n,
        a: 235n
    });
    let tile = 360.0 * scale;
    let tiles = s32(bounds.width / tile) + 2n;
    if (tiles > 60n) {
        tiles = 60n;
    }
    let start = AppsSceneryStart(-position * 16.0 * scale, tile);
    for (let index = s32(0n); index < tiles; index += s32(1)) {
        let x = bounds.x + start + float32(index) * tile;
        let key = u64(54000n + index * 16n);
        for (let star = s32(0n); star <= 5n; star += s32(1)) {
            let column = float32((star * 37n + 11n) % 100n) / 100.0;
            let row = float32((star * 53n + 7n) % 40n) / 100.0;
            AppsSceneryCircleView(
                session,
                key + u64(star),
                x + column * tile,
                bounds.y + bounds.height * (0.05 + row),
                float32(1n + (star % 2n)) * scale,
                { r: 232n, g: 246n, b: 255n, a: 120n }
            );
        }
        let cloud_y = bounds.y + bounds.height * (index % 2n === 0n ? 0.17 : 0.31);
        let cloud: Color = { r: 50n, g: 88n, b: 106n, a: 255n };
        <Box
            session={session}
            props={{
                key: key + u64(6n),
                bounds: { x: x + tile * 0.3, y: cloud_y, width: tile * 0.42, height: 22.0 * scale },
                radius: 11.0 * scale,
                fill: cloud
            }}
        />;
        AppsSceneryCircleView(
            session,
            key + u64(7n),
            x + tile * 0.44,
            cloud_y + 2.0 * scale,
            20.0 * scale,
            cloud
        );
        AppsSceneryCircleView(
            session,
            key + u64(8n),
            x + tile * 0.56,
            cloud_y + 4.0 * scale,
            14.0 * scale,
            cloud
        );
    }
    for (let layer = s32(0n); layer <= 2n; layer += s32(1)) {
        let top = bounds.y + bounds.height * (0.58 + float32(layer) * 0.13);
        let radius = tile * (0.56 - float32(layer) * 0.06);
        let fill: Color =
            layer === 0n
                ? { r: 56n, g: 122n, b: 124n, a: 255n }
                : layer === 1n
                  ? { r: 36n, g: 96n, b: 96n, a: 255n }
                  : { r: 21n, g: 64n, b: 68n, a: 255n };
        <Box
            session={session}
            props={{
                key: u64(50410n + layer),
                bounds: {
                    x: bounds.x,
                    y: top,
                    width: bounds.width,
                    height: bounds.y + bounds.height - top
                },
                fill: fill
            }}
        />;
        let layer_start = AppsSceneryStart(
            -position * float32(24n + layer * 28n) * scale - float32(layer) * tile * 0.37,
            tile
        );
        for (let index = s32(0n); index < tiles; index += s32(1)) {
            let x = bounds.x + layer_start + float32(index) * tile;
            let key = u64(51000n + layer * 1000n + index * 16n);
            AppsSceneryCircleView(session, key, x + tile * 0.25, top + radius * 0.62, radius, fill);
            AppsSceneryCircleView(
                session,
                key + u64(1n),
                x + tile * 0.78,
                top + radius * 0.8,
                radius * 0.7,
                fill
            );
        }
        if (layer !== 1n) {
            continue;
        }
        for (let index = s32(0n); index < tiles; index += s32(1)) {
            let x = bounds.x + layer_start + float32(index) * tile;
            let key = u64(55000n + index * 16n);
            for (let tree = s32(0n); tree <= 2n; tree += s32(1)) {
                let tree_x = x + tile * (0.12 + float32(tree) * 0.31);
                let size = float32(13n + ((tree * 5n + index * 3n) % 8n)) * scale;
                let base = top - radius * (0.18 - float32(tree) * 0.05);
                <Box
                    session={session}
                    props={{
                        key: key + u64(tree * 2n),
                        bounds: {
                            x: tree_x - 2.0 * scale,
                            y: base - size,
                            width: 4.0 * scale,
                            height: size + 4.0 * scale
                        },
                        fill: { r: 30n, g: 62n, b: 58n, a: 255n }
                    }}
                />;
                AppsSceneryCircleView(
                    session,
                    key + u64(tree * 2n + 1n),
                    tree_x,
                    base - size * 1.4,
                    size,
                    { r: 28n, g: 82n, b: 78n, a: 255n }
                );
            }
        }
    }
    let shade = bounds.y + bounds.height * 0.62;
    <Box
        session={session}
        props={{
            key: u64(50420n),
            bounds: {
                x: bounds.x,
                y: shade,
                width: bounds.width,
                height: bounds.y + bounds.height - shade
            },
            fill: { r: 6n, g: 18n, b: 24n, a: 0n },
            fill_bottom: { r: 6n, g: 18n, b: 24n, a: 170n },
            has_fill_bottom: true
        }}
    />;
}

export function AppsConsoleView(
    session: Session,
    bounds: Rectangle,
    scale: float32,
    language: string,
    font: s32
): void {
    AppsConsoleDownloads();
    let visible = NewVisible();
    let count: s32 = s32(0);
    for (let index = s32(0n); index < s32(State.cards.count); index += s32(1)) {
        const candidate = AppsCardAt(index);
        if (
            TextUntilNul(nativeSlice(candidate.cover.action)) !== "internal" &&
            !TextHasSuffix(TextUntilNul(nativeSlice(candidate.id)), "-editor")
        ) {
            nativeSet(visible, count, index);
            count = count + 1n;
        }
    }
    if (count === 0n) {
        <Text
            session={session}
            props={{
                key: u64(6n),
                bounds: bounds,
                text: AppsLabel(language, "empty"),
                size: font,
                wrap: NativeText.Wrap.TextWrapEllipsis
            }}
        />;
        return;
    }
    let wide = bounds.width > bounds.height;
    let key = State.dialog === 0n && nativeAt(State.menu_id, 0n) === 0n ? AppKey() : 0n;
    let delta: s32 = s32(0);
    if (key === 262n || key === 264n) {
        delta = 1n;
    }
    if (key === 263n || key === 265n) {
        delta = -1n;
    }
    State.cover_time = State.cover_time + 1.0 / 60.0;
    if (State.dialog === 0n && nativeAt(State.menu_id, 0n) === 0n) {
        let wheel = NativeCarousel.CarouselWheel(session, bounds);
        if (wheel !== 0.0 && State.cover_time - State.cover_state.wheel_time > 0.18) {
            delta = wheel < 0.0 ? 1n : -1n;
            State.cover_state.wheel_time = State.cover_time;
        }
    }
    NativeCarousel.CarouselSelect(nativeRef(State.cover_state), count, delta, State.cover_time);
    let selected_index = State.cover_state.selected;
    AppsSceneryView(session, bounds, scale, State.cover_state.position);
    let gap = 18.0 * scale;
    let center = bounds.x + bounds.width * 0.5;
    let ratio: float32 = wide ? 16.0 / 9.0 : 2.0 / 3.0;
    let width = bounds.width * (wide ? 0.58 : 0.7);
    let available = bounds.height - 220.0 * scale;
    if (width / ratio > available) {
        width = available * ratio;
    }
    if (width < 40.0 * scale) {
        width = 40.0 * scale;
    }
    let y = bounds.y + 108.0 * scale + (available - width / ratio) * 0.5;
    let stride = width + gap;
    let height = width / ratio;
    let frames = NewFrames();
    let markers = NewMarkers();
    let focused_action: Rectangle = {};
    let focused_action_enabled: boolean = false;
    let activated: s32 = -1n;
    if (key === 257n || key === 32n) {
        activated = State.cover_state.selected;
    }
    for (let index = s32(0n); index < count; index += s32(1)) {
        let card = AppsCardAt(nativeAt(visible, index));
        let focused = index === selected_index;
        let x = center - width * 0.5 + (float32(index) - State.cover_state.position) * stride;
        if (x + width < bounds.x || x > bounds.x + bounds.width) {
            continue;
        }
        let shrink: float32 = focused ? 1.0 : 0.92;
        let w = width * shrink;
        let h = height * shrink;
        let frame: Rectangle = {
            x: x + (width - w) * 0.5,
            y: y + (height - h) * 0.5,
            width: w,
            height: h
        };
        nativeSet(frames, index, frame);
        let card_key = NativeRules.AppCardKey(TextUntilNul(nativeSlice(card.id)));
        if (focused) {
            for (let glow = s32(0n); glow <= 2n; glow += s32(1)) {
                let pad = float32(10n - glow * 3n) * scale;
                <Box
                    session={session}
                    props={{
                        key: card_key + u64(10n + glow),
                        bounds: {
                            x: frame.x - pad,
                            y: frame.y - pad,
                            width: w + pad * 2.0,
                            height: h + pad * 2.0
                        },
                        radius: 20.0 * scale + pad,
                        fill:
                            glow === 2n
                                ? { r: 211n, g: 255n, b: 219n, a: 255n }
                                : { r: 80n, g: 235n, b: 219n, a: u8(35n + glow * 35n) }
                    }}
                />;
            }
        } else {
            <Box
                session={session}
                props={{
                    key: card_key + u64(10n),
                    bounds: {
                        x: frame.x - 2.0 * scale,
                        y: frame.y - 2.0 * scale,
                        width: w + 4.0 * scale,
                        height: h + 4.0 * scale
                    },
                    radius: 18.0 * scale,
                    fill: { r: 151n, g: 182n, b: 167n, a: 190n }
                }}
            />;
        }
        let art = wide
            ? TextUntilNul(nativeSlice(card.cover.landscape))
            : TextUntilNul(nativeSlice(card.cover.portrait));
        if (art === "") {
            art = TextUntilNul(nativeSlice(card.preview));
        }
        <Image
            session={session}
            props={{
                key: card_key + u64(2n),
                asset_path: art,
                alt_text: TextUntilNul(nativeSlice(card.title)),
                bounds: frame,
                radius: 16.0 * scale,
                fit: NativeImage.ImageFit.ImageFitCover,
                smooth: true
            }}
        />;
        if (!focused) {
            <Box
                session={session}
                props={{
                    key: card_key + u64(13n),
                    bounds: frame,
                    radius: 16.0 * scale,
                    fill: { r: 0n, g: 10n, b: 18n, a: 65n }
                }}
            />;
        }
        let download_first =
            (!card.on_device || !card.installed) && AppsSupported(card, NativeRules.APPS_INSTALL);
        if (
            (
                <Button
                    session={session}
                    props={{
                        key: card_key,
                        bounds: frame,
                        label: TextUntilNul(nativeSlice(card.title)),
                        selected: focused,
                        invisible: true,
                        disabled:
                            State.dialog !== 0n ||
                            card.disabled ||
                            ((key === 257n || key === 32n) && !focused) ||
                            (!AppsSupported(card, NativeRules.APPS_OPEN) && !download_first)
                    }}
                />
            )
        ) {
            if (focused) {
                activated = index;
            } else {
                State.cover_state.selected = index;
            }
        }
        let pending = AppsConsolePending(card.id) >= 0n;
        if (card.downloading || pending) {
            let track: Rectangle = {
                x: frame.x + 10.0 * scale,
                y: frame.y + h - 24.0 * scale,
                width: w - 64.0 * scale,
                height: 14.0 * scale
            };
            <Box
                session={session}
                props={{
                    key: card_key + u64(14n),
                    bounds: track,
                    radius: 7.0 * scale,
                    fill: { r: 20n, g: 39n, b: 42n, a: 240n }
                }}
            />;
            let fill = track;
            let progress = card.on_device ? 100n : card.progress >= 0n ? card.progress : 1n;
            fill.width = (track.width * float32(progress)) / 100.0;
            <Box
                session={session}
                props={{
                    key: card_key + u64(15n),
                    bounds: fill,
                    radius: 7.0 * scale,
                    fill: { r: 131n, g: 246n, b: 183n, a: 255n }
                }}
            />;
            <Text
                session={session}
                props={{
                    key: card_key + u64(16n),
                    bounds: {
                        x: track.x,
                        y: track.y - 24.0 * scale,
                        width: track.width,
                        height: 22.0 * scale
                    },
                    text: AppsLabel(language, "downloading"),
                    size: font,
                    wrap: NativeText.Wrap.TextWrapEllipsis
                }}
            />;
        } else if (card.download_failed) {
            <Text
                session={session}
                props={{
                    key: card_key + u64(14n),
                    bounds: {
                        x: frame.x + 8.0 * scale,
                        y: frame.y + h - 32.0 * scale,
                        width: w - 60.0 * scale,
                        height: 28.0 * scale
                    },
                    text: AppsLabel(language, "download_failed"),
                    size: font,
                    wrap: NativeText.Wrap.TextWrapEllipsis
                }}
            />;
        }
        if (focused) {
            let action = AppsActionProps(
                card_key + u64(5n),
                card,
                State.action_class,
                {
                    x: frame.x + w - 44.0 * scale,
                    y: frame.y + h - 44.0 * scale,
                    width: 36.0 * scale,
                    height: 36.0 * scale
                },
                language,
                true
            );
            focused_action = action.bounds;
            action.disabled = action.disabled || State.dialog !== 0n || key === 257n || key === 32n;
            focused_action_enabled = !action.disabled;
            if (!card.on_device || !card.installed) {
                action.label = AppsLabel(language, card.on_device ? "install" : "download");
                action.icon_shape = APP_DOWNLOAD;
                if ((<Button session={session} props={action} />)) {
                    AppsConsoleDownload(card);
                }
            } else if (<Button session={session} props={action} /> || key === 77n) {
                State.menu_id = card.id;
                State.menu_x = action.bounds.x;
                State.menu_y = action.bounds.y;
                if (
                    card.update_available &&
                    !card.update_seen &&
                    AppsSupported(card, NativeRules.APPS_SEEN)
                ) {
                    AppsAct("seen", card.id, card.available);
                }
            }
        }
    }
    if (activated >= 0n) {
        let card = AppsCardAt(nativeAt(visible, activated));
        if (!card.disabled) {
            AppsConsoleOpen(card);
        }
    }
    {
        let mini_height = (wide ? 58.0 : 76.0) * scale;
        let mini_width = mini_height * ratio;
        let mini_gap = 14.0 * scale;
        let mini_row = float32(count) * (mini_width + mini_gap) - mini_gap;
        for (let index = s32(0n); index < count; index += s32(1)) {
            let target: Rectangle = {
                x: center - mini_row * 0.5 + float32(index) * (mini_width + mini_gap),
                y: bounds.y + bounds.height - mini_height - 24.0 * scale,
                width: mini_width,
                height: mini_height
            };
            nativeSet(markers, index, target);
            let focused = index === selected_index;
            if (focused) {
                <Box
                    session={session}
                    props={{
                        key: u64(50100n + index),
                        bounds: {
                            x: target.x - 3.0 * scale,
                            y: target.y - 3.0 * scale,
                            width: target.width + 6.0 * scale,
                            height: target.height + 6.0 * scale
                        },
                        radius: 10.0 * scale,
                        fill: { r: 211n, g: 255n, b: 219n, a: 255n }
                    }}
                />;
            }
            let marker = AppsCardAt(nativeAt(visible, index));
            let marker_art = wide
                ? TextUntilNul(nativeSlice(marker.cover.landscape))
                : TextUntilNul(nativeSlice(marker.cover.portrait));
            if (marker_art === "") {
                marker_art = TextUntilNul(nativeSlice(marker.preview));
            }
            <Image
                session={session}
                props={{
                    key: u64(50300n + index),
                    bounds: target,
                    asset_path: marker_art,
                    alt_text: "",
                    radius: 8.0 * scale,
                    fit: NativeImage.ImageFit.ImageFitCover,
                    smooth: true
                }}
            />;
            if (
                (
                    <Button
                        session={session}
                        props={{
                            key: u64(50200n + index),
                            bounds: target,
                            label: TextUntilNul(nativeSlice(marker.title)),
                            invisible: true,
                            disabled: State.dialog !== 0n || key === 257n || key === 32n
                        }}
                    />
                )
            ) {
                State.cover_state.selected = index;
            }
        }
    }
    if (State.dialog === 0n && nativeAt(State.menu_id, 0n) === 0n) {
        let gesture = SwipeArea({
            session: session,
            props: {
                key: u64(50020n),
                bounds: {
                    x: bounds.x,
                    y: bounds.y + 88.0 * scale,
                    width: bounds.width,
                    height: bounds.height - 88.0 * scale
                },
                label: "",
                now: State.cover_time,
                min_distance: 40.0 * scale
            }
        });
        if (gesture.swiped === 0n) {
            NativeCarousel.CarouselSelect(
                nativeRef(State.cover_state),
                count,
                1n,
                State.cover_time
            );
        }
        if (gesture.swiped === 2n) {
            NativeCarousel.CarouselSelect(
                nativeRef(State.cover_state),
                count,
                -1n,
                State.cover_time
            );
        }
        if (gesture.tapped) {
            let handled: boolean = false;
            for (let index = s32(0n); index < count; index += s32(1)) {
                if (PointInBounds(gesture.x, gesture.y, nativeAt(markers, index))) {
                    State.cover_state.selected = index;
                    handled = true;
                }
            }
            if (!handled && PointInBounds(gesture.x, gesture.y, focused_action)) {
                let card = AppsCardAt(nativeAt(visible, State.cover_state.selected));
                if (!card.disabled && focused_action_enabled) {
                    if (!card.on_device || !card.installed) {
                        AppsConsoleDownload(card);
                    } else {
                        State.menu_id = card.id;
                        State.menu_x = focused_action.x;
                        State.menu_y = focused_action.y;
                        if (
                            card.update_available &&
                            !card.update_seen &&
                            AppsSupported(card, NativeRules.APPS_SEEN)
                        ) {
                            AppsAct("seen", card.id, card.available);
                        }
                    }
                }
                handled = true;
            }
            if (!handled) {
                for (let index = s32(0n); index < count; index += s32(1)) {
                    if (
                        nativeAt(frames, index).width > 0.0 &&
                        PointInBounds(gesture.x, gesture.y, nativeAt(frames, index))
                    ) {
                        let card = AppsCardAt(nativeAt(visible, index));
                        if (!card.disabled) {
                            if (index === selected_index) {
                                AppsConsoleOpen(card);
                            } else {
                                State.cover_state.selected = index;
                            }
                        }
                    }
                }
            }
        }
    }
    AppsMenuView(session, scale, language);
    AppsDialogView(session, scale, language, font);
}

export function AppsFrameView(): boolean {
    State.action_taken = false;
    let session = AppSession();
    let bounds = AppBounds();
    let font = AppFont();
    let scale = AppScale();
    if (scale <= 0.0) {
        scale = 1.0;
    }
    if (!AppsReadCatalog()) {
        <Text
            session={session}
            props={{
                key: u64(1n),
                bounds: bounds,
                text: AppsLabel("en", "unavailable"),
                size: font,
                wrap: NativeText.Wrap.TextWrapEllipsis
            }}
        />;
        return true;
    }
    let language = TextUntilNul(nativeSlice(State.locale));
    if (State.cover_grid) {
        WidgetPaletteUse(session, AppCoversPalette());
        <Box
            session={session}
            props={{
                key: u64(50010n),
                bounds: bounds,
                fill: { r: 17n, g: 18n, b: 35n, a: 255n },
                fill_bottom: { r: 28n, g: 24n, b: 46n, a: 255n },
                has_fill_bottom: true
            }}
        />;
    }
    if (State.request > 0n && TextUntilNul(nativeSlice(State.status)) === "queued") {
        let bytes: Vec<u8> = NewByteBuffer();
        BuilderPrint(nativeRef(bytes), '{"v":1,"op":"status","request":%}', State.request);
        AppsResponse(AppService("apps", TextView(VecSlice(bytes, 0n, bytes.count))));
        VecFree(bytes);
    }
    if (State.cover_grid) {
        if (State.dialog === 5n) {
            AppsDialogView(session, scale, language, font);
        } else if (nativeAt(State.title_id, 0n) !== 0n) {
            AppsTitleView(session, bounds, scale, language);
        } else {
            AppsConsoleView(session, bounds, scale, language, font);
        }
        return true;
    }
    if (State.cover_mode && !State.icon_mode && !State.cover_grid) {
        let cover_items = NewCoverItems();
        for (let index = s32(0n); index < s32(State.cards.count); index += s32(1)) {
            let card = AppsCardAt(index);
            let action = TextUntilNul(nativeSlice(card.cover.action));
            nativeSet(cover_items, index, {
                label: TextUntilNul(nativeSlice(card.title)),
                portrait:
                    nativeAt(card.cover.portrait, 0n) !== 0n
                        ? TextUntilNul(nativeSlice(card.cover.portrait))
                        : TextUntilNul(nativeSlice(card.preview)),
                landscape: TextUntilNul(nativeSlice(card.cover.landscape)),
                logo: TextUntilNul(nativeSlice(card.cover.logo)),
                caption: TextUntilNul(nativeSlice(card.cover.caption)),
                action: AppsLabel(
                    language,
                    action === "title" ? "play" : action !== "" ? action : "open"
                ),
                disabled:
                    State.dialog !== 0n ||
                    card.disabled ||
                    (action === "buy"
                        ? !AppsSupported(card, NativeRules.APPS_INSTALL)
                        : !AppsSupported(card, NativeRules.APPS_OPEN) &&
                          !(
                              (!card.on_device || !card.installed) &&
                              AppsSupported(card, NativeRules.APPS_INSTALL)
                          ))
            });
        }
        State.cover_time = State.cover_time + 1.0 / 60.0;
        let entered = (
            <Carousel
                session={session}
                props={{
                    key: u64(50000n),
                    bounds: bounds,
                    logo_max_width: State.cover_logo_width,
                    logo_top: State.cover_logo_top,
                    label: TextUntilNul(nativeSlice(State.title)),
                    now: State.cover_time,
                    key_pressed: State.dialog !== 0n ? 0n : AppKey(),
                    scale: scale,
                    dark: AppDark(),
                    previous_label: AppsLabel(language, "previous"),
                    next_label: AppsLabel(language, "next")
                }}
                items={nativeSlice(cover_items, 0n, State.cards.count)}
                state={nativeRef(State.cover_state)}
            />
        );
        if (entered >= 0n) {
            let card = AppsCardAt(entered);
            if (
                TextUntilNul(nativeSlice(card.cover.action)) === "buy" &&
                AppsSupported(card, NativeRules.APPS_INSTALL)
            ) {
                AppsAct("install", card.id);
            } else if (
                (!card.on_device || !card.installed) &&
                AppsSupported(card, NativeRules.APPS_INSTALL)
            ) {
                AppsDownloadOpen(card);
            } else {
                AppsAct("open", card.id);
            }
        }
        if (
            State.can_back && (
                <Button
                    session={session}
                    props={{
                        key: u64(2n),
                        label: AppsLabel(language, "back"),
                        bounds: {
                            x: bounds.x + 12.0 * scale,
                            y: bounds.y + 12.0 * scale,
                            width: 84.0 * scale,
                            height: 44.0 * scale
                        },
                        emphasis: ButtonEmphasis.ButtonEmphasisSoft
                    }}
                />
            )
        ) {
            AppsAct("back", State.empty_target);
        }
        if (TextUntilNul(nativeSlice(State.status)) === "rejected") {
            <Text
                session={session}
                props={{
                    key: u64(4n),
                    bounds: {
                        x: bounds.x + 20.0 * scale,
                        y: bounds.y + bounds.height - 64.0 * scale,
                        width: bounds.width - 40.0 * scale,
                        height: 44.0 * scale
                    },
                    text: AppsLabel(language, "rejected"),
                    size: font,
                    wrap: NativeText.Wrap.TextWrapEllipsis
                }}
            />;
        }
        AppsDialogView(session, scale, language, font);
        return true;
    }
    let gap = (State.cover_grid ? 20.0 : 12.0) * scale;
    let area = bounds;
    if (!State.icon_mode) {
        if (
            State.can_back && (
                <Button
                    session={session}
                    props={{
                        key: u64(2n),
                        label: AppsLabel(language, "back"),
                        bounds: {
                            x: bounds.x + gap,
                            y: bounds.y + gap,
                            width: 84.0 * scale,
                            height: 44.0 * scale
                        },
                        fit_content: true
                    }}
                />
            )
        ) {
            AppsAct("back", State.empty_target);
        }
        let title_x = bounds.x + gap + (State.can_back ? 96.0 * scale : 0.0);
        <Text
            session={session}
            props={{
                key: u64(3n),
                bounds: {
                    x: title_x,
                    y: bounds.y + gap,
                    width: bounds.x + bounds.width - gap - title_x,
                    height: 44.0 * scale
                },
                text: TextUntilNul(nativeSlice(State.title)),
                size: font + (State.cover_grid ? 16n : 4n),
                wrap: NativeText.Wrap.TextWrapEllipsis
            }}
        />;
        let top = bounds.y + (State.cover_grid ? 92.0 : 68.0) * scale;
        area = {
            x: bounds.x + gap,
            y: top,
            width: bounds.width - gap * 2.0,
            height: bounds.y + bounds.height - top - gap
        };
        let state_buffer = State.status;
        let state = TextUntilNul(nativeSlice(state_buffer));
        if (state === "rejected") {
            <Text
                session={session}
                props={{
                    key: u64(4n),
                    bounds: { x: area.x, y: area.y, width: area.width, height: 26.0 * scale },
                    text: AppsLabel(language, "rejected"),
                    size: font,
                    wrap: NativeText.Wrap.TextWrapEllipsis
                }}
            />;
            area.y = area.y + 30.0 * scale;
            area.height = area.height - 30.0 * scale;
        }
    }
    let columns: s32 = area.width >= 440.0 * scale ? 2n : 1n;
    let card_height = 232.0 * scale;
    if (State.icon_mode) {
        columns = s32((area.width + gap) / (140.0 * scale + gap));
        if (columns < 1n) {
            columns = 1n;
        }
        if (columns > 6n) {
            columns = 6n;
        }
        if (State.presentation_columns >= 1n && State.presentation_columns <= 6n) {
            columns = State.presentation_columns;
        }
        card_height = 88.0 * scale;
    }
    if (State.list_mode) {
        columns = 1n;
        card_height = 64.0 * scale;
        gap = 4.0 * scale;
    }
    if (State.cover_grid) {
        let narrow = area.width < 600.0 * scale;
        if (narrow) {
            gap = 12.0 * scale;
        }
        columns = s32((area.width + gap) / ((narrow ? 104.0 : 200.0) * scale + gap));
        if (columns < 1n) {
            columns = 1n;
        }
        if (columns > 4n) {
            columns = 4n;
        }
        if (State.cards.count > 0n && columns > s32(State.cards.count)) {
            columns = s32(State.cards.count);
        }
    }
    let card_width = (area.width - gap * float32(columns - 1n)) / float32(columns);
    let picture_height = 168.0 * scale;
    if (State.cover_grid) {
        picture_height =
            card_width *
            (bounds.height < 480.0 * scale && bounds.width > bounds.height ? 2.0 / 3.0 : 1.5);
        if (bounds.width > bounds.height && picture_height > area.height - 36.0 * scale) {
            picture_height = area.height - 36.0 * scale;
            if (picture_height < 120.0 * scale) {
                picture_height = 120.0 * scale;
            }
        }
        card_height = picture_height + 36.0 * scale;
    }
    let rows = (s32(State.cards.count) + columns - 1n) / columns;
    if (State.icon_mode) {
        AppsCardGrid(
            session,
            bounds,
            area,
            scale,
            font,
            language,
            columns,
            card_height,
            card_width,
            picture_height,
            gap
        );
    } else {
        const scroll = Scroll({
            session: session,
            props: {
                key: u64(5),
                bounds: area,
                scale: scale,
                content_height: rows * s32(card_height + gap),
                scroll_offset: State.scroll_offset
            },
            children: (scroll: NativeScroll.ScrollResult): void => {
                AppsCardGrid(
                    session,
                    bounds,
                    scroll.content,
                    scale,
                    font,
                    language,
                    columns,
                    card_height,
                    card_width,
                    picture_height,
                    gap
                );
            }
        });
        State.scroll_offset = scroll.scroll_offset;
        if (!scroll.opened) {
            return true;
        }
    }
    AppsMenuView(session, scale, language);
    AppsDialogView(session, scale, language, font);
    return true;
}

function AppsCardGrid(
    session: Session,
    bounds: Rectangle,
    area: Rectangle,
    scale: float32,
    font: s32,
    language: string,
    columns: s32,
    card_height: float32,
    card_width: float32,
    picture_height: float32,
    gap: float32
): void {
    if (State.cards.count === 0n) {
        <Text
            session={session}
            props={{
                key: u64(6n),
                bounds: area,
                text: AppsLabel(language, "empty"),
                size: font,
                wrap: NativeText.Wrap.TextWrapEllipsis
            }}
        />;
    }
    for (let index = s32(0n); index < s32(State.cards.count); index += s32(1)) {
        let card = AppsCardAt(index);
        let position = index;
        let section_y: float32 = float32(0);
        if (State.icon_mode && State.has_section_break && index >= State.section_break) {
            position = position - State.section_break;
            section_y =
                float32((State.section_break + columns - 1n) / columns) * (card_height + gap) +
                36.0 * scale;
        }
        let x = area.x + float32(position % columns) * (card_width + gap);
        let y = area.y + float32(position / columns) * (card_height + gap) + section_y;
        let key = NativeRules.AppCardKey(TextUntilNul(nativeSlice(card.id)));
        let tile: NativeButton.Props = {
            key: key,
            label: TextUntilNul(nativeSlice(card.title)),
            class_name: State.tile_class,
            bounds: { x: x, y: y, width: card_width, height: card_height },
            disabled: card.disabled,
            selected: card.selected,
            fit_content: true,
            emphasis: ButtonEmphasis.ButtonEmphasisSoft
        };
        if (card.selected) {
            tile.tone = ButtonTone.ButtonToneAccent;
            tile.emphasis = ButtonEmphasis.ButtonEmphasisFilled;
        }
        let download_first = !card.on_device && AppsSupported(card, NativeRules.APPS_INSTALL);
        tile.disabled =
            tile.disabled || (!AppsSupported(card, NativeRules.APPS_OPEN) && !download_first);
        let activated: boolean = false;
        if (State.cover_grid) {
            tile.invisible = true;
            activated = <Button session={session} props={tile} />;
        }
        if (State.icon_mode) {
            tile.icon_shape = TextUntilNul(nativeSlice(card.icon_shape));
            tile.image = {
                asset_path: TextUntilNul(nativeSlice(card.icon)),
                alt_text: TextUntilNul(nativeSlice(card.title))
            };
            tile.icon_placement = State.list_mode
                ? IconPlacement.IconPlacementLeading
                : IconPlacement.IconPlacementAbove;
            if (State.list_mode) {
                tile.content_alignment = ContentAlignment.ContentAlignmentStart;
                tile.bounds.width = tile.bounds.width - 48.0 * scale;
            }
            if (State.has_reorder_handles) {
                tile.bounds.x = tile.bounds.x + 44.0 * scale;
                tile.bounds.width = tile.bounds.width - 44.0 * scale;
            }
        } else {
            let fill: Color = AppDark()
                ? { r: 33n, g: 47n, b: 44n, a: 255n }
                : { r: 249n, g: 252n, b: 250n, a: 255n };
            if (!State.cover_grid) {
                <Box
                    session={session}
                    props={{
                        key: key + u64(1n),
                        bounds: tile.bounds,
                        radius: 12.0 * scale,
                        fill: fill
                    }}
                />;
            }
            let preview = TextUntilNul(nativeSlice(card.preview));
            if (State.cover_grid && nativeAt(card.cover.portrait, 0n) !== 0n) {
                preview = TextUntilNul(nativeSlice(card.cover.portrait));
                if (
                    bounds.height < 480.0 * scale &&
                    bounds.width > bounds.height &&
                    nativeAt(card.cover.landscape, 0n) !== 0n
                ) {
                    preview = TextUntilNul(nativeSlice(card.cover.landscape));
                }
            }
            if (preview !== "") {
                <Image
                    session={session}
                    props={{
                        key: key + u64(2n),
                        asset_path: preview,
                        alt_text: TextUntilNul(nativeSlice(card.title)),
                        class_name: State.cover_grid ? State.image_class : 0n,
                        bounds: State.cover_grid
                            ? { x: x, y: y, width: card_width, height: picture_height }
                            : {
                                  x: x + gap,
                                  y: y + gap,
                                  width: card_width - gap * 2.0,
                                  height: picture_height
                              },
                        radius: State.cover_grid ? 20.0 * scale : 0.0,
                        fit: State.cover_grid
                            ? NativeImage.ImageFit.ImageFitCover
                            : NativeImage.ImageFit.ImageFitContain,
                        smooth: true
                    }}
                />;
            }
            if (State.cover_grid && nativeAt(card.cover.logo, 0n) !== 0n) {
                let logo_width = card_width - gap * 4.0;
                <Image
                    session={session}
                    props={{
                        key: key + u64(8n),
                        asset_path: TextUntilNul(nativeSlice(card.cover.logo)),
                        alt_text: TextUntilNul(nativeSlice(card.title)),
                        smooth: true,
                        fit: NativeImage.ImageFit.ImageFitContain,
                        bounds: {
                            x: x + gap * 2.0,
                            y: y + gap * 2.0,
                            width: logo_width,
                            height: logo_width * 0.36
                        }
                    }}
                />;
            }
            let title_y = State.cover_grid ? y + picture_height + 10.0 * scale : y + 188.0 * scale;
            <Text
                session={session}
                props={{
                    key: key + u64(3n),
                    bounds: {
                        x: x + 4.0 * scale,
                        y: title_y,
                        width: card_width - 8.0 * scale,
                        height: State.cover_grid ? 24.0 * scale : 32.0 * scale
                    },
                    text: TextUntilNul(nativeSlice(card.title)),
                    size: font + 2n,
                    wrap: NativeText.Wrap.TextWrapEllipsis
                }}
            />;
            if (State.cover_grid && !card.on_device && !State.hide_sizes) {
                let size_text = NewSizeText();
                if (AppsSize(card.bytes, nativeSlice(size_text))) {
                    <Text
                        session={session}
                        props={{
                            key: key + u64(9n),
                            text: TextUntilNul(nativeSlice(size_text)),
                            size: s32(14.0 * scale),
                            class_name: State.muted_class,
                            bounds: {
                                x: x + 4.0 * scale,
                                y: title_y,
                                width: card_width - 8.0 * scale,
                                height: 20.0 * scale
                            },
                            wrap: NativeText.Wrap.TextWrapNone
                        }}
                    />;
                }
            }
            tile.invisible = true;
        }
        let list_size = NewListSize();
        if (State.list_mode) {
            if (card.downloading) {
                tile.detail = AppsLabel(language, "downloading");
            } else if (
                !card.on_device &&
                !State.hide_sizes &&
                AppsSize(card.bytes, nativeSlice(list_size))
            ) {
                tile.detail = TextUntilNul(nativeSlice(list_size));
            }
        }
        if (!State.cover_grid) {
            activated = <Button session={session} props={tile} />;
        }
        if (activated) {
            if (download_first) {
                AppsDownloadOpen(card);
            } else {
                AppsAct("open", card.id);
            }
        }
        if (State.icon_mode && card.reorderable) {
            <Button
                session={session}
                props={{
                    key: NativeRules.AppReorderKey(TextUntilNul(nativeSlice(card.id))),
                    label: AppsLabel(language, "move_app"),
                    icon_shape: APP_REORDER,
                    icon_only: true,
                    disabled: card.disabled,
                    class_name: State.action_class,
                    emphasis: ButtonEmphasis.ButtonEmphasisGhost,
                    bounds: {
                        x: x,
                        y: y + (State.list_mode ? 10.0 * scale : 0.0),
                        width: 44.0 * scale,
                        height: 44.0 * scale
                    }
                }}
            />;
        }
        if (State.icon_mode) {
            let size_text = NewSizeText();
            if (card.downloading) {
                CopyCString(AppsLabel(language, "downloading"), nativeSlice(size_text));
            }
            if (
                !State.list_mode &&
                (card.downloading ||
                    (!card.on_device &&
                        !State.hide_sizes &&
                        AppsSize(card.bytes, nativeSlice(size_text))))
            ) {
                <Text
                    session={session}
                    props={{
                        key: key + u64(4n),
                        text: TextUntilNul(nativeSlice(size_text)),
                        size: s32(11.0 * scale),
                        bounds: {
                            x: x + 8.0 * scale,
                            y: y + card_height - 16.0 * scale,
                            width: card_width - 16.0 * scale,
                            height: 12.0 * scale
                        },
                        wrap: NativeText.Wrap.TextWrapNone,
                        align: TextAlign.TextAlignCenter,
                        class_name: State.muted_class
                    }}
                />;
            }
        }
        let action = AppsActionProps(
            key + u64(5n),
            card,
            State.action_class,
            {
                x: x + card_width - 40.0 * scale,
                y: y + (State.list_mode ? 14.0 * scale : 4.0 * scale),
                width: 36.0 * scale,
                height: 36.0 * scale
            },
            language,
            State.cover_grid
        );
        if (!card.on_device) {
            action.label = AppsLabel(language, "download");
            action.icon_shape = APP_DOWNLOAD;
            action.disabled = card.disabled || !AppsSupported(card, NativeRules.APPS_INSTALL);
            if ((<Button session={session} props={action} />)) {
                AppsDownloadOpen(card);
            }
        } else if ((<Button session={session} props={action} />)) {
            State.menu_id = card.id;
            State.menu_x = action.bounds.x;
            State.menu_y = action.bounds.y + action.bounds.height;
            if (
                card.update_available &&
                !card.update_seen &&
                AppsSupported(card, NativeRules.APPS_SEEN)
            ) {
                AppsAct("seen", card.id, card.available);
            }
        }
        if (card.update_available && !card.update_seen) {
            let dot = 8.0 * scale;
            <Box
                session={session}
                props={{
                    key: key + u64(6n),
                    radius: dot * 0.5,
                    fill: { r: 163n, g: 98n, b: 0n, a: 255n },
                    bounds: {
                        x: action.bounds.x + action.bounds.width - dot - 6.0 * scale,
                        y: action.bounds.y + 6.0 * scale,
                        width: dot,
                        height: dot
                    }
                }}
            />;
        }
    }
}
