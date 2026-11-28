// Typed UI composition. Native state and effects remain in launcher.zi.
import * as NativeScroll from "kryon/scroll";
import { ButtonEmphasis, ButtonTone } from "kryon/control_props";
import { Session } from "kryon/session";
import { Scroll } from "kryon/tsx/scroll";
import * as NativeTextField from "kryon/text_field";
import { Button } from "kryon/tsx/button";
import { Separator } from "kryon/tsx/separator";
import { Text } from "kryon/tsx/text";
import { ControlledTextField } from "kryon/tsx/text_field";
import {
    APP_LAUNCHER_GRID,
    APP_LAUNCHER_LIST,
    AppLauncherFilter,
    AppLauncherItem,
    AppLauncherProps,
    AppLauncherReplace,
    AppLauncherResult,
    AppLauncherState,
    NewSnapshot,
    AppLauncherHasCards
} from "launcher";
import { CopyCString } from "std/c_string";
import { TextUntilNul } from "std/text_buffer";
import { AppsLabel } from "words";

// Call once per frame after the host's title/account bar. Cards run inside
// the scroll scope; their ordinary overlays retain the same host routing.
export function AppLauncherScreen(
    session: Session,
    state: NativeRef<AppLauncherState>,
    props: AppLauncherProps,
    items: AppLauncherItem[]
): AppLauncherResult {
    let result: AppLauncherResult = {};
    let scale = props.scale > 0.0 ? props.scale : 1.0;
    let bounds = props.bounds;
    let field_height = 48.0 * scale;
    result.search_bounds = {
        x: bounds.x,
        y: bounds.y,
        width: bounds.width - 104.0 * scale,
        height: field_height
    };
    let snapshot = NewSnapshot();
    for (let index = s32(0n); index <= 127n; index += s32(1)) {
        nativeSet(snapshot, index, nativeAt(state.query, index));
    }
    let field = (
        <ControlledTextField
            session={session}
            props={{
                key: u64(30001n),
                focus_id: 6791n,
                bounds: result.search_bounds,
                value: TextUntilNul(nativeSlice(snapshot)),
                label: AppsLabel(props.locale, "search"),
                placeholder: AppsLabel(props.locale, "search"),
                clear_label: AppsLabel(props.locale, "clear_search"),
                class_name: props.search_class,
                cursor: state.cursor,
                anchor: state.anchor,
                scroll_x: state.scroll_x,
                focused: state.focused,
                max_bytes: 127n,
                max_codepoints: 80n,
                scale: scale,
                input: state.focused ? props.input : {}
            }}
        />
    );
    if (field.edit.changed) {
        AppLauncherReplace(nativeSlice(state.query), field.edit);
        state.scroll = 0n;
    }
    state.cursor = field.cursor;
    state.anchor = field.anchor;
    state.scroll_x = field.scroll_x;
    state.focused = field.focused && !field.escaped;
    result.clipboard_write = field.clipboard_write;
    if (field.clipboard_write) {
        CopyCString(field.clipboard_text, nativeSlice(result.clipboard_text));
    }
    for (let mode = s32(0n); mode <= 1n; mode += s32(1)) {
        let grid = mode === 1n;
        if (
            (
                <Button
                    session={session}
                    props={{
                        key: u64(30002n + mode),
                        label: AppsLabel(props.locale, grid ? "grid_view" : "list_view"),
                        icon_shape: grid ? APP_LAUNCHER_GRID : APP_LAUNCHER_LIST,
                        icon_only: true,
                        selected: state.grid === grid,
                        tone:
                            state.grid === grid
                                ? ButtonTone.ButtonToneAccent
                                : ButtonTone.ButtonToneNeutral,
                        emphasis: ButtonEmphasis.ButtonEmphasisSoft,
                        bounds: {
                            x:
                                bounds.x +
                                bounds.width -
                                96.0 * scale +
                                float32(mode) * 52.0 * scale,
                            y: bounds.y + 2.0 * scale,
                            width: 44.0 * scale,
                            height: 44.0 * scale
                        }
                    }}
                />
            ) &&
            state.grid !== grid
        ) {
            state.grid = grid;
            state.scroll = 0n;
            result.changed = true;
        }
    }
    AppLauncherFilter(state, items);
    result.columns = 1n;
    result.tile_height = s32(64.0 * scale);
    result.gap = s32(4.0 * scale);
    if (state.grid) {
        result.tile_height = s32(88.0 * scale);
        result.gap = s32(12.0 * scale);
        result.columns = s32(
            (bounds.width + float32(result.gap)) / (140.0 * scale + float32(result.gap))
        );
        if (result.columns < 1n) {
            result.columns = 1n;
        }
        if (result.columns > 6n) {
            result.columns = 6n;
        }
    }
    let sections = props.empty_favorites || state.favorites > 0n;
    let heading = sections ? s32(36.0 * scale) : 0n;
    let more = state.count - state.favorites;
    let stride = result.tile_height + result.gap;
    let favorites_height =
        heading + ((state.favorites + result.columns - 1n) / result.columns) * stride;
    let library_height = heading + ((more + result.columns - 1n) / result.columns) * stride;
    if (props.empty_favorites && more === 0n) {
        library_height = library_height + s32(64.0 * scale);
    }
    if (state.count === 0n) {
        library_height = library_height + s32(64.0 * scale);
    }
    let top = bounds.y + 68.0 * scale;
    if (props.status.count > 0n) {
        <Text
            session={session}
            props={{
                key: u64(30004n),
                text: props.status,
                class_name: props.muted_class,
                bounds: { x: bounds.x, y: top, width: bounds.width, height: 44.0 * scale }
            }}
        />;
        top = top + 48.0 * scale;
    }
    result.scroll_bounds = {
        x: bounds.x,
        y: top,
        width: bounds.width,
        height: bounds.y + bounds.height - top
    };
    const result_ref = nativeRef(result);
    const props_ref = nativeRef(props);
    const scrolled = Scroll({
        session: session,
        props: {
            key: u64(30005n),
            bounds: result.scroll_bounds,
            scale: scale,
            scroll_offset: state.scroll,
            content_height: favorites_height + library_height
        },
        children: (scrolled: NativeScroll.ScrollResult): void => {
            nativeDeref(state).scroll = scrolled.scroll_offset;
            let area = scrolled.content;
            nativeDeref(result_ref).favorites_bounds = {
                x: area.x,
                y: area.y,
                width: area.width,
                height: float32(favorites_height)
            };
            nativeDeref(result_ref).library_bounds = {
                x: area.x,
                y: area.y + float32(favorites_height),
                width: area.width,
                height: float32(library_height)
            };
            nativeDeref(result_ref).cards_bounds = {
                x: area.x,
                y: area.y + float32(heading),
                width: area.width,
                height: float32(favorites_height + library_height - heading)
            };
            if (sections) {
                <Text
                    session={session}
                    props={{
                        key: u64(30006n),
                        text: AppsLabel(props.locale, "favorites"),
                        class_name: props.heading_class,
                        bounds: { x: area.x, y: area.y, width: area.width, height: 28.0 * scale }
                    }}
                />;
                <Separator
                    session={session}
                    props={{
                        key: u64(30009n),
                        bounds: {
                            x: area.x,
                            y: nativeDeref(result_ref).library_bounds.y + 28.0 * scale,
                            width: area.width,
                            height: 8.0 * scale
                        }
                    }}
                />;
            }
            let input: NativeTextField.Input = state.focused ? {} : nativeDeref(props_ref).input;
            if (AppLauncherHasCards(props) && state.count > 0n) {
                nativeDeref(result_ref).ran = nativeDeref(props_ref).cards(
                    nativeDeref(props_ref).context,
                    nativeSlice(nativeDeref(state).visible, 0n, nativeDeref(state).count),
                    nativeDeref(result_ref).cards_bounds,
                    input,
                    sections ? state.favorites : -1n,
                    nativeDeref(result_ref).columns
                );
            } else {
                <Text
                    session={session}
                    props={{
                        key: u64(30008n),
                        text: AppsLabel(props.locale, "no_results"),
                        class_name: props.muted_class,
                        bounds: nativeDeref(result_ref).cards_bounds
                    }}
                />;
                nativeDeref(result_ref).ran = true;
            }
        }
    });
    result.scrolled = scrolled;
    if (!scrolled.opened) {
        state.scroll = scrolled.scroll_offset;
    }
    return result;
}
