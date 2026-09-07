import "./SurfaceFrame.css";

const VARIANTS = {
  primary: "pc-frame--primary",
  store: "pc-frame--store",
  ghost: "pc-frame--ghost",
  card: "pc-frame--card",
};

export default function SurfaceFrame({
  children,
  variant = "primary",
  size = "md",
  full = false,
  className = "",
}) {
  const classes = [
    "pc-frame",
    VARIANTS[variant] || VARIANTS.primary,
    size === "lg" ? "pc-frame--lg" : size === "sm" ? "pc-frame--sm" : "",
    full ? "pc-frame--full" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return <span className={classes}>{children}</span>;
}
