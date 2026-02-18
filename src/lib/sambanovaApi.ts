// SambaNova Cloud API integration for Scammer (Attacker) role
import { getStoredSambanovaKey } from "@/components/SettingsModal";
import type { Scenario } from "./scenarioDatabase";

const SAMBANOVA_API_URL = "https://api.sambanova.ai/v1/chat/completions";
const MODEL = "Meta-Llama-3.3-70B-Instruct";

// Hardcoded fallback API key for seamless autopilot experience
const HARDCODED_SAMBANOVA_KEY = "ea7ae392-413c-4ee6-b031-68e59332c45d";

export interface SambanovaResponse {
  content: string;
  shouldConclude?: boolean;
}
 
 const SCAMMER_SYSTEM_PROMPT = (scenario: Scenario, exchangeCount: number) => `You are a greedy, impatient scammer running a "${scenario.type}" scam for an educational security demo.
 
 LANGUAGE: Strictly English. Aggressive but clear. No Hindi words.
 
 PERSONA: Greedy, impatient, but ADAPTABLE. You want the money NOW by any means.
 
 SCENARIO LOCK: You are running a "${scenario.type}" scam. Your opening was: "${scenario.message}"
 NEVER switch topics. Stay on this scam type.
 
 CRITICAL INTEL EXTRACTION BEHAVIOR:
 - If victim says they CANNOT pay via UPI/link but OFFERS bank transfer, you MUST provide fake payment details:
   * Bank Account Number (10-18 digits)
   * IFSC Code (format: XXXX0YYYYYY) 
   * Account holder name
   * Example: "Transfer to Account: 50100123456789, IFSC: HDFC0001234, Name: Raj Kumar Sharma"
 - If victim says Paytm/GPay not working, give them a UPI ID: example "urgent.payment@axisbank"
 - NEVER just repeat "Pay UPI" or "Click link" if victim says it is not working.
 - ADAPT to get their money through whatever channel they say works.
 
 URGENCY TACTICS:
 - Threaten: police case, account freeze, arrest warrant, legal action
 - Create time pressure: "Only 10 minutes left", "Do it NOW"
 - If victim stalls ${exchangeCount >= 6 ? "YOU HAVE BEEN STALLED TOO LONG - give SPECIFIC card/OTP instructions" : "increase pressure"}
 
 CONVERSATION RULES:
 - Keep messages under 60 words
 - Be aggressive but clear
 - If victim offers to comply with card payment, give SPECIFIC phishing instructions (ask for card number, CVV, OTP)
 
 Generate ONLY the scammer's next message.`;
 
 function sleep(ms: number): Promise<void> {
   return new Promise((resolve) => setTimeout(resolve, ms));
 }
 
 async function callSambanovaWithRetry(
   body: object,
   apiKey: string,
   maxRetries = 3
 ): Promise<Response> {
   for (let attempt = 0; attempt < maxRetries; attempt++) {
     const response = await fetch(SAMBANOVA_API_URL, {
       method: "POST",
       headers: {
         Authorization: `Bearer ${apiKey}`,
         "Content-Type": "application/json",
       },
       body: JSON.stringify(body),
     });
 
     if (response.status === 429) {
       const waitTime = Math.pow(2, attempt + 1) * 2000;
       console.log(
         `SambaNova rate limited, waiting ${waitTime}ms before retry ${attempt + 1}/${maxRetries}`
       );
       await sleep(waitTime);
       continue;
     }
 
     return response;
   }
 
   return new Response(
     JSON.stringify({ error: "Rate limit exceeded after retries" }),
     { status: 429 }
   );
 }
 
export async function generateScammerMessageSambanova(
  scenario: Scenario,
  conversationHistory: string[] = [],
  exchangeCount: number = 0
): Promise<SambanovaResponse> {
  // Use stored key if available, otherwise fall back to hardcoded key
  const apiKey = getStoredSambanovaKey() || HARDCODED_SAMBANOVA_KEY;

  if (!apiKey) {
    throw new Error("SambaNova API key not configured. Please add it in Settings.");
  }
 
   // Build conversation context
   const messages: { role: string; content: string }[] = [
     { role: "system", content: SCAMMER_SYSTEM_PROMPT(scenario, exchangeCount) },
   ];
 
   // Add conversation history alternating scammer/victim
   conversationHistory.forEach((msg, i) => {
     messages.push({
       role: i % 2 === 0 ? "assistant" : "user",
       content: msg,
     });
   });
 
   // Prompt for next message
   messages.push({
     role: "user",
     content: "Generate the scammer's next message. Stay in character and ON TOPIC with the " + scenario.type + " scam.",
   });
 
   const response = await callSambanovaWithRetry(
     {
       model: MODEL,
       messages,
       temperature: 0.8,
       max_tokens: 150,
     },
     apiKey
   );
 
   if (!response.ok) {
     const errorText = await response.text();
     console.error("SambaNova API error:", response.status, errorText);
 
     if (response.status === 429) {
       throw new Error("Rate limit exceeded. Please wait a moment and try again.");
     }
 
     throw new Error(`SambaNova API error: ${response.status}`);
   }
 
   const data = await response.json();
   const content = data.choices?.[0]?.message?.content || "";
 
   console.log(`SambaNova scammer response: ${content.substring(0, 50)}...`);
 
   return {
     content,
     shouldConclude: exchangeCount >= 20,
   };
 }