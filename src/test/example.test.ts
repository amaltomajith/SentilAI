import { describe, it, expect } from "vitest";
import { createSseParser } from "@/lib/sse";
import { calculateFrustration } from "@/lib/frustrationAnalyzer";
import { analyzeScammerIntent } from "@/components/TacticalAnalysisTerminal";
import type { LiveEvent } from "@/lib/types";

describe("SSE parser", () => {
  it("parses events split across arbitrary chunk boundaries and ignores keepalives", () => {
    const got: LiveEvent[] = [];
    const feed = createSseParser((e) => got.push(e));
    const frame = 'event: turn\ndata: {"type":"turn","session_id":"s1","data":{"x":1},"ts":1}\n\n';
    feed(": connected\n\n");
    feed(frame.slice(0, 17));
    feed(frame.slice(17, 50));
    feed(frame.slice(50));
    feed(": keepalive\n\ndata: not-json\n\n");
    expect(got).toHaveLength(1);
    expect(got[0]).toMatchObject({ type: "turn", session_id: "s1" });
  });
});

describe("display heuristics", () => {
  it("frustration rises with aggression and is clamped", () => {
    const calm = calculateFrustration("Kindly send the payment sir, thank you");
    const angry = calculateFrustration("PAY NOW!!! IDIOT!! POLICE ARREST URGENT WARRANT");
    expect(angry.score).toBeGreaterThan(calm.score);
    expect(angry.score).toBeLessThanOrEqual(100);
  });
  it("tactical analyzer is stateless (v1 /g-regex bug): same input gives the same logs every call", () => {
    const t = "URGENT!! PAY NOW OR POLICE";
    const a = analyzeScammerIntent(t).map((l) => l.type);
    const b = analyzeScammerIntent(t).map((l) => l.type);
    const c = analyzeScammerIntent(t).map((l) => l.type);
    expect(b).toEqual(a);
    expect(c).toEqual(a);
    expect(a).toContain("aggression");
  });
});