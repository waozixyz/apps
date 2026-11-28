import * as State from "native_behavior";
import { NativeDrawContents } from "native_behavior";
import { Session } from "kryon/session";
import * as NativeScroll from "kryon/scroll";
import { Scroll } from "kryon/tsx/scroll";

// The real host fixture exercises the controller under the public scroll scope.
export function NativeDrawView(session: Session, icon_mode: boolean, quiet: boolean): boolean {
    if (!icon_mode) {
        return NativeDrawContents(quiet);
    }
    let ran = false;
    const ran_ref = nativeRef(ran);
    const group = Scroll({
        session: session,
        props: {
            key: u64(99),
            bounds: { x: 0.0, y: 0.0, width: 480.0, height: 88.0 },
            content_height: 200n
        },
        children: (group: NativeScroll.ScrollResult): void => {
            State.native_controller.app.bounds = {
                x: group.content.x,
                y: group.content.y,
                width: group.content.width,
                height: 88.0
            };
            nativeDeref(ran_ref) = NativeDrawContents(quiet);
        }
    });
    return group.opened && ran;
}
