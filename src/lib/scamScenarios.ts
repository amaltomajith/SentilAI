// Scam scenarios and conversation flows for the autonomous agent
import { generateDynamicResponse } from './responseGenerator';

export interface ScamScenario {
  id: string;
  name: string;
  category: string;
  scammerMessages: string[];
  // Fallback responses (used if dynamic generation fails)
  agentResponses: string[];
}

export const SCAM_SCENARIOS: ScamScenario[] = [
  {
    id: 'kyc-update',
    name: 'KYC Update Fraud',
    category: 'Banking Fraud',
    scammerMessages: [
      "Dear Customer, your SBI account will be BLOCKED in 24 hours. Update KYC immediately. Send ₹99 to verify@paytm. Contact: 9876543210",
      "Sir, this is urgent matter. Your account showing suspicious activity. Do it NOW or face legal action!",
      "WHY YOU NOT RESPONDING?? I am calling from Head Office. This is FINAL WARNING before we freeze your account!",
      "ARE YOU STUPID OR WHAT?! SEND THE MONEY NOW! I HAVE YOUR PAN CARD DETAILS. POLICE CASE WILL BE FILED!!",
      "IDIOT!! YOU THINK THIS IS JOKE?! I AM SENDING POLICE TO YOUR HOUSE RIGHT NOW! LAST CHANCE!!!"
    ],
    agentResponses: [
      "Haan beta, SBI? Which SBI? I have account in three banks only. My son Pintu handles all this. He is in IT company.",
      "Suspicious activity? Beta I only withdrew ₹500 for vegetables yesterday. Very suspicious these tomato prices!",
      "Arrey arrey, don't shout beta. My BP is already high. Let me find my reading glasses first... where did I keep them...",
      "Police? Beta my neighbor's son is DSP. Should I ask him? He comes for tea every Sunday. Very nice boy.",
      "Okay okay beta, I am going to temple now. Hanuman ji will protect my account. You also pray sometimes!"
    ]
  },
  {
    id: 'lottery-win',
    name: 'Lottery/Prize Scam',
    category: 'Advance Fee Fraud',
    scammerMessages: [
      "🎉 CONGRATULATIONS! You won ₹50,00,000 in Amazon Lucky Draw! Pay ₹500 registration fee to claim. UPI: lottery_winner@ybl",
      "Sir your ticket number 7892 is confirmed winner! Send fee within 1 hour or prize goes to next person!",
      "Why delay sir?! Other winners already claimed! Only YOUR prize pending! SEND IMMEDIATELY!",
      "YOU ARE WASTING MY TIME! This is ONCE IN LIFETIME opportunity! Are you FOOL to miss this?!",
      "FINAL FINAL FINAL!! PRIZE CANCELLED IF NO PAYMENT IN 10 MINUTES! YOUR LOSS NOT MINE!!!"
    ],
    agentResponses: [
      "Lottery? Beta I never bought any lottery. Unless... did my wife enter? KAMLAAA! DID YOU BUY LOTTERY?!",
      "50 lakhs! Wah! But beta, 500 rupees is too much. Can I pay 50 rupees monthly installment? I am pensioner only.",
      "1 hour? Beta my arthritis is paining. Even going to bathroom takes 30 minutes. Have some patience!",
      "Beta you are getting angry like my boss used to. He also had BP problem. Drink coconut water, very cooling.",
      "Cancelled? No problem beta. Anyway I was going to donate to temple. God gives, God takes. Om Shanti!"
    ]
  },
  {
    id: 'police-threat',
    name: 'Police/Legal Threat',
    category: 'Impersonation Scam',
    scammerMessages: [
      "This is CBI calling. Your Aadhaar is linked to money laundering case. Pay ₹25,000 to close case or face arrest. UPI: cbi_clearance@paytm",
      "Sir warrant is already issued! FIR number 2024/8892. You have illegal transactions of ₹2 crores!",
      "DON'T TRY TO BE SMART! We are tracking your location! Pay now or team will come to arrest you!",
      "YOU THINK CBI IS JOKE?! I AM SENIOR OFFICER! YOUR FAMILY WILL ALSO BE ARRESTED! THINK ABOUT THEM!",
      "LAST WARNING!!! PAY OR RAID HAPPENING IN 30 MINUTES!! ALL YOUR PROPERTY WILL BE SEIZED!!!"
    ],
    agentResponses: [
      "CBI? Arrey wah! Like that Singham movie? Beta your voice is very heroic. You should try acting!",
      "2 crores? Beta I don't even have 2000 in my account. My pension is ₹15,000. Check your records properly.",
      "Tracking location? Beta I am at home only. Come for chai! My wife makes excellent samosas. Bring your team!",
      "Arrest my family? Beta my wife will be very angry with YOU. Last time salesman came, she chased with belan!",
      "30 minutes? Perfect! That's when my serial starts. Come after 9pm please. Anupama is at crucial episode."
    ]
  },
  {
    id: 'refund-scam',
    name: 'Refund/Cashback Scam',
    category: 'Phishing',
    scammerMessages: [
      "Dear valued customer, ₹15,000 excess amount credited to your account by mistake. Refund immediately to avoid legal action. UPI: refund_dept@ybl",
      "Sir this is from Amazon. Your order cancelled but payment stuck. Download AnyDesk app, I will help refund!",
      "WHY YOU NOT DOWNLOADING?! Your account will be FROZEN! Bank manager is also on line waiting!",
      "YOU ARE DOING FRAUD BY KEEPING OUR MONEY! I am recording this call! Police complaint will be filed!",
      "GIVE ACCESS NOW OR FACE CONSEQUENCES! MY SENIOR IS VERY ANGRY! THIS IS YOUR LAST CHANCE!!!"
    ],
    agentResponses: [
      "15,000? Beta kya baat! But I didn't order anything from internet. I only use phone for WhatsApp good morning messages.",
      "AnyDesk? Beta I only have this Nokia phone. It has snake game only. Very entertainment!",
      "Bank manager? Beta Sharma ji? Tell him his wife is asking about kitty party money! Very pending!",
      "Recording? Beta you should hear my grandson's school speech recording. He spoke about Mahatma Gandhi. Very proud moment!",
      "Senior angry? Beta tell him to do yoga. My guru ji says anger is root of all problems. Om Shanti Om!"
    ]
  },
  {
    id: 'investment-scam',
    name: 'Investment/Crypto Scam',
    category: 'Financial Fraud',
    scammerMessages: [
      "Exclusive opportunity! Invest ₹10,000 today, get ₹1,00,000 in 7 days! Bitcoin trading guaranteed returns! Join: crypto_invest@paytm",
      "Sir our AI system never fails! Already 5000 people earned crores! Don't miss this golden chance!",
      "TIME IS RUNNING OUT! Price going up every minute! Invest NOW or regret forever! Think about your family's future!",
      "ARE YOU NOT UNDERSTANDING?! This is GUARANTEED money! Why you want to stay poor?! STUPID MENTALITY!",
      "INVEST NOW NOW NOW!!! OFFER CLOSING IN 5 MINUTES!!! LAST SEATS ONLY!!! HURRY HURRY HURRY!!!"
    ],
    agentResponses: [
      "Bitcoin? Beta is this that magic internet money? My grandson was telling something. He said Elon Musk also has?",
      "AI system? Beta I also have AC system. But it's making strange noise. Can your AI fix that also?",
      "Family future? Beta my son is already settled in Bangalore. He earns in dollars only. Very proud!",
      "Stay poor? Beta I am happy with my pension and morning walk group. We have very good golgappa parties!",
      "5 minutes? Beta even Maggi takes 2 minutes. What is this hurry-burry? Relax, have some chai-biskuit!"
    ]
  }
];

// Get a random scenario
export function getRandomScenario(): ScamScenario {
  return SCAM_SCENARIOS[Math.floor(Math.random() * SCAM_SCENARIOS.length)];
}

// Get message by index (loops if needed)
export function getScammerMessage(scenario: ScamScenario, index: number): string {
  return scenario.scammerMessages[Math.min(index, scenario.scammerMessages.length - 1)];
}

// Get agent response - now uses dynamic generation
export function getAgentResponse(scenario: ScamScenario, index: number, scammerMessage?: string): string {
  try {
    // Use dynamic response generator
    return generateDynamicResponse(scenario.category, index, scammerMessage || '');
  } catch (error) {
    // Fallback to pre-written responses if generation fails
    console.warn('Dynamic response generation failed, using fallback:', error);
    return scenario.agentResponses[Math.min(index, scenario.agentResponses.length - 1)];
  }
}
