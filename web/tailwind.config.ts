import type { Config } from "tailwindcss";

/**
 * Design tokens from the Stitch MCP project "Nucleus Liquid Glass Dashboard"
 * (project 3532817977086505409), design system **Hyper-Modern Neon**
 * (assets/201346a998544eeea6ab5883533cc45c). Ported verbatim from the generated
 * screens so the storefront and the dashboard share one system.
 *
 * Do not hand-edit values here -- change the design system in Stitch and re-pull.
 *
 * The sibling system "Kinetic Noir" shares the dark base, Anybody/Hanken
 * Grotesk pairing and the lime primary; it differs only in the secondary accent
 * (#ff5f00 orange rather than #00f2ff cyan) and a tighter roundness. Switching
 * is a change to `electric-cyan` and `borderRadius` here, nothing more.
 */
const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // -- the void ----------------------------------------------------
        "pure-black": "#000000",
        background: "#000000",
        "on-background": "#e2e4d3",

        // -- neon accents ------------------------------------------------
        "electric-lime": "#d4ff5b",
        "electric-cyan": "#00f2ff",

        // -- dark glass --------------------------------------------------
        "glass-dark": "rgba(255, 255, 255, 0.04)",
        "glass-border": "rgba(255, 255, 255, 0.12)",

        // -- surfaces ----------------------------------------------------
        surface: "#12140a",
        "surface-dim": "#12140a",
        "surface-bright": "#383a2e",
        "surface-container-lowest": "#0d0f06",
        "surface-container-low": "#1a1d12",
        "surface-container": "#1e2116",
        "surface-container-high": "#292b20",
        "surface-container-highest": "#33362a",
        "surface-variant": "#33362a",
        "surface-tint": "#acd534",
        "on-surface": "#e2e4d3",
        "on-surface-variant": "#c5c9b0",
        "inverse-surface": "#e2e4d3",
        "inverse-on-surface": "#2f3226",
        outline: "#8e937c",
        "outline-variant": "#444936",

        /* `primary` is white and `secondary` is the cyan accent, so the
         * semantic classes already written across the app (text-primary for
         * headings, text-secondary for agent features) stay correct on a dark
         * ground instead of every file needing a rename. */
        primary: "#ffffff",
        "on-primary": "#283500",
        "primary-container": "#c8f24f",
        "on-primary-container": "#546d00",
        "inverse-primary": "#4f6600",
        "primary-fixed": "#c8f24f",
        "primary-fixed-dim": "#acd534",
        "on-primary-fixed": "#161f00",
        "on-primary-fixed-variant": "#3b4d00",

        secondary: "#00f2ff",
        "on-secondary": "#00363a",
        "secondary-container": "#00f1fe",
        "on-secondary-container": "#006a70",
        "secondary-fixed": "#74f5ff",
        "secondary-fixed-dim": "#00dbe7",
        "on-secondary-fixed": "#002022",
        "on-secondary-fixed-variant": "#004f54",

        tertiary: "#ffffff",
        "on-tertiary": "#3a2c3b",
        "tertiary-container": "#f2dcf0",
        "on-tertiary-container": "#d4ff5b",
        "tertiary-fixed": "#f2dcf0",
        "tertiary-fixed-dim": "#d5c0d4",
        "on-tertiary-fixed": "#241726",
        "on-tertiary-fixed-variant": "#514252",

        error: "#ffb4ab",
        "on-error": "#690005",
        "error-container": "#93000a",
        "on-error-container": "#ffdad6",
      },

      // Extreme circularity: containers 24px+, interactive elements pill.
      borderRadius: {
        sm: "0.5rem",
        DEFAULT: "1rem",
        md: "1.5rem",
        lg: "2rem",
        xl: "1.5rem",
        "2xl": "2rem",
        full: "9999px",
      },

      spacing: {
        unit: "8px",
        base: "8px",
        gutter: "24px",
        "margin-mobile": "20px",
        "margin-desktop": "80px",
        "section-gap": "120px",
        "card-padding": "32px",
        "stack-sm": "12px",
        "stack-md": "24px",
        "stack-lg": "48px",
        "container-max": "1440px",
      },
      maxWidth: { "container-max": "1440px" },

      fontFamily: {
        // Anybody: structural, athletic impact for display and labels
        "display-xl": ["Anybody", "system-ui", "sans-serif"],
        "display-lg": ["Anybody", "system-ui", "sans-serif"],
        "headline-lg": ["Anybody", "system-ui", "sans-serif"],
        "headline-lg-mobile": ["Anybody", "system-ui", "sans-serif"],
        "label-caps": ["Anybody", "system-ui", "sans-serif"],
        "label-sm": ["Anybody", "system-ui", "sans-serif"],
        // Hanken Grotesk: technical, modern readability for functional copy
        "title-md": ["Hanken Grotesk", "system-ui", "sans-serif"],
        "body-md": ["Hanken Grotesk", "system-ui", "sans-serif"],
        "body-sm": ["Hanken Grotesk", "system-ui", "sans-serif"],
        "cta-button": ["Anybody", "system-ui", "sans-serif"],
      },

      // Generous tracking throughout -- luxury/expansive, not aggressive/compact.
      fontSize: {
        "display-xl": ["72px", { lineHeight: "1.0", letterSpacing: "0.02em", fontWeight: "800" }],
        "display-lg": ["72px", { lineHeight: "1.0", letterSpacing: "0.02em", fontWeight: "800" }],
        "headline-lg": ["48px", { lineHeight: "1.1", letterSpacing: "0.01em", fontWeight: "800" }],
        "headline-lg-mobile": ["32px", { lineHeight: "1.1", letterSpacing: "0.01em", fontWeight: "800" }],
        "title-md": ["20px", { lineHeight: "1.4", letterSpacing: "0.02em", fontWeight: "700" }],
        "body-md": ["16px", { lineHeight: "1.6", letterSpacing: "0.01em", fontWeight: "400" }],
        "body-sm": ["14px", { lineHeight: "1.5", letterSpacing: "0.01em", fontWeight: "400" }],
        "label-caps": ["12px", { lineHeight: "1.0", letterSpacing: "0.15em", fontWeight: "700" }],
        "label-sm": ["12px", { lineHeight: "1.0", letterSpacing: "0.15em", fontWeight: "700" }],
        "cta-button": ["12px", { lineHeight: "1.0", letterSpacing: "0.15em", fontWeight: "700" }],
      },

      // Light emission replaces drop shadows.
      boxShadow: {
        "glow-lime": "0 0 15px rgba(212,255,91,0.2)",
        "glow-lime-strong": "0 0 20px rgba(212,255,91,0.5)",
        "glow-cyan": "0 0 15px rgba(0,242,255,0.2)",
        "glow-cyan-strong": "0 0 20px rgba(0,242,255,0.4)",
        "rail-cyan": "5px 0 15px rgba(0,242,255,0.1)",
      },

      scale: { "98": "0.98" },
    },
  },
  plugins: [],
};

export default config;
