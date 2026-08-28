// React only suppresses its "not configured to support act(...)" warning when
// the environment declares itself an act environment. Without this flag every
// component test that renders through `act` prints the warning on each update,
// which buries the output that matters -- an assertion failure ends up several
// screens below a wall of identical notices.
//
// Setting it is also the documented contract, not a workaround: it tells React
// that updates are being driven deliberately by the test rather than escaping
// unbatched, which is exactly what these tests do.
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

declare global {
  var IS_REACT_ACT_ENVIRONMENT: boolean;
}

export {};
