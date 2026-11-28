import { AppLauncherItem, AppLauncherProps, AppLauncherState } from "apps/launcher";
import { AppLauncherScreen } from "apps/tsx/launcher";
import { AppGameHome, AppGameHud } from "apps/tsx/game_hud";
import { Color } from "kryon/drawing_props";
import { Rectangle } from "kryon/geometry";
import { Session } from "kryon/session";

// Independent public imports share the exact checked native Kryon types.
export function TypedScreen(session: Session, bounds: Rectangle, fill: Color): boolean {
    let state: AppLauncherState = {};
    const props: AppLauncherProps = { bounds: bounds, scale: 1.0, locale: "en" };
    const items: [AppLauncherItem] = [{ title: "Clock" }];
    AppLauncherScreen(session, nativeRef(state), props, nativeSlice(items));
    AppGameHud(session, { key: 100n, bounds: bounds, dew_text: "10" });
    AppGameHome(session, { key: 200n, bounds: bounds, label: "Home" });
    return fill.a === 255n && props.bounds.width === bounds.width;
}
