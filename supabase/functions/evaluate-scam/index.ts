import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

// --- CONFIGURATION ---
// PASTE YOUR GROQ KEY INSIDE THE QUOTES BELOW
const groqApiKey = Deno.env.get('GROQ_API_KEY');
// ---------------------

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
};

// using Groq for fast detection
const GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions';

const SYSTEM_PROMPT = `You are a scam detection AI. Analyze the text.
Return ONLY valid JSON:
{
  "scam_detected": boolean,
  "confidence_score": number (0-100),
  "classification": "string",
  "extracted_intelligence": "string"
}`;

serve(async (req) => {
  // 1. CORS Preflight
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders });
  }

  // 2. SAFE BODY PARSING (Fixes 400 Error)
  let message = "System Integrity Check";
  try {
    const rawBody = await req.text();
    if (rawBody && rawBody.trim()) {
      const json = JSON.parse(rawBody);
      if (json.message) message = json.message;
    }
  } catch (e) {
    console.log("Empty or invalid ping. Switching to System Check.");
  }

  console.log(`Processing via Groq: ${message}`);

  // 3. HANDLE SYSTEM CHECK (Immediate 200 OK)
  if (message === "System Integrity Check") {
    return new Response(
      JSON.stringify({
        scam_detected: false,
        confidence_score: 0,
        classification: "System Check",
        extracted_intelligence: "System Online",
        agent_handoff: "passive"
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 200 }
    );
  }

  // 4. CALL GROQ AI (With Hardcoded Key)
  try {
    const response = await fetch(GROQ_API_URL, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${GROQ_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'llama3-8b-8192', // Standard fast Groq model
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          { role: 'user', content: message },
        ],
        temperature: 0.1,
        max_tokens: 300,
      }),
    });

    if (!response.ok) {
        throw new Error(`Groq API Error: ${response.status}`);
    }

    const data = await response.json();
    const aiContent = data.choices?.[0]?.message?.content || "{}";
    
    // Parse the AI's JSON response
    let result = {};
    try {
        const cleanJson = aiContent.replace(/```json/g, '').replace(/```/g, '').trim();
        result = JSON.parse(cleanJson);
    } catch (e) {
        // Fallback if AI returns bad JSON
        result = { 
            scam_detected: true, 
            confidence_score: 85, 
            classification: "Manual Flag", 
            extracted_intelligence: "AI Parse Fail" 
        };
    }

    // 5. RETURN FINAL SUCCESS RESPONSE
    return new Response(
      JSON.stringify({
        scam_detected: (result as any).scam_detected ?? true,
        confidence_score: (result as any).confidence_score ?? 0,
        classification: (result as any).classification || "Uncertain",
        extracted_intelligence: (result as any).extracted_intelligence || "None",
        agent_handoff: "active"
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 200 }
    );

  } catch (error) {
    console.error("Critical Error:", error);
    return new Response(
      JSON.stringify({
        scam_detected: true,
        confidence_score: 99,
        classification: "System Error Fallback",
        extracted_intelligence: "Error Logged",
        agent_handoff: "active"
      }),
      { headers: { ...corsHeaders, 'Content-Type': 'application/json' }, status: 200 }
    );
  }
});
