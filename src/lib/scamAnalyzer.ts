// Scam detection and analysis utilities

export interface Persona {
  id: string;
  name: string;
  description: string;
  avatar: string;
  responses: string[];
}

export interface ExtractedIntel {
  type: 'UPI ID' | 'Phone Number' | 'URL' | 'Email' | 'Bank Account' | 'Phishing URL' | 'IFSC Code';
  value: string;
  risk: 'High' | 'Medium' | 'Low' | 'Critical';
}

export interface AnalysisResult {
  isScam: boolean;
  confidence: number;
  scamType: string;
  detectedKeywords: string[];
  persona: Persona;
  aiResponse: string;
  extractedIntel: ExtractedIntel[];
  timestamp: string;
  processingTime: number;
}

// Victim personas with funny responses
export const PERSONAS: Persona[] = [
  {
    id: 'sentinel-agent',
    name: 'Sentinel',
    description: 'Autonomous Threat Neutralization Agent',
    avatar: '🛡️',
    responses: [
      "Beta, my spectacles are broken, which button is UPI? Also, my grandson Chintu can help but he's studying for IIT.",
      "Haan haan, but first tell me - are you from that same company that called about my electricity bill? Very confusing all this.",
      "I won lottery?! Wait, let me call my wife... KAMLAAA! Someone saying we won lottery! ...she's not believing also.",
      "Beta, I am on WhatsApp only. My phone is Nokia 3310, how to do this UPI-VPI? Send me by speed post.",
      "Very good very good! But beta, 500 rupees is too much. My pension is coming on 1st. Can you wait till then? I will give 50-50 every month.",
    ]
  },
  {
    id: 'rahul-student',
    name: 'Rahul',
    description: 'Broke Engineering Student from Delhi',
    avatar: '🧑‍💻',
    responses: [
      "Bro I literally have ₹47 in my account and that's for Maggi. Can you accept payment in exposure? I have 200 Instagram followers.",
      "Wait wait, let me ask my hostel warden for permission first. Also, can you send the money to my mess account instead? I owe them 3 months.",
      "Dude perfect timing! I just failed my DSA exam, maybe this lottery is my sign. But bro, my UPI is linked to my dad's account and he checks EVERY transaction 💀",
      "No cap, I thought this was my internship offer letter 😭 Anyway, can I pay in installments? Like ₹10 per month for 50 months?",
      "Saar pls I am just a student. My father will kill me if he sees -500 in account. Can you WhatsApp my father and convince him? His number is 98XXXXXX",
    ]
  },
  {
    id: 'aunty-ji',
    name: 'Aunty Ji',
    description: 'Neighborhood Gossip Queen from Mumbai',
    avatar: '👩‍🦳',
    responses: [
      "Arre wah! Wait I'm telling Sharma ji's wife also - PINKY! PINKY! Come here! Someone giving free money! ...she's asking if her son can also register?",
      "Beta, you know that Gupta ji from B-wing? He also got this message but he didn't send money and NOW he's driving Fortuner. What is the logic?",
      "Haan haan but first tell me - are you married? My niece is very beautiful, fair, homely. She knows cooking also. Should I send biodata?",
      "I knew it! I told everyone in my kitty party that my luck is changing. Yesterday also I found 10 rupees in old purse. Universe is giving signs!",
      "Very nice beta! But my husband is very kanjoos. He doesn't even give money for my salon. Can you talk to him? He's sitting right here watching crime patrol.",
    ]
  }
];

// Scam detection keywords and patterns
const SCAM_KEYWORDS = [
  'lottery', 'winner', 'won', 'prize', 'congratulations', 'selected',
  'urgent', 'immediately', 'limited time', 'act now', 'hurry',
  'registration fee', 'processing fee', 'tax', 'send money', 'transfer',
  'bank details', 'account number', 'upi', 'paytm', 'gpay', 'phonepe',
  'kyc', 'verify', 'blocked', 'suspended', 'update required',
  'refund', 'cashback', 'bonus', 'free', 'guaranteed',
  'click here', 'link', 'verify now', 'confirm',
  'bitcoin', 'crypto', 'investment', 'returns', 'profit',
  'government', 'rbi', 'income tax', 'court', 'legal action'
];

const SCAM_TYPES: Record<string, string[]> = {
  'Lottery/Prize Scam': ['lottery', 'winner', 'won', 'prize', 'congratulations', 'selected'],
  'KYC Fraud': ['kyc', 'verify', 'blocked', 'suspended', 'update required', 'account'],
  'Advance Fee Fraud': ['registration fee', 'processing fee', 'tax', 'send money', 'transfer'],
  'Investment Scam': ['bitcoin', 'crypto', 'investment', 'returns', 'profit', 'guaranteed'],
  'Impersonation Scam': ['government', 'rbi', 'income tax', 'court', 'legal action'],
  'Phishing Attack': ['click here', 'link', 'verify now', 'confirm', 'urgent'],
  'Refund Scam': ['refund', 'cashback', 'bonus', 'credited', 'excess payment'],
};

// Regex patterns for intel extraction
const PATTERNS = {
  upi: /[a-zA-Z0-9._-]+@[a-zA-Z]{2,}/g,
  phone: /(?:\+91[\s-]?)?[6-9]\d{9}/g,
  url: /https?:\/\/[^\s<>"{}|\\^`\[\]]+/gi,
  email: /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g,
  bankAccount: /\d{9,18}/g,
  amount: /₹?\s?\d{1,3}(?:,?\d{3})*(?:\.\d{2})?/g,
};

// Analyze message for scam indicators
export function analyzeMessage(message: string): AnalysisResult {
  const startTime = performance.now();
  const lowerMessage = message.toLowerCase();
  
  // Detect keywords
  const detectedKeywords = SCAM_KEYWORDS.filter(keyword => 
    lowerMessage.includes(keyword.toLowerCase())
  );
  
  // Calculate confidence based on keyword matches
  const keywordScore = Math.min(detectedKeywords.length * 12, 60);
  const patternScore = calculatePatternScore(message);
  const urgencyScore = calculateUrgencyScore(lowerMessage);
  
  const confidence = Math.min(keywordScore + patternScore + urgencyScore, 99);
  const isScam = confidence > 30;
  
  // Determine scam type
  const scamType = detectScamType(detectedKeywords);
  
  // Extract intel
  const extractedIntel = extractIntel(message);
  
  // Select random persona
  const persona = PERSONAS[Math.floor(Math.random() * PERSONAS.length)];
  
  // Select random response from persona
  const aiResponse = persona.responses[Math.floor(Math.random() * persona.responses.length)];
  
  const endTime = performance.now();
  
  return {
    isScam,
    confidence,
    scamType,
    detectedKeywords,
    persona,
    aiResponse,
    extractedIntel,
    timestamp: new Date().toISOString(),
    processingTime: Math.round(endTime - startTime),
  };
}

function calculatePatternScore(message: string): number {
  let score = 0;
  
  if (PATTERNS.upi.test(message)) score += 15;
  if (PATTERNS.phone.test(message)) score += 10;
  if (PATTERNS.url.test(message)) score += 15;
  if (PATTERNS.amount.test(message)) score += 10;
  
  // Reset lastIndex for reuse
  PATTERNS.upi.lastIndex = 0;
  PATTERNS.phone.lastIndex = 0;
  PATTERNS.url.lastIndex = 0;
  PATTERNS.amount.lastIndex = 0;
  
  return score;
}

function calculateUrgencyScore(message: string): number {
  const urgencyPhrases = [
    'urgent', 'immediately', 'right now', 'today only',
    'last chance', 'expiring', 'act fast', 'don\'t miss',
    'limited time', '24 hours', 'hurry'
  ];
  
  let score = 0;
  urgencyPhrases.forEach(phrase => {
    if (message.includes(phrase)) score += 5;
  });
  
  // Excessive caps or exclamation marks
  const capsRatio = (message.match(/[A-Z]/g) || []).length / message.length;
  const exclamations = (message.match(/!/g) || []).length;
  
  if (capsRatio > 0.3) score += 10;
  if (exclamations > 2) score += 5;
  
  return Math.min(score, 25);
}

function detectScamType(keywords: string[]): string {
  for (const [type, typeKeywords] of Object.entries(SCAM_TYPES)) {
    const matches = keywords.filter(k => 
      typeKeywords.some(tk => k.toLowerCase().includes(tk))
    );
    if (matches.length >= 2) return type;
  }
  
  if (keywords.length > 0) return 'Suspicious Activity';
  return 'Unknown';
}

function extractIntel(message: string): ExtractedIntel[] {
  const intel: ExtractedIntel[] = [];
  
  // Extract UPI IDs
  const upiMatches = message.match(PATTERNS.upi) || [];
  upiMatches.forEach(match => {
    if (!match.includes('.com') && !match.includes('.in') && !match.includes('.org')) {
      intel.push({ type: 'UPI ID', value: match, risk: 'High' });
    }
  });
  
  // Extract phone numbers
  const phoneMatches = message.match(PATTERNS.phone) || [];
  phoneMatches.forEach(match => {
    intel.push({ type: 'Phone Number', value: match.replace(/\s/g, ''), risk: 'Medium' });
  });
  
  // Extract URLs
  const urlMatches = message.match(PATTERNS.url) || [];
  urlMatches.forEach(match => {
    intel.push({ type: 'URL', value: match, risk: 'High' });
  });
  
  // Extract emails (excluding UPI-like patterns)
  const emailMatches = message.match(PATTERNS.email) || [];
  emailMatches.forEach(match => {
    if (match.includes('.com') || match.includes('.in') || match.includes('.org')) {
      intel.push({ type: 'Email', value: match, risk: 'Medium' });
    }
  });
  
  return intel;
}
