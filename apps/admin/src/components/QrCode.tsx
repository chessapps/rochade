import { QRCodeSVG } from "qrcode.react";

/** The device token as the thing a phone scans. SVG, so it prints sharp at any size. */
export function QrCode({ value, size = 240 }: { value: string; size?: number }) {
  return (
    <QRCodeSVG
      value={value}
      size={size}
      level="M"
      marginSize={2}
      className="rounded-lg bg-white"
      role="img"
      aria-label="QR code admitting a phone to this tournament"
    />
  );
}
