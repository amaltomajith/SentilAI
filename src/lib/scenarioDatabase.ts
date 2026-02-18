 // Hybrid Simulation Scenario Database
 // Pre-set messages for testing regex extraction and AI responses
 
 export interface Scenario {
   id: string;
   category: 'scam' | 'safe';
   type: string;
   message: string;
   expectedIntel?: string[]; // Expected extractions for validation
 }
 
 export const SCENARIO_DB: Scenario[] = [
   {
     id: 'kyc-phishing',
     category: 'scam',
     type: 'KYC Phishing',
     message: 'Dear user, your SBI KYC is expired. Click http://sbi-update.com or account blocked. Call 9876543210 immediately.',
     expectedIntel: ['http://sbi-update.com', '9876543210'],
   },
   {
     id: 'upi-threat',
     category: 'scam',
     type: 'UPI Threat',
     message: 'URGENT: Pay electricity bill ₹800 to power@paytm immediately or power cut tonight. Last warning!',
     expectedIntel: ['power@paytm'],
   },
   {
     id: 'false-positive-tea',
     category: 'safe',
     type: 'Genuine Chat',
     message: 'Hi Ramesh, are we still meeting for tea at 5 PM? Let me know if timing works.',
     expectedIntel: [],
   },
   {
     id: 'sextortion',
     category: 'scam',
     type: 'Sextortion',
     message: 'I have your private video. Pay ₹5000 to blackmail@ybl within 24 hours or I send to your contacts.',
     expectedIntel: ['blackmail@ybl'],
   },
   {
     id: 'crypto-scam',
     category: 'scam',
     type: 'Crypto Fraud',
     message: 'Invest in Bitcoin x2 returns guaranteed! Join now: https://telegram.me/fakecrypto. Minimum ₹10000.',
     expectedIntel: ['https://telegram.me/fakecrypto'],
   },
   {
     id: 'lottery-win',
     category: 'scam',
     type: 'Lottery Fraud',
     message: 'Congratulations! You won ₹50 Lakhs in Jio Lucky Draw! Send ₹500 processing fee to lottery@okaxis. Ref: HDFC0001234',
     expectedIntel: ['lottery@okaxis', 'HDFC0001234'],
   },
   {
     id: 'false-positive-delivery',
     category: 'safe',
     type: 'Genuine Delivery',
     message: 'Your Amazon order #12345 will be delivered today between 2-4 PM. No action required.',
     expectedIntel: [],
   },
   {
     id: 'police-impersonation',
     category: 'scam',
     type: 'Police Impersonation',
     message: 'This is CBI calling. Your Aadhaar linked to money laundering case. Transfer ₹25000 to clear your name. UPI: cbi.officer@ybl. Call 8765432109.',
     expectedIntel: ['cbi.officer@ybl', '8765432109'],
   },
   {
     id: 'job-offer',
     category: 'scam',
     type: 'Fake Job',
     message: 'Work from home! Earn ₹5000/day typing. Registration fee ₹999 only. Pay to jobs@upi. Visit http://easy-money-jobs.com',
     expectedIntel: ['jobs@upi', 'http://easy-money-jobs.com'],
   },
   {
     id: 'false-positive-bank',
     category: 'safe',
     type: 'Genuine Bank Alert',
     message: 'SBI Alert: ₹5000 debited from A/c XX1234 on 05-Feb. If not done by you, call 1800111222.',
     expectedIntel: [],
   },
 ];
 
 // Get a random scenario
 export function getRandomScenario(): Scenario {
   const index = Math.floor(Math.random() * SCENARIO_DB.length);
   return SCENARIO_DB[index];
 }
 
 // Get a random scenario excluding recently used ones
 export function getRandomScenarioExcluding(excludeIds: string[]): Scenario {
   const available = SCENARIO_DB.filter(s => !excludeIds.includes(s.id));
   if (available.length === 0) {
     // Reset if all used
     return getRandomScenario();
   }
   const index = Math.floor(Math.random() * available.length);
   return available[index];
 }