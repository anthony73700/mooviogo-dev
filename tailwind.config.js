/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./apps/**/templates/**/*.html",
    "./apps/**/static/**/*.js",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // ── Mooviogo Nightlife palette ──
        // Deep night background tones
        night: {
          950: "#06040E",  // deepest black-violet
          900: "#0A0818",  // app bg
          850: "#0F0C20",  // card bg
          800: "#15112B",  // elevated
          700: "#1E1738",  // border
          600: "#2A2148",  // hover
        },
        // Primary neon — electric magenta/violet
        neon: {
          50:  "#FCE7FF",
          100: "#F7C8FF",
          200: "#EA9BFF",
          300: "#D770FF",
          400: "#C04DFF",
          500: "#A832F5",   // primary brand
          600: "#8B1FD9",
          700: "#6E18AD",
          800: "#511381",
          900: "#360D55",
        },
        // Secondary — hot pink / fuchsia
        flamingo: {
          50:  "#FFE7F1",
          100: "#FFC2DE",
          200: "#FF9CCC",
          300: "#FF6FAF",
          400: "#FF4D9A",
          500: "#F31C7F",   // accent
          600: "#CC0A6A",
          700: "#9F0855",
          800: "#760640",
          900: "#4F052B",
        },
        // Tertiary — neon cyan / electric blue
        electric: {
          50:  "#DBFEFF",
          100: "#A6FBFF",
          200: "#73F5FF",
          300: "#43ECFB",
          400: "#21DCEE",   // accent
          500: "#06C5DA",
          600: "#0399B0",
          700: "#04778B",
          800: "#085866",
          900: "#093E4A",
        },
        // Warm accent — sunset orange (kept from legacy palette)
        sunset: {
          400: "#FF8A66",
          500: "#FF6A4D",
          600: "#E05030",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["'Bricolage Grotesque'", "Inter", "sans-serif"],
      },
      borderRadius: {
        "4xl": "2rem",
        "5xl": "2.5rem",
      },
      boxShadow: {
        "neon-sm":   "0 4px 14px rgba(0,0,0,0.32)",
        "neon":      "0 10px 28px rgba(0,0,0,0.42)",
        "neon-lg":   "0 18px 48px rgba(0,0,0,0.5)",
        "flamingo":  "0 8px 28px rgba(0,0,0,0.4)",
        "electric":  "0 8px 28px rgba(0,0,0,0.36)",
        "glow":      "0 0 0 1px rgba(255,255,255,0.06), 0 12px 40px -10px rgba(0,0,0,0.65)",
        // Apple-style elevation system
        "card":      "0 1px 2px rgba(0,0,0,0.5), 0 8px 32px -8px rgba(0,0,0,0.6)",
        "card-hover":"0 2px 4px rgba(0,0,0,0.5), 0 28px 56px -18px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.06)",
        "elev-1":    "0 1px 2px rgba(0,0,0,0.4)",
        "elev-2":    "0 2px 8px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.2)",
        "elev-3":    "0 8px 24px rgba(0,0,0,0.5), 0 2px 4px rgba(0,0,0,0.2)",
        "elev-4":    "0 24px 48px rgba(0,0,0,0.6), 0 8px 16px rgba(0,0,0,0.3)",
        "dice":      "0 0 0 1px rgba(255,255,255,0.08), 0 24px 60px -16px rgba(0,0,0,0.55)",
        "fever":     "0 28px 70px -24px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.08)",
      },
      transitionTimingFunction: {
        // Linear/Apple smooth easings
        "spring":    "cubic-bezier(0.22, 1, 0.36, 1)",
        "smooth":    "cubic-bezier(0.4, 0, 0.2, 1)",
        "snappy":    "cubic-bezier(0.34, 1.56, 0.64, 1)",
      },
      backgroundImage: {
        "grad-brand":   "linear-gradient(135deg,#1a2230 0%,#10161f 55%,#0a0f17 100%)",
        "grad-night":   "linear-gradient(180deg,#0A0818 0%,#06040E 100%)",
        "grad-aurora":  "radial-gradient(1200px 600px at 10% -10%, rgba(140,160,200,0.10), transparent 60%), radial-gradient(900px 500px at 90% 10%, rgba(180,200,225,0.08), transparent 60%), radial-gradient(700px 400px at 50% 100%, rgba(120,150,200,0.08), transparent 60%)",
        "grad-card":    "linear-gradient(180deg,rgba(21,17,43,0.85),rgba(10,8,24,0.95))",
        "grad-text":    "linear-gradient(90deg,#ffffff 0%,#e8eef8 50%,#aab6cc 100%)",
      },
      keyframes: {
        "aurora-pan": {
          "0%,100%": { backgroundPosition: "0% 50%" },
          "50%":     { backgroundPosition: "100% 50%" },
        },
        "float-y": {
          "0%,100%": { transform: "translateY(0)" },
          "50%":     { transform: "translateY(-20px)" },
        },
        "pulse-neon": {
          "0%,100%": { boxShadow: "0 0 0 0 rgba(168,50,245,0.6)" },
          "50%":     { boxShadow: "0 0 0 12px rgba(168,50,245,0)" },
        },
        "shimmer": {
          "0%":   { backgroundPosition: "-400px 0" },
          "100%": { backgroundPosition: "400px 0" },
        },
        "slide-up": {
          "from": { opacity: "0", transform: "translateY(20px)" },
          "to":   { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "aurora":     "aurora-pan 18s ease-in-out infinite",
        "float-y":    "float-y 8s ease-in-out infinite",
        "pulse-neon": "pulse-neon 2.4s ease-out infinite",
        "shimmer":    "shimmer 4s linear infinite",
        "slide-up":   "slide-up 0.6s cubic-bezier(0.22,1,0.36,1) both",
      },
    },
  },
  plugins: [
    require("@tailwindcss/forms"),
    require("@tailwindcss/typography"),
    require("@tailwindcss/aspect-ratio"),
  ],
};
