import * as React from "react";

// 768px matches the Tailwind `md` breakpoint. Views below this width are
// treated as mobile and receive the collapsible (hamburger) sidebar.
const MOBILE_BREAKPOINT = 768;

/**
 * Returns true when the viewport width is below the mobile breakpoint.
 *
 * The hook listens to both a MediaQueryList change event and `window.innerWidth`
 * directly to handle cases where the browser fires resize events that the MQL
 * does not capture (e.g. some iOS Safari versions). Both sources are synced on
 * mount to prevent a flash of incorrect layout before the first event fires.
 *
 * Initial state is `undefined` (not yet measured); the !! coercion at the
 * return site converts this to `false` so consumers never receive undefined.
 */
export function useIsMobile() {
  const [isMobile, setIsMobile] = React.useState<boolean | undefined>(undefined);

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`);
    const onChange = () => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    };
    mql.addEventListener("change", onChange);
    setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  return !!isMobile;
}
