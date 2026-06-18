declare module "react" {
  export const StrictMode: (props: { children?: unknown }) => unknown;
  export function createElement(type: unknown, props?: unknown, ...children: unknown[]): unknown;
  const React: {
    StrictMode: typeof StrictMode;
    createElement: typeof createElement;
  };
  export default React;
}

declare module "react-dom/client" {
  export function createRoot(element: Element): {
    render(children: unknown): void;
  };
}

declare module "react/jsx-runtime" {
  export const Fragment: unknown;
  export function jsx(type: unknown, props: unknown, key?: unknown): unknown;
  export function jsxs(type: unknown, props: unknown, key?: unknown): unknown;
}

declare namespace JSX {
  interface IntrinsicElements {
    [elementName: string]: Record<string, unknown>;
  }
}
