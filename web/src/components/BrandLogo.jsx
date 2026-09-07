import logoUrl from "../assets/pyclips-logo.png";

export default function BrandLogo({ size = 36, className = "" }) {
  return (
    <img
      src={logoUrl}
      alt=""
      aria-hidden="true"
      className={"brand-logo" + (className ? " " + className : "")}
      width={size}
      height={size}
      draggable={false}
    />
  );
}
