/**
 * CoCo mascot (same as logo symbol). Used in Hero and Nav.
 */
import { CatPawIcon } from "./CatPawIcon";

interface CocoMascotProps {
  size?: number;
  className?: string;
}

export function CocoMascot({ size = 80, className = "" }: CocoMascotProps) {
  return <CatPawIcon size={size} className={className} />;
}
