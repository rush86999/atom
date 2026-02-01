import { SkillResponse } from '../types';
import { z } from 'zod';
import axios from 'axios';
import { EnrichedIntent } from '../nlu_agents/nlu_types';

// Define the structure of a tax query
export interface TaxQuery {
  intent:
    | 'calculate_tax'
    | 'find_deductions'
    | 'get_tax_advice'
    | 'lookup_tax_law';
  parameters: {
    income?: number;
    filingStatus?:
      | 'single'
      | 'married_jointly'
      | 'married_separately'
      | 'head_of_household';
    dependents?: number;
    query?: string;
  };
}

// Handle tax-related queries
export async function handleTaxQuery(
  userId: string,
  intent: EnrichedIntent,
  context?: any
): Promise<SkillResponse<string>> {
  try {
    switch (intent.primaryGoal) {
      case 'calculate_tax':
        return await getTaxCalculation(userId, intent.extractedParameters);
      case 'find_deductions':
        return await findTaxDeductions(userId, intent.extractedParameters);
      case 'get_tax_advice':
        return await getTaxAdvice(userId, intent.extractedParameters);
      case 'lookup_tax_law':
        return await lookupTaxLaw(userId, intent.extractedParameters);
      default:
        return await provideTaxHelp();
    }
  } catch (error) {
    console.error('Tax query error:', error);
    return {
      ok: false,
      error: {
        code: 'TAX_ERROR',
        message:
          'I encountered an issue processing your tax query. Please try rephrasing or contact support.',
      },
    };
  }
}

// --- Response Functions ---

async function getTaxCalculation(
  userId: string,
  params: any
): Promise<SkillResponse<string>> {
  // In a real application, this would call a tax calculation API
  const estimatedTaxes = (params.income || 50000) * 0.2;
  const responseText = `Based on the information provided, your estimated tax liability is $${estimatedTaxes.toLocaleString()}. This is just an estimate. For a more accurate calculation, please consult a tax professional.`;
  return { ok: true, data: responseText };
}

async function findTaxDeductions(
  userId: string,
  params: any
): Promise<SkillResponse<string>> {
  const deductions = [
    'Student loan interest',
    'Charitable contributions',
    'Medical expenses',
    'State and local taxes (SALT)',
    'Home office expenses',
  ];
  const responseText = `Here are some common tax deductions you may be eligible for:\n\n- ${deductions.join('\n- ')}\n\nPlease consult a tax professional to see if you qualify.`;
  return { ok: true, data: responseText };
}

async function getTaxAdvice(
  userId: string,
  params: any
): Promise<SkillResponse<string>> {
  const advice = `I am not a certified tax professional and cannot provide tax advice. However, I can provide general information about taxes. For personalized advice, please consult a qualified tax professional.`;
  return { ok: true, data: advice };
}

async function lookupTaxLaw(
  userId: string,
  params: any
): Promise<SkillResponse<string>> {
  const responseText = `I am sorry, but I am unable to look up specific tax laws at this time.`;
  return { ok: true, data: responseText };
}

async function provideTaxHelp(): Promise<SkillResponse<string>> {
  const helpText = `I can help you with basic tax-related questions. For example, you can ask me to:\n\n- Calculate your estimated tax liability\n- Find common tax deductions\n- Provide general tax information\n\nFor personalized advice, please consult a tax professional.`;
  return { ok: true, data: helpText };
}

// --- Utility Functions ---

function extractIncome(query: string): number | undefined {
  const match = query.match(/\$(\d+(?:,\d{3})*(?:\.\d{2})?)/);
  return match ? parseFloat(match[1].replace(/,/g, '')) : undefined;
}

function extractFilingStatus(
  query: string
):
  | 'single'
  | 'married_jointly'
  | 'married_separately'
  | 'head_of_household'
  | undefined {
  if (query.includes('single')) return 'single';
  if (query.includes('married filing jointly')) return 'married_jointly';
  if (query.includes('married filing separately')) return 'married_separately';
  if (query.includes('head of household')) return 'head_of_household';
  return undefined;
}

function extractDependents(query: string): number | undefined {
  const match = query.match(/(\d+)\s+dependents?/);
  return match ? parseInt(match[1]) : undefined;
}
