export type SmsEncoding = "gsm7" | "unicode";

export interface SmsEstimate {
  characters: number;
  encoding: SmsEncoding;
  segments: number;
  /** Characters allowed per segment for this encoding and segment count. */
  perSegment: number;
}

// GSM 03.38 basic set plus the extension table (extension chars cost 2 units).
const GSM_BASIC =
  "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà";
const GSM_EXTENDED = "^{}\\[~]|€\f";

function gsmLength(body: string): number | null {
  let units = 0;
  for (const char of body) {
    if (GSM_BASIC.includes(char)) units += 1;
    else if (GSM_EXTENDED.includes(char)) units += 2;
    else return null;
  }
  return units;
}

/** Client-side estimate only. The backend is authoritative for segments and cost. */
export function estimateSms(body: string): SmsEstimate {
  const gsmUnits = gsmLength(body);
  if (gsmUnits !== null) {
    const single = gsmUnits <= 160;
    return {
      characters: gsmUnits,
      encoding: "gsm7",
      segments: gsmUnits === 0 ? 0 : single ? 1 : Math.ceil(gsmUnits / 153),
      perSegment: single ? 160 : 153,
    };
  }
  // Unicode segments count UTF-16 code units: characters outside the BMP (most emoji) cost two.
  const characters = body.length;
  const single = characters <= 70;
  return {
    characters,
    encoding: "unicode",
    segments: characters === 0 ? 0 : single ? 1 : Math.ceil(characters / 67),
    perSegment: single ? 70 : 67,
  };
}

export function maskPhoneNumber(e164: string): string {
  if (e164.length < 8) return "****";
  const countryCode = e164.startsWith("+63") ? "+63" : e164.slice(0, 3);
  return `${countryCode}****${e164.slice(-4)}`;
}
