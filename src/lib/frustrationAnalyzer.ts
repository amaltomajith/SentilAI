// Heuristic Frustration Model - Analyzes scammer's emotional state

export interface FrustrationResult {
  score: number;
  factors: FrustrationFactor[];
  level: 'Low' | 'Medium' | 'High' | 'Critical';
}

export interface FrustrationFactor {
  type: string;
  impact: number;
  description: string;
}

// Aggressive keywords that increase frustration
const AGGRESSIVE_KEYWORDS = [
  'police', 'jail', 'arrest', 'block', 'stupid', 'fast', 'immediately',
  'urgent', 'warning', 'final', 'last', 'idiot', 'fool', 'now', 'hurry',
  'seized', 'freeze', 'legal', 'court', 'warrant'
];

// Polite keywords that decrease frustration
const POLITE_KEYWORDS = [
  'kindly', 'sir', 'please', 'dear', 'valued', 'respected', 'thank',
  'request', 'humble', 'appreciate'
];

export function calculateFrustration(text: string): FrustrationResult {
  const factors: FrustrationFactor[] = [];
  let score = 0;

  // Check for ALL CAPS ratio
  const upperCount = (text.match(/[A-Z]/g) || []).length;
  const letterCount = (text.match(/[a-zA-Z]/g) || []).length;
  const capsRatio = letterCount > 0 ? upperCount / letterCount : 0;
  
  if (capsRatio > 0.6) {
    score += 20;
    factors.push({
      type: 'ALL_CAPS',
      impact: 20,
      description: 'Message contains excessive CAPS LOCK'
    });
  } else if (capsRatio > 0.3) {
    score += 10;
    factors.push({
      type: 'PARTIAL_CAPS',
      impact: 10,
      description: 'Message contains significant uppercase text'
    });
  }

  // Check for "!!" or "?!" patterns
  const aggressivePunctuation = (text.match(/!{2,}|\?!/g) || []).length;
  if (aggressivePunctuation > 0) {
    const punctuationScore = Math.min(aggressivePunctuation * 15, 30);
    score += punctuationScore;
    factors.push({
      type: 'AGGRESSIVE_PUNCTUATION',
      impact: punctuationScore,
      description: `Found ${aggressivePunctuation} aggressive punctuation pattern(s)`
    });
  }

  // Check for excessive exclamation marks
  const exclamationCount = (text.match(/!/g) || []).length;
  if (exclamationCount >= 3) {
    const exclamationScore = Math.min(exclamationCount * 3, 15);
    score += exclamationScore;
    factors.push({
      type: 'EXCESSIVE_EXCLAMATION',
      impact: exclamationScore,
      description: `Found ${exclamationCount} exclamation marks`
    });
  }

  // Check for aggressive keywords
  const lowerText = text.toLowerCase();
  const foundAggressive: string[] = [];
  AGGRESSIVE_KEYWORDS.forEach(keyword => {
    if (lowerText.includes(keyword)) {
      foundAggressive.push(keyword);
    }
  });
  
  if (foundAggressive.length > 0) {
    const keywordScore = Math.min(foundAggressive.length * 10, 40);
    score += keywordScore;
    factors.push({
      type: 'AGGRESSIVE_KEYWORDS',
      impact: keywordScore,
      description: `Detected: ${foundAggressive.join(', ')}`
    });
  }

  // Check for polite keywords (reduce frustration)
  const foundPolite: string[] = [];
  POLITE_KEYWORDS.forEach(keyword => {
    if (lowerText.includes(keyword)) {
      foundPolite.push(keyword);
    }
  });
  
  if (foundPolite.length > 0) {
    const politeReduction = Math.min(foundPolite.length * 10, 20);
    score -= politeReduction;
    factors.push({
      type: 'POLITE_LANGUAGE',
      impact: -politeReduction,
      description: `Detected calming words: ${foundPolite.join(', ')}`
    });
  }

  // Check for repeated words (shows frustration)
  const words = text.toLowerCase().split(/\s+/);
  const wordCounts = new Map<string, number>();
  words.forEach(word => {
    if (word.length > 3) {
      wordCounts.set(word, (wordCounts.get(word) || 0) + 1);
    }
  });
  
  let repetitions = 0;
  wordCounts.forEach((count) => {
    if (count >= 3) repetitions++;
  });
  
  if (repetitions > 0) {
    const repeatScore = Math.min(repetitions * 8, 16);
    score += repeatScore;
    factors.push({
      type: 'WORD_REPETITION',
      impact: repeatScore,
      description: `Frustrated repetition detected`
    });
  }

  // Ensure score is between 0 and 100
  score = Math.max(0, Math.min(100, score));

  // Determine level
  let level: FrustrationResult['level'];
  if (score >= 75) {
    level = 'Critical';
  } else if (score >= 50) {
    level = 'High';
  } else if (score >= 25) {
    level = 'Medium';
  } else {
    level = 'Low';
  }

  return { score, factors, level };
}

// Get color based on frustration level
export function getFrustrationColor(level: FrustrationResult['level']): string {
  switch (level) {
    case 'Critical': return 'hsl(var(--destructive))';
    case 'High': return 'hsl(var(--warning))';
    case 'Medium': return 'hsl(var(--secondary))';
    case 'Low': return 'hsl(var(--primary))';
    default: return 'hsl(var(--muted))';
  }
}
