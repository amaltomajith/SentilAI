import jsPDF from 'jspdf';
import type { Message } from '@/components/ConversationLoop';
import type { ExtractedIntel } from '@/lib/scamAnalyzer';

interface ReportData {
  messages: Message[];
  extractedIntel: ExtractedIntel[];
  exchangeCount: number;
  scenarioType?: string;
  confidence: number;
  isThreat: boolean;
}

export function generateForensicReport(data: ReportData) {
  const doc = new jsPDF();
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 20;
  const contentWidth = pageWidth - margin * 2;
  let y = 20;

  // Dark mode color palette
  const colors = {
    pageBg: [17, 24, 39] as [number, number, number],         // #111827
    cardBg: [31, 41, 55] as [number, number, number],          // #1F2937
    borderGrey: [55, 65, 81] as [number, number, number],      // #374151
    white: [243, 244, 246] as [number, number, number],         // #F3F4F6
    textLight: [229, 231, 235] as [number, number, number],     // #E5E7EB
    textMuted: [156, 163, 175] as [number, number, number],     // #9CA3AF
    scammerRed: [248, 113, 113] as [number, number, number],    // #F87171
    sentinelCyan: [56, 189, 248] as [number, number, number],   // #38BDF8
    badgeRed: [220, 38, 38] as [number, number, number],        // DC2626
    green: [0, 255, 136] as [number, number, number],           // sentinel green
    scammerBg: [40, 20, 20] as [number, number, number],
    sentinelBg: [20, 30, 45] as [number, number, number],
  };

  // Fill entire page with dark background
  function fillPageBackground() {
    doc.setFillColor(...colors.pageBg);
    doc.rect(0, 0, pageWidth, pageHeight, 'F');
  }

  // Fill first page
  fillPageBackground();

  // Helper: ensure page space (adds page with dark bg)
  function ensureSpace(needed: number) {
    if (y + needed > pageHeight - 20) {
      doc.addPage();
      fillPageBackground();
      y = 20;
    }
  }

  // Helper: draw section header
  function drawSectionHeader(title: string) {
    ensureSpace(20);
    doc.setFillColor(...colors.cardBg);
    doc.roundedRect(margin, y, contentWidth, 12, 2, 2, 'F');
    doc.setFont('courier', 'bold');
    doc.setFontSize(11);
    doc.setTextColor(...colors.green);
    doc.text(title, margin + 5, y + 8);
    y += 18;
  }

  // Helper: draw key-value pair
  function drawKeyValue(key: string, value: string, valueColor?: [number, number, number]) {
    ensureSpace(10);
    doc.setFont('courier', 'normal');
    doc.setFontSize(9);
    doc.setTextColor(...colors.textMuted);
    doc.text(key, margin + 5, y);
    doc.setTextColor(...(valueColor || colors.white));
    doc.setFont('courier', 'bold');
    doc.text(value, margin + 60, y);
    y += 7;
  }

  // Helper: draw a thin separator line
  function drawSeparator() {
    doc.setDrawColor(...colors.borderGrey);
    doc.setLineWidth(0.3);
    doc.line(margin + 4, y, pageWidth - margin - 4, y);
    y += 4;
  }

  // ==========================================
  // A. HEADER
  // ==========================================
  // Header area (slightly darker)
  doc.setFillColor(10, 10, 18);
  doc.rect(0, 0, pageWidth, 55, 'F');

  // Title - white text
  doc.setFont('courier', 'bold');
  doc.setFontSize(18);
  doc.setTextColor(...colors.white);
  doc.text('SENTINEL AI', margin, 20);

  doc.setFont('courier', 'normal');
  doc.setFontSize(10);
  doc.setTextColor(...colors.textMuted);
  doc.text('Threat Neutralization Report', margin, 28);

  // Dynamic badge - CONFIRMED THREAT (red) or FALSE POSITIVE (green)
  const badgeText = data.isThreat ? 'CONFIRMED THREAT' : 'FALSE POSITIVE';
  const badgeBgColor: [number, number, number] = data.isThreat ? colors.badgeRed : [22, 163, 74]; // red or green-600
  doc.setFont('courier', 'bold');
  doc.setFontSize(9);
  const badgeTextWidth = doc.getTextWidth(badgeText);
  const badgePadding = 12;
  const badgeW = badgeTextWidth + badgePadding * 2;
  const badgeH = 14;
  const badgeX = pageWidth - margin - badgeW;
  const badgeY = 11;
  doc.setFillColor(...badgeBgColor);
  doc.roundedRect(badgeX, badgeY, badgeW, badgeH, 3, 3, 'F');
  doc.setTextColor(255, 255, 255);
  doc.text(badgeText, badgeX + badgePadding, badgeY + 10);

  // Date & Time
  const now = new Date();
  doc.setFont('courier', 'normal');
  doc.setFontSize(8);
  doc.setTextColor(...colors.textMuted);
  doc.text(`Generated: ${now.toLocaleDateString()} at ${now.toLocaleTimeString()}`, margin, 38);
  doc.text(`Report ID: SENTINEL-${Date.now().toString(36).toUpperCase()}`, margin, 45);

  // Divider
  doc.setDrawColor(...colors.green);
  doc.setLineWidth(0.5);
  doc.line(margin, 52, pageWidth - margin, 52);

  y = 62;

  // ==========================================
  // B. THREAT ANALYSIS
  // ==========================================
  drawSectionHeader('▶ THREAT ANALYSIS');

  const classification = data.scenarioType || 'Phishing';
  drawKeyValue('Classification:', classification.toUpperCase(), colors.scammerRed);
  drawKeyValue('Confidence Score:', `${data.confidence}%`, data.confidence >= 70 ? colors.scammerRed : colors.textMuted);
  drawKeyValue('Exchanges:', `${data.exchangeCount} rounds`);
  drawKeyValue('Messages Analyzed:', `${data.messages.length}`);

  if (data.extractedIntel.length > 0) {
    y += 4;
    doc.setFont('courier', 'bold');
    doc.setFontSize(9);
    doc.setTextColor(...colors.green);
    doc.text('Extracted Intelligence:', margin + 5, y);
    y += 7;

    data.extractedIntel.forEach((intel) => {
      ensureSpace(7);
      doc.setFont('courier', 'normal');
      doc.setFontSize(8);
      doc.setTextColor(...colors.textMuted);
      doc.text(`• [${intel.type}]`, margin + 8, y);
      doc.setTextColor(...colors.white);
      const truncated = intel.value.length > 50 ? intel.value.substring(0, 50) + '...' : intel.value;
      doc.text(truncated, margin + 45, y);
      doc.setTextColor(
        intel.risk === 'Critical' ? 248 : intel.risk === 'High' ? 251 : 156,
        intel.risk === 'Critical' ? 113 : intel.risk === 'High' ? 191 : 163,
        intel.risk === 'Critical' ? 113 : intel.risk === 'High' ? 36 : 175
      );
      doc.text(`[${intel.risk}]`, pageWidth - margin - 20, y);
      y += 6;
    });
  }

  y += 5;

  // ==========================================
  // C. IMPACT STATS
  // ==========================================
  drawSectionHeader('▶ IMPACT ASSESSMENT');

  // Stats box with darker bg
  ensureSpace(35);
  doc.setFillColor(...colors.cardBg);
  doc.roundedRect(margin, y, contentWidth, 28, 3, 3, 'F');
  doc.setDrawColor(...colors.borderGrey);
  doc.setLineWidth(0.3);
  doc.roundedRect(margin, y, contentWidth, 28, 3, 3, 'S');

  const statsY = y + 8;
  doc.setFont('courier', 'normal');
  doc.setFontSize(9);

  // Calculate actual duration from message timestamps
  const firstMsg = data.messages[0];
  const lastMsg = data.messages[data.messages.length - 1];
  const durationMs = firstMsg && lastMsg ? lastMsg.timestamp.getTime() - firstMsg.timestamp.getTime() : 0;
  const durationMin = Math.max(1, Math.round(durationMs / 60000));
  const durationText = durationMs > 0 ? `${durationMin} minute${durationMin !== 1 ? 's' : ''}` : 'N/A';

  doc.setTextColor(...colors.textMuted);
  doc.text('Session Duration:', margin + 8, statsY);
  doc.setTextColor(...colors.green);
  doc.setFont('courier', 'bold');
  doc.text(durationText, margin + 60, statsY);

  doc.setFont('courier', 'normal');
  doc.setTextColor(...colors.textMuted);
  doc.text('Threat Level:', margin + 8, statsY + 8);
  const threatLevel = data.confidence >= 80 ? 'HIGH' : data.confidence >= 50 ? 'MEDIUM' : 'LOW';
  const threatColor = data.isThreat ? (data.confidence >= 80 ? colors.scammerRed : [251, 191, 36] as [number, number, number]) : colors.green;
  doc.setTextColor(...threatColor);
  doc.setFont('courier', 'bold');
  doc.text(data.isThreat ? threatLevel : 'NONE', margin + 60, statsY + 8);

  doc.setFont('courier', 'normal');
  doc.setTextColor(...colors.textMuted);
  doc.text('Verdict:', margin + 8, statsY + 16);
  doc.setTextColor(...(data.isThreat ? colors.scammerRed : colors.green));
  doc.setFont('courier', 'bold');
  doc.text(data.isThreat ? 'SCAM DETECTED' : 'NO THREAT FOUND', margin + 60, statsY + 16);

  y += 35;

  // ==========================================
  // D. EVIDENCE LOG
  // ==========================================
  drawSectionHeader('▶ EVIDENCE LOG — FULL TRANSCRIPT');

  data.messages.forEach((msg, index) => {
    const isScammer = msg.sender === 'scammer';
    const label = isScammer ? 'SCAMMER' : 'SENTINEL';
    const labelColor = isScammer ? colors.scammerRed : colors.sentinelCyan;
    const timestamp = msg.timestamp.toLocaleTimeString();

    // Wrap message text
    doc.setFont('courier', 'normal');
    doc.setFontSize(8);
    const wrappedLines = doc.splitTextToSize(msg.text, contentWidth - 30);
    const blockHeight = 10 + wrappedLines.length * 4.5;

    ensureSpace(blockHeight + 6);

    // Message background
    const bgColor = isScammer ? colors.scammerBg : colors.sentinelBg;
    doc.setFillColor(...bgColor);
    doc.roundedRect(margin, y - 2, contentWidth, blockHeight, 2, 2, 'F');

    // Border
    doc.setDrawColor(...colors.borderGrey);
    doc.setLineWidth(0.2);
    doc.roundedRect(margin, y - 2, contentWidth, blockHeight, 2, 2, 'S');

    // Label + timestamp
    doc.setFont('courier', 'bold');
    doc.setFontSize(7);
    doc.setTextColor(...labelColor);
    doc.text(`[${String(index + 1).padStart(2, '0')}] ${label}`, margin + 4, y + 4);

    doc.setFont('courier', 'normal');
    doc.setTextColor(...colors.textMuted);
    doc.text(timestamp, pageWidth - margin - 30, y + 4);

    // Message text - white
    doc.setTextColor(255, 255, 255);
    doc.setFontSize(8);
    let textY = y + 10;
    wrappedLines.forEach((line: string) => {
      doc.text(line, margin + 6, textY);
      textY += 4.5;
    });

    y += blockHeight + 3;

    // Separator between messages
    if (index < data.messages.length - 1) {
      drawSeparator();
    }
  });

  y += 10;

  // ==========================================
  // E. FOOTER (centered, proper spacing)
  // ==========================================
  ensureSpace(45);

  doc.setDrawColor(...colors.green);
  doc.setLineWidth(0.3);
  doc.line(margin, y, pageWidth - margin, y);
  y += 10;

  const sigNumber = Math.floor(Math.random() * 900000 + 100000);
  doc.setFont('courier', 'bold');
  doc.setFontSize(8);
  doc.setTextColor(...colors.textMuted);
  const sigText = `Digital Signature: SENTINEL-SECURE-${sigNumber}`;
  const sigWidth = doc.getTextWidth(sigText);
  doc.text(sigText, (pageWidth - sigWidth) / 2, y);
  y += 10;

  doc.setFont('courier', 'normal');
  doc.setFontSize(7);
  doc.setTextColor(...colors.textMuted);
  const line1 = 'This report was generated by Sentinel AI — Autonomous Threat Neutralization System';
  doc.text(line1, (pageWidth - doc.getTextWidth(line1)) / 2, y);
  y += 10;

  const line2 = 'Classification: CONFIDENTIAL | For authorized personnel only';
  doc.text(line2, (pageWidth - doc.getTextWidth(line2)) / 2, y);
  y += 10;

  const line3 = `Timestamp: ${now.toISOString()}`;
  doc.text(line3, (pageWidth - doc.getTextWidth(line3)) / 2, y);

  // Save
  const filename = `sentinel-report-${now.toISOString().split('T')[0]}-${sigNumber}.pdf`;
  doc.save(filename);
}
