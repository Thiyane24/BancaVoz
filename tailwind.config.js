/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./bancavoz/web/**/*.html", "./bancavoz/web/static/**/*.js"],
  theme: {
    extend: {
      colors: {
        savanna: "#f7f1e8",
        terracotta: "#b75438",
        "terracotta-dark": "#8d3827",
        baobab: "#64775d",
        ink: "#28231f",
      },
      boxShadow: {
        paper: "0 16px 40px rgb(79 56 32 / 0.09)",
      },
    },
  },
  plugins: [],
};
