import { describe, expect, it } from "vitest";
import { estimateSms } from "@/lib/sms";

// Shared with backend/tests/unit/test_sms_helpers.py (VECTORS): (body, encoding, units, segments).
const VECTORS: [string, "gsm7" | "unicode", number, number][] = [
  ["", "gsm7", 0, 0],
  ["Hello", "gsm7", 5, 1],
  ["a".repeat(160), "gsm7", 160, 1],
  ["a".repeat(161), "gsm7", 161, 2],
  ["a".repeat(306), "gsm7", 306, 2],
  ["a".repeat(307), "gsm7", 307, 3],
  ["{".repeat(80), "gsm7", 160, 1],
  ["{".repeat(81), "gsm7", 162, 2],
  ["Kumusta ka, Nanay?", "gsm7", 18, 1],
  ["é".repeat(70), "gsm7", 70, 1],
  ["日本語", "unicode", 3, 1],
  ["ñ".repeat(70) + "😀", "unicode", 72, 2],
  ["字".repeat(70), "unicode", 70, 1],
  ["字".repeat(71), "unicode", 71, 2],
  ["字".repeat(134), "unicode", 134, 2],
  ["字".repeat(135), "unicode", 135, 3],
  ["Hi 😀", "unicode", 5, 1],
];

describe("estimateSms matches the server's segment rules", () => {
  it.each(VECTORS)("%j", (body, encoding, units, segments) => {
    const estimate = estimateSms(body);
    expect({
      encoding: estimate.encoding,
      units: estimate.characters,
      segments: estimate.segments,
    }).toEqual({
      encoding,
      units,
      segments,
    });
  });
});
