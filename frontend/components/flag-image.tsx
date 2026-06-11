/**
 * Contenedor con dimensiones fijas + overflow-hidden para garantizar que todas
 * las banderas se rendericen al mismo tamaño sin importar el aspect ratio
 * original de la imagen (Suiza 1:1, Qatar 28:11, Nepal 4:3, etc.).
 *
 * Tamaños definidos según DESIGN.md § Flags.
 */

type Size = "xs" | "md" | "lg";

const SIZES: Record<Size, { box: string; src: string; radius: string }> = {
  xs: { box: "h-5 w-[30px]",      src: "w40", radius: "rounded-[2px]" }, // picker list / trigger
  md: { box: "h-10 w-[60px]",     src: "w80", radius: "rounded-[4px]" }, // match cards
  lg: { box: "h-[52px] w-[78px]", src: "w80", radius: "rounded-[6px]" }, // prediction header
};

interface Props {
  iso2: string;
  name: string;
  size?: Size;
  className?: string;
}

export default function FlagImage({ iso2, name, size = "md", className = "" }: Props) {
  const { box, src, radius } = SIZES[size];
  return (
    <span
      className={`block shrink-0 overflow-hidden ${box} ${radius} ${className}`}
    >
      <img
        src={`https://flagcdn.com/${src}/${iso2}.png`}
        alt={name}
        className="h-full w-full object-cover"
      />
    </span>
  );
}
