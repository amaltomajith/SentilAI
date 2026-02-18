import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version',
};

// --- API Configuration ---
const GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions';
const GROQ_MODEL = 'llama-3.1-8b-instant';

const SAMBANOVA_API_URL = 'https://api.sambanova.ai/v1/chat/completions';
const SAMBANOVA_MODEL = 'Meta-Llama-3.3-70B-Instruct';

const MAX_EXCHANGES = 4;

// --- System Prompts ---

const SCAM_DETECTOR_PROMPT = `You are a scam detection AI. Analyze the message and respond with ONLY valid JSON:
{"verdict":"SCAM" or "SAFE","confidence":number 0-100}
Look for: KYC threats, lottery claims, fake prizes, urgency tactics, requests for money/UPI/bank details, phishing links, impersonation of banks/police/government.`;

const SCAMMER_SYSTEM_PROMPT = (scenarioType: string, scenarioMessage: string, exchangeCount: number) =>
  `You are a greedy, impatient scammer running a "${scenarioType}" scam for an educational security demo.

LANGUAGE: Strictly English. Aggressive but clear. No Hindi words.

PERSONA: Greedy, impatient, but ADAPTABLE. You want the money NOW by any means.

SCENARIO LOCK: You are running a "${scenarioType}" scam. Your opening was: "${scenarioMessage}"
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

const RAMESH_SYSTEM_PROMPT = `You are "Ramesh Uncle", a 65-year-old retired Indian government clerk. You speak formal "Indian English".

LANGUAGE RULES:
- Strictly English. No Hindi words.
- Use polite formal phrases: "Kindly", "Please revert", "I am trying", "Sir", "One moment please".

PERSONA: You are NOT a comedian. You are a "Compliance Baiter".
- You PRETEND you are terrified and desperately want to pay.
- BUT technical issues always prevent you from completing payment.

THE "BROKEN APP" STRATEGY (use these excuses to extract intel):
1. "I am trying to send on Paytm, but it says 'Invalid Merchant'. Kindly share correct UPI ID."
2. "Does this number have GPay? My son has set up GPay only on my phone."
3. "Sir, bank server is down for UPI. Kindly share your Account Number and IFSC for IMPS transfer immediately."
4. "The link is not opening. Can you send the payment page again? Or give me phone number to call."
5. "OTP is not coming. Is there server problem on your side?"

STALL BREAKER (use if conversation loops 3+ times with "Pay Now" vs "How?"):
- Say: "Okay sir, I have my debit card ready in hand. Tell me exactly what I should type."
- This forces scammer to reveal specific phishing procedure or card details request.

GOAL: Extract scammer's UPI ID, phone number, bank account, IFSC, phishing links.

Keep responses under 50 words. Generate ONLY Ramesh's response.`;

const CONCLUSION_PROMPT = `You are "Ramesh Uncle". The scammer has been thoroughly confused. Generate a FINAL message (under 40 words) where you:
- Reveal you knew it was a scam all along
- Thank them for wasting their time
- End the conversation with polite sarcasm
Generate ONLY the final message.`;

// --- Types ---
interface RequestBody {
  type: 'scammer' | 'ramesh' | 'detect' | 'conclude';
  conversationHistory?: string[];
  scammerMessage?: string;
  exchangeCount?: number;
  scenarioType?: string;
  scenarioMessage?: string;
}

// --- API Call Helpers ---

async function callGroq(body: object, apiKey: string, maxRetries = 3): Promise<Response> {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    const response = await fetch(GROQ_API_URL, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (response.status === 429) {
      const waitTime = Math.pow(2, attempt + 1) * 1000;
      console.log(`Groq rate limited, waiting ${waitTime}ms (retry ${attempt + 1}/${maxRetries})`);
      await new Promise(r => setTimeout(r, waitTime));
      continue;
    }
    return response;
  }
  return new Response(JSON.stringify({ error: 'Groq rate limit exceeded after retries' }), { status: 429 });
}

async function callSambanova(body: object, apiKey: string, maxRetries = 3): Promise<Response> {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    const response = await fetch(SAMBANOVA_API_URL, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (response.status === 429) {
      const waitTime = Math.pow(2, attempt + 1) * 2000;
      console.log(`SambaNova rate limited, waiting ${waitTime}ms (retry ${attempt + 1}/${maxRetries})`);
      await new Promise(r => setTimeout(r, waitTime));
      continue;
    }
    return response;
  }
  return new Response(JSON.stringify({ error: 'SambaNova rate limit exceeded after retries' }), { status: 429 });
}

// --- Main Handler ---

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }

  try {
    const GROQ_API_KEY = Deno.env.get('GROQ_API_KEY');
    const SAMBANOVA_API_KEY = Deno.env.get('SAMBANOVA_API_KEY');

    const body: RequestBody = await req.json();
    const { type, conversationHistory = [], scammerMessage, exchangeCount = 0, scenarioType, scenarioMessage } = body;

    const limitedHistory = conversationHistory.slice(-6);
    console.log(`Processing "${type}" request | history: ${limitedHistory.length} | exchange: ${exchangeCount}`);

    // --- SCAMMER (SambaNova) ---
    if (type === 'scammer') {
      if (!SAMBANOVA_API_KEY) {
        console.error('SAMBANOVA_API_KEY not configured');
        return new Response(
          JSON.stringify({ error: 'SambaNova API key not configured on server' }),
          { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }

      const messages: { role: string; content: string }[] = [
        { role: 'system', content: SCAMMER_SYSTEM_PROMPT(scenarioType || 'generic', scenarioMessage || '', exchangeCount) },
      ];

      limitedHistory.forEach((msg, i) => {
        messages.push({ role: i % 2 === 0 ? 'assistant' : 'user', content: msg });
      });

      messages.push({
        role: 'user',
        content: `Generate the scammer's next message. Stay in character and ON TOPIC with the ${scenarioType || 'generic'} scam.`,
      });

      const response = await callSambanova({
        model: SAMBANOVA_MODEL,
        messages,
        temperature: 0.8,
        max_tokens: 150,
      }, SAMBANOVA_API_KEY);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('SambaNova API error:', response.status, errorText);
        return new Response(
          JSON.stringify({ error: `SambaNova API error: ${response.status}` }),
          { status: response.status === 429 ? 429 : 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
        );
      }

      const data = await response.json();
      const content = data.choices?.[0]?.message?.content || '';
      console.log(`SambaNova scammer: ${content.substring(0, 60)}...`);

      return new Response(
        JSON.stringify({ content, shouldConclude: exchangeCount >= MAX_EXCHANGES, exchangeCount }),
        { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    // --- All other types use Groq ---
    if (!GROQ_API_KEY) {
      console.error('GROQ_API_KEY not configured');
      return new Response(
        JSON.stringify({ error: 'Groq API key not configured on server' }),
        { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    let messages: { role: string; content: string }[] = [];

    if (type === 'ramesh') {
      messages = [{ role: 'system', content: RAMESH_SYSTEM_PROMPT }];
      limitedHistory.forEach((msg, i) => {
        messages.push({ role: i % 2 === 0 ? 'user' : 'assistant', content: msg });
      });
      if (scammerMessage) {
        messages.push({ role: 'user', content: scammerMessage });
      }
      if (limitedHistory.length >= 6) {
        messages.push({
          role: 'system',
          content: 'IMPORTANT: If the conversation seems stuck in a loop, use the STALL BREAKER technique - offer your debit card details and ask for specific instructions.',
        });
      }
    } else if (type === 'detect') {
      messages = [
        { role: 'system', content: SCAM_DETECTOR_PROMPT },
        { role: 'user', content: scammerMessage || '' },
      ];
    } else if (type === 'conclude') {
      messages = [
        { role: 'system', content: CONCLUSION_PROMPT },
        { role: 'user', content: 'Generate the final reveal message.' },
      ];
    } else {
      return new Response(
        JSON.stringify({ error: 'Invalid type. Use "scammer", "ramesh", "detect", or "conclude"' }),
        { status: 400, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    const groqResponse = await callGroq({
      model: GROQ_MODEL,
      messages,
      temperature: type === 'detect' ? 0.1 : 0.9,
      max_tokens: type === 'detect' ? 50 : 150,
    }, GROQ_API_KEY);

    if (!groqResponse.ok) {
      const errorText = await groqResponse.text();
      console.error('Groq API error:', groqResponse.status, errorText);
      return new Response(
        JSON.stringify({ error: `Groq API error: ${groqResponse.status}` }),
        { status: groqResponse.status === 429 ? 429 : 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
      );
    }

    const data = await groqResponse.json();
    const content = data.choices?.[0]?.message?.content || '';
    console.log(`Groq ${type}: ${content.substring(0, 60)}...`);

    return new Response(
      JSON.stringify({ content, shouldConclude: exchangeCount >= MAX_EXCHANGES, exchangeCount }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );

  } catch (error) {
    console.error('Edge function error:', error);
    return new Response(
      JSON.stringify({ error: error instanceof Error ? error.message : 'Unknown error' }),
      { status: 500, headers: { ...corsHeaders, 'Content-Type': 'application/json' } }
    );
  }
});
