// Typed UI composition. Native state and effects remain in connection.zi.
import * as NativeText from "kryon/text";
import { AppCoversPalette } from "appearance";
import {
    APP_CONNECTION_ALLOWED,
    APP_CONNECTION_OFFLINE,
    APP_CONNECTION_UNDECIDED
} from "connection";
import { ButtonEmphasis, ButtonTone } from "kryon/control_props";
import { Rectangle } from "kryon/geometry";
import { Session } from "kryon/session";
import { Box } from "kryon/tsx/box";
import { Button } from "kryon/tsx/button";
import { Text } from "kryon/tsx/text";
import { WidgetPaletteUse, WidgetPaletteRestore } from "kryon/widget_palette";
import { AppsLabel } from "words";

// The host suspends its underlying screen while asking. Rendering performs
// no request and grants no permission; only the returned answer is persisted.
export function AppConnectionNotice(
    session: Session,
    bounds: Rectangle,
    locale: string,
    origin: string,
    key: u64
): s32 {
    WidgetPaletteUse(session, AppCoversPalette());
    const choice = ConnectionNotice(session, bounds, locale, origin, key);
    WidgetPaletteRestore(session);
    return choice;
}

function ConnectionNotice(
    session: Session,
    bounds: Rectangle,
    locale: string,
    origin: string,
    key: u64
): s32 {
    <Box
        session={session}
        props={{ key: key, bounds: bounds, fill: { r: 17n, g: 18n, b: 35n, a: 255n } }}
    />;
    let width = bounds.width - 32.0 < 480.0 ? bounds.width - 32.0 : 480.0;
    let height = bounds.height - 24.0 < 292.0 ? bounds.height - 24.0 : 292.0;
    let x = bounds.x + (bounds.width - width) / 2.0;
    let y = bounds.y + (bounds.height - height) / 2.0;
    <Box
        session={session}
        props={{
            key: key + 1n,
            bounds: { x: x, y: y, width: width, height: height },
            fill: { r: 32n, g: 34n, b: 56n, a: 255n },
            border: { r: 65n, g: 66n, b: 96n, a: 255n },
            radius: 18.0
        }}
    />;
    <Text
        session={session}
        props={{
            key: key + 2n,
            text: AppsLabel(locale, "allow_content_title"),
            size: 22n,
            wrap: NativeText.Wrap.TextWrapAuto,
            bounds: { x: x + 20.0, y: y + 18.0, width: width - 40.0, height: 56.0 }
        }}
    />;
    <Text
        session={session}
        props={{
            key: key + 3n,
            text: AppsLabel(locale, "allow_content_description"),
            size: 16n,
            wrap: NativeText.Wrap.TextWrapAuto,
            bounds: { x: x + 20.0, y: y + 82.0, width: width - 40.0, height: height - 166.0 }
        }}
    />;
    let button_width = (width - 52.0) / 2.0;
    if (
        (
            <Button
                session={session}
                props={{
                    key: key + 5n,
                    id: 1n,
                    label: AppsLabel(locale, "stay_offline"),
                    bounds: {
                        x: x + 20.0,
                        y: y + height - 52.0,
                        width: button_width,
                        height: 40.0
                    },
                    tone: ButtonTone.ButtonToneNeutral,
                    emphasis: ButtonEmphasis.ButtonEmphasisSoft
                }}
            />
        )
    ) {
        return APP_CONNECTION_OFFLINE;
    }
    if (
        (
            <Button
                session={session}
                props={{
                    key: key + 6n,
                    id: 2n,
                    label: AppsLabel(locale, "allow_content"),
                    bounds: {
                        x: x + 32.0 + button_width,
                        y: y + height - 52.0,
                        width: button_width,
                        height: 40.0
                    },
                    tone: ButtonTone.ButtonToneAccent
                }}
            />
        )
    ) {
        return APP_CONNECTION_ALLOWED;
    }
    return APP_CONNECTION_UNDECIDED;
}
