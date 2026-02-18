// Dynamic Response Generator for Ramesh Uncle
// Creates varied, contextual responses without AI API

// Random interjections Ramesh Uncle might say
const INTERJECTIONS = [
  "Arrey wah!",
  "Hai Ram!",
  "Achha achha...",
  "Beta beta beta...",
  "Hmm hmm...",
  "Oho!",
  "Kya baat hai!",
  "Aisa kya?",
  "Theek hai theek hai...",
  "Haan haan...",
  "Chalo chalo...",
  "Dekho dekho...",
  "Uff!",
  "Bas bas...",
];

// Random family members to reference
const FAMILY_MEMBERS = [
  { name: "Pintu", relation: "son", job: "IT company in Bangalore" },
  { name: "Bunty", relation: "nephew", job: "bank manager" },
  { name: "Kamla", relation: "wife", trait: "makes excellent samosas" },
  { name: "Sharma ji", relation: "neighbor", trait: "DSP in police" },
  { name: "Guddi", relation: "daughter", job: "doctor in Delhi" },
  { name: "Pappu", relation: "grandson", trait: "very smart in computer" },
  { name: "Ramu kaka", relation: "old friend", trait: "retired from SBI" },
];

// Random excuses for delays
const DELAY_EXCUSES = [
  "my arthritis is paining today",
  "I need to take my BP medicine first",
  "my reading glasses are somewhere...",
  "let me finish my chai first",
  "I have to go to temple at 6",
  "my hearing aid battery is low",
  "the phone screen is too small",
  "I need to ask my son first",
  "my afternoon nap time is coming",
  "the maid is at the door",
];

// Random tangential topics
const TANGENTS = [
  "By the way, tomato prices are very high these days!",
  "You know, when I was young, we didn't have all these phone things.",
  "My wife is calling me for lunch, one minute...",
  "Beta, have you eaten? You should eat properly.",
  "In my time, banks were very trustworthy.",
  "My guru ji always says, patience is key.",
  "Weather is so hot today, no?",
  "These young people and their technology!",
  "I remember in 1985, I also had account problem...",
  "My blood sugar is bit high, doctor said no sweets.",
];

// Response templates by scenario type
const RESPONSE_TEMPLATES: Record<string, string[][]> = {
  'kyc-update': [
    [
      "Haan beta, {bank}? Which {bank}? I have account in {count} banks only. My {family} handles all this. {family_detail}.",
      "{interjection} SBI you say? Let me check... I think my passbook is in that almirah... {delay}.",
      "Beta, my {family} told me never give details on phone. {tangent}",
    ],
    [
      "Suspicious activity? Beta I only withdrew ₹{amount} for {item} yesterday. Very suspicious these {item} prices!",
      "{interjection} What suspicious? I am retired government servant. 35 years service! {tangent}",
      "Activity? Only activity I do is morning walk and watching Kapil Sharma. {delay}.",
    ],
    [
      "{interjection} Don't shout beta. My BP is already high. {delay}",
      "Arrey arrey, why so angry? Take deep breath. My yoga teacher says anger is poison. {tangent}",
      "Beta, you are shouting like my old boss. He also had BP problem. {delay}",
    ],
    [
      "Police? Beta my {family} is {family_detail}. Should I ask {family_pronoun}? {family_pronoun_cap} comes for tea every Sunday.",
      "{interjection} Police I know very well! My {family} is {family_detail}. Very nice person.",
      "Arrest? Beta, I have never even got traffic challan! {tangent}",
    ],
    [
      "Okay okay beta, I am going to temple now. Hanuman ji will protect my account. You also pray sometimes! {tangent}",
      "{interjection} Theek hai, I will do tomorrow. Today is Tuesday, very auspicious for Hanuman temple. {delay}.",
      "Beta, final warning? My wife gives final warning daily, I am used to it! Ha ha!",
    ],
  ],
  'lottery-win': [
    [
      "Lottery? Beta I never bought any lottery. Unless... did my {family} enter? {family_name_upper}! DID YOU BUY LOTTERY?!",
      "{interjection} 50 lakhs? Wah! But beta, I don't remember buying any ticket. {delay}.",
      "Amazon lucky draw? Beta I only use Amazon for ordering BP machine. {tangent}",
    ],
    [
      "50 lakhs! Wah! But beta, {amount} rupees is too much. Can I pay {small_amount} rupees monthly installment? I am pensioner only.",
      "{interjection} Registration fee? But if I won, why I should pay? In my time, lottery people give money, not take!",
      "Beta, my pension is only ₹{pension}. {amount} is too much! {tangent}",
    ],
    [
      "1 hour? Beta {delay}. Even going to bathroom takes 30 minutes. Have some patience!",
      "{interjection} Why so hurry beta? Good things take time. My {family} always says this.",
      "One hour only? Beta, getting government pension takes 3 months! {tangent}",
    ],
    [
      "Beta you are getting angry like my {family}. {family_pronoun_cap} also had BP problem. Drink coconut water, very cooling.",
      "{interjection} Why shouting? My hearing is actually fine, no need to shout!",
      "Waste your time? Beta, at my age, I have plenty of time! {delay}.",
    ],
    [
      "Cancelled? No problem beta. Anyway I was going to donate to temple. God gives, God takes. Om Shanti!",
      "{interjection} Prize gone? Chalo koi baat nahi. I still have my health and family. {tangent}",
      "Last chance? Beta, at 68 years, every day is last chance! Ha ha! {tangent}",
    ],
  ],
  'police-threat': [
    [
      "CBI? Arrey wah! Like that Singham movie? Beta your voice is very heroic. You should try acting!",
      "{interjection} CBI calling me? I am feeling like VIP today! Should I tell my {family}?",
      "CBI? Beta, in my 35 years government service, never any problem. {tangent}",
    ],
    [
      "2 crores? Beta I don't even have {amount} in my account. My pension is ₹{pension}. Check your records properly.",
      "{interjection} Money laundering? Beta, I don't even know how to do online transfer! My {family} does everything.",
      "Crores? Beta, my whole life savings is in FD only. {tangent}",
    ],
    [
      "Tracking location? Beta I am at home only. Come for chai! My {family} makes excellent {food}. Bring your team!",
      "{interjection} You can track me? Very impressive! Can you also find my lost spectacles?",
      "Tracking? Beta, I don't go anywhere. Temple, park, home. That's it. {delay}.",
    ],
    [
      "Arrest my {family}? Beta my {family} will be very angry with YOU. Last time salesman came, {family_pronoun} chased with belan!",
      "{interjection} Family arrest? Beta, my {family} is {family_detail}. You want to arrest {family_pronoun}? Good luck!",
      "Arrest? Beta, first tell your seniors my {family} is {family_detail}. Then see what happens!",
    ],
    [
      "30 minutes? Perfect! That's when my serial starts. Come after 9pm please. {show} is at crucial episode.",
      "{interjection} Raid? Beta, house is bit messy, give me 1 hour to clean. {delay}.",
      "30 minutes? {interjection} Let me call my {family} first, {family_pronoun} will make tea for everyone. {tangent}",
    ],
  ],
  'refund-scam': [
    [
      "15,000? Beta kya baat! But I didn't order anything from internet. I only use phone for WhatsApp good morning messages.",
      "{interjection} Excess amount? Beta, only excess I get is gas bill every month! {tangent}",
      "Credited to my account? Let me check... {delay}. No beta, same ₹{amount} only.",
    ],
    [
      "AnyDesk? Beta I only have this {phone} phone. It has snake game only. Very entertainment!",
      "{interjection} Download app? Beta, my phone storage is full with WhatsApp videos of {family}.",
      "App? Beta, my {family} told me never download apps from strangers. {tangent}",
    ],
    [
      "Bank manager? Beta Sharma ji? Tell him his {family} is asking about kitty party money! Very pending!",
      "{interjection} Manager on line? Put him on speaker, I want to complain about ATM queue also!",
      "Waiting? Beta, tell him I am also waiting. For my pension increase since 2019! {tangent}",
    ],
    [
      "Recording? Beta you should hear my {family}'s school speech recording. Very proud moment! {tangent}",
      "{interjection} Recording for police? Good! They should hear how you are troubling senior citizen!",
      "Recording? Beta, I also have recording of PM's speech. Very inspiring! {tangent}",
    ],
    [
      "Senior angry? Beta tell him to do yoga. My guru ji says anger is root of all problems. Om Shanti Om!",
      "{interjection} Last chance? Beta, you said same thing 5 minutes ago. How many last chances?",
      "Angry senior? Give phone to him, I will explain. {delay}. I have experience dealing with angry people.",
    ],
  ],
  'investment-scam': [
    [
      "Bitcoin? Beta is this that magic internet money? My {family} was telling something. {family_pronoun_cap} said Elon Musk also has?",
      "{interjection} Crypto? In my time, we only had FD and LIC. Very safe! {tangent}",
      "Investment? Beta, I invested in my children's education. Best investment! {tangent}",
    ],
    [
      "AI system? Beta I also have AC system. But it's making strange noise. Can your AI fix that also?",
      "{interjection} 5000 people earned crores? Beta, why they not on TV then? {tangent}",
      "Never fails? Beta, even Indian cricket team fails sometimes! {tangent}",
    ],
    [
      "Family future? Beta my {family} is already settled in {city}. {family_pronoun_cap} earns in {currency} only. Very proud!",
      "{interjection} Think about family? Beta, I think about them 24 hours! That's why I don't do risky things.",
      "Future? Beta, at my age, I think about past more! Good memories. {tangent}",
    ],
    [
      "Stay poor? Beta I am happy with my pension and morning walk group. We have very good golgappa parties!",
      "{interjection} Poor? Beta, I have house, family, health. What more I need? {tangent}",
      "Stupid mentality? Beta, saving money is not stupid. My father taught me this. {tangent}",
    ],
    [
      "5 minutes? Beta even Maggi takes 2 minutes. What is this hurry-burry? Relax, have some {food}!",
      "{interjection} Offer closing? Beta, in my experience, good offers don't need deadline. {tangent}",
      "Hurry? Beta, I am retired. I have plenty of time. No hurry at all! {delay}.",
    ],
  ],
};

// Helper functions
function randomItem<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function getRandomFamily() {
  return randomItem(FAMILY_MEMBERS);
}

function getRandomAmount() {
  const amounts = [500, 1000, 1500, 2000, 2500, 3000, 5000];
  return randomItem(amounts);
}

function getRandomPension() {
  const pensions = [15000, 18000, 22000, 25000, 28000];
  return randomItem(pensions);
}

function getRandomItem() {
  const items = ['vegetables', 'fruits', 'medicines', 'groceries', 'milk'];
  return randomItem(items);
}

function getRandomFood() {
  const foods = ['samosas', 'pakoras', 'chai-biskuit', 'ladoo', 'poha'];
  return randomItem(foods);
}

function getRandomPhone() {
  const phones = ['Nokia', 'Samsung', 'Jio', 'Redmi'];
  return randomItem(phones);
}

function getRandomShow() {
  const shows = ['Anupama', 'Taarak Mehta', 'CID', 'Kapil Sharma Show', 'KBC'];
  return randomItem(shows);
}

function getRandomCity() {
  const cities = ['Bangalore', 'Pune', 'Mumbai', 'Hyderabad', 'Chennai', 'USA', 'Canada'];
  return randomItem(cities);
}

function getRandomCurrency() {
  const currencies = ['dollars', 'rupees', 'good salary'];
  return randomItem(currencies);
}

function getRandomBank() {
  const banks = ['SBI', 'PNB', 'HDFC', 'ICICI', 'Bank of Baroda'];
  return randomItem(banks);
}

function getRandomCount() {
  const counts = ['two', 'three', 'four'];
  return randomItem(counts);
}

// Fill template with random values
function fillTemplate(template: string): string {
  const family = getRandomFamily();
  
  let result = template
    .replace(/{interjection}/g, randomItem(INTERJECTIONS))
    .replace(/{delay}/g, randomItem(DELAY_EXCUSES))
    .replace(/{tangent}/g, randomItem(TANGENTS))
    .replace(/{family}/g, family.relation)
    .replace(/{family_name}/g, family.name)
    .replace(/{family_name_upper}/g, family.name.toUpperCase())
    .replace(/{family_detail}/g, family.job || family.trait || '')
    .replace(/{family_pronoun}/g, family.relation === 'wife' || family.relation === 'daughter' ? 'she' : 'he')
    .replace(/{family_pronoun_cap}/g, family.relation === 'wife' || family.relation === 'daughter' ? 'She' : 'He')
    .replace(/{amount}/g, getRandomAmount().toString())
    .replace(/{small_amount}/g, '50')
    .replace(/{pension}/g, getRandomPension().toString())
    .replace(/{item}/g, getRandomItem())
    .replace(/{food}/g, getRandomFood())
    .replace(/{phone}/g, getRandomPhone())
    .replace(/{show}/g, getRandomShow())
    .replace(/{city}/g, getRandomCity())
    .replace(/{currency}/g, getRandomCurrency())
    .replace(/{bank}/g, getRandomBank())
    .replace(/{count}/g, getRandomCount());
  
  return result;
}

// Get scenario type from category
function getScenarioType(category: string): string {
  const mapping: Record<string, string> = {
    'Banking Fraud': 'kyc-update',
    'Advance Fee Fraud': 'lottery-win',
    'Impersonation Scam': 'police-threat',
    'Phishing': 'refund-scam',
    'Financial Fraud': 'investment-scam',
  };
  return mapping[category] || 'kyc-update';
}

// Main function to generate dynamic response
export function generateDynamicResponse(
  category: string,
  exchangeIndex: number,
  scammerMessage: string
): string {
  const scenarioType = getScenarioType(category);
  const templates = RESPONSE_TEMPLATES[scenarioType];
  
  if (!templates || !templates[exchangeIndex]) {
    return "Haan beta, theek hai... let me think about this...";
  }
  
  // Get a random template for this exchange
  const templateOptions = templates[exchangeIndex];
  const template = randomItem(templateOptions);
  
  // Fill in the template
  let response = fillTemplate(template);
  
  // 30% chance to add an extra interjection at the start
  if (Math.random() < 0.3 && !response.startsWith(randomItem(INTERJECTIONS).split(' ')[0])) {
    response = `${randomItem(INTERJECTIONS)} ${response}`;
  }
  
  // 20% chance to add a tangent at the end
  if (Math.random() < 0.2 && !response.includes('tangent')) {
    response = `${response} ${randomItem(TANGENTS)}`;
  }
  
  return response;
}

// Export for use in agent personas
export const RAMESH_UNCLE_PERSONA = {
  id: 'sentinel-agent',
  name: 'Sentinel',
  avatar: '🛡️',
  description: 'Autonomous Threat Neutralization Agent',
  generateResponse: generateDynamicResponse,
};
