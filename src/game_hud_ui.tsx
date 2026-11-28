// Typed UI composition with native props from game_hud.zi.
import * as NativeImage from "kryon/image";
import * as NativeText from "kryon/text";
import { AppGameHomeProps, AppGameHudProps } from "game_hud";
import { ButtonEmphasis } from "kryon/control_props";
import { Rectangle } from "kryon/geometry";
import { Session } from "kryon/session";
import { TextAlign } from "kryon/text_align";
import { Box } from "kryon/tsx/box";
import { Button } from "kryon/tsx/button";
import { Image } from "kryon/tsx/image";
import { Text } from "kryon/tsx/text";
import { WidgetPaletteRestore, WidgetPaletteUse } from "kryon/widget_palette";

// Reserves key..key+7. Returns 0, 1 (Profile), or 2 (Dew).
export function AppGameHud(session: Session, props: AppGameHudProps): s32 {
    if (props.bounds.width <= 0.0 || props.bounds.height <= 0.0) {
        return 0n;
    }
    WidgetPaletteUse(session, {
        background: 0x111316ffn,
        base: 0x2a2722ffn,
        text: 0xffeec1ffn,
        selected: 0xad843effn,
        selected_text: 0xffeec1ffn,
        border: 0x66522bffn,
        danger: 0xdc655bffn,
        warning: 0xdeb56dffn,
        success: 0x79b18bffn
    });
    const action = GameHud(session, props);
    WidgetPaletteRestore(session);
    return action;
}

function GameHud(session: Session, props: AppGameHudProps): s32 {
    let area = props.bounds;
    if (area.height > 64.0) {
        area.height = 64.0;
    }
    let pad = area.height * 0.12;
    if (pad > area.width * 0.04) {
        pad = area.width * 0.04;
    }
    let size = area.height - pad * 2.0;
    if (size > area.width * 0.22) {
        size = area.width * 0.22;
    }
    let bevel = pad * 0.25;
    <Box
        session={session}
        props={{
            key: props.key + 5n,
            bounds: area,
            fill: { r: 222n, g: 188n, b: 109n, a: 255n },
            fill_bottom: { r: 84n, g: 57n, b: 26n, a: 255n },
            has_fill_bottom: true,
            border: { r: 239n, g: 211n, b: 146n, a: 255n },
            radius: area.height * 0.2
        }}
    />;
    <Box
        session={session}
        props={{
            key: props.key + 6n,
            bounds: {
                x: area.x + bevel,
                y: area.y + bevel,
                width: area.width - bevel * 2.0,
                height: area.height - bevel * 2.0
            },
            fill: { r: 42n, g: 39n, b: 34n, a: 255n },
            fill_bottom: { r: 17n, g: 19n, b: 22n, a: 255n },
            has_fill_bottom: true,
            border: { r: 102n, g: 78n, b: 43n, a: 255n },
            radius: area.height * 0.18
        }}
    />;
    let profile: Rectangle = {
        x: area.x + area.width - pad - size,
        y: area.y + (area.height - size) / 2.0,
        width: size,
        height: size
    };
    <Box
        session={session}
        props={{
            key: props.key + 7n,
            bounds: {
                x: profile.x - bevel,
                y: profile.y - bevel,
                width: size + bevel * 2.0,
                height: size + bevel * 2.0
            },
            fill: { r: 173n, g: 132n, b: 62n, a: 255n },
            border: { r: 238n, g: 209n, b: 142n, a: 255n },
            radius: size / 2.0 + bevel
        }}
    />;
    <Image
        session={session}
        props={{
            key: props.key + 1n,
            bounds: profile,
            asset_path:
                props.profile_image.count > 0n ? props.profile_image : "assets/hud/profile.webp",
            preview_path: "assets/hud/profile.webp",
            fit: NativeImage.ImageFit.ImageFitContain,
            smooth: true,
            radius: size / 2.0
        }}
    />;
    let profile_action = (
        <Button
            session={session}
            props={{
                key: props.key,
                bounds: profile,
                label: props.profile_label,
                invisible: true,
                circle: true
            }}
        />
    );
    let jewel: Rectangle = { x: area.x + pad, y: profile.y, width: size, height: size };
    <Image
        session={session}
        props={{
            key: props.key + 3n,
            bounds: jewel,
            asset_path: props.dew_image.count > 0n ? props.dew_image : "assets/hud/dew.webp",
            preview_path: "assets/hud/dew.webp",
            fit: NativeImage.ImageFit.ImageFitContain,
            smooth: true
        }}
    />;
    let text_x = jewel.x + size + pad * 0.5;
    <Text
        session={session}
        props={{
            key: props.key + 4n,
            bounds: { x: text_x, y: area.y, width: profile.x - pad - text_x, height: area.height },
            text: props.dew_text,
            size: 18n,
            vertical_align: TextAlign.TextAlignCenter,
            wrap: NativeText.Wrap.TextWrapEllipsis
        }}
    />;
    let dew_action = (
        <Button
            session={session}
            props={{
                key: props.key + 2n,
                bounds: {
                    x: area.x,
                    y: area.y,
                    width: profile.x - pad * 0.5 - area.x,
                    height: area.height
                },
                label: props.dew_label,
                invisible: true
            }}
        />
    );
    if (profile_action) {
        return 1n;
    }
    if (dew_action) {
        return 2n;
    }
    return 0n;
}

// Optional collection navigation; standalone games do not compose it.
export function AppGameHome(session: Session, props: AppGameHomeProps): boolean {
    WidgetPaletteUse(session, {
        background: 0x111316ffn,
        base: 0x2a2722ffn,
        text: 0xffeec1ffn,
        selected: 0xad843effn,
        selected_text: 0xffeec1ffn,
        border: 0x66522bffn
    });
    const clicked = GameHome(session, props);
    WidgetPaletteRestore(session);
    return clicked;
}

function GameHome(session: Session, props: AppGameHomeProps): boolean {
    return (
        <Button
            session={session}
            props={{
                key: props.key,
                bounds: props.bounds,
                label: props.label,
                icon_shape: "S1.8rr:M3 11L12 3L21 11M5 10V21H10V15H14V21H19V10",
                emphasis: ButtonEmphasis.ButtonEmphasisSoft
            }}
        />
    );
}
