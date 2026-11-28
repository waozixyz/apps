import { AppCoversPalette } from "appearance";
import { Rectangle } from "kryon/geometry";
import { ColorFromPacked } from "kryon/drawing_props";
import { Session } from "kryon/session";
import { Box } from "kryon/tsx/box";

// Shared opaque navigation strip above a mounted game.
export function AppHostHomeStrip(session: Session, bounds: Rectangle): void {
    <Box
        session={session}
        props={{
            key: u64(49190),
            bounds: { x: bounds.x, y: bounds.y, width: bounds.width, height: 64.0 },
            fill: ColorFromPacked(AppCoversPalette().background)
        }}
    />;
}
