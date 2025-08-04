import { SkillResponse, XeroInvoice, XeroBill, XeroContact } from '../../atomic-docker/project/functions/atom-agent/types';
export declare function listXeroInvoices(userId: string): Promise<SkillResponse<{
    invoices: XeroInvoice[];
}>>;
export declare function listXeroBills(userId: string): Promise<SkillResponse<{
    bills: XeroBill[];
}>>;
export declare function listXeroContacts(userId: string): Promise<SkillResponse<{
    contacts: XeroContact[];
}>>;
export declare function createXeroInvoice(userId: string, contactId: string, lineItems: any[], // Simplified for example
type?: 'ACCREC' | 'ACCPAY'): Promise<SkillResponse<XeroInvoice>>;
export declare function createXeroBill(userId: string, contactId: string, lineItems: any[], // Simplified for example
type?: 'ACCREC' | 'ACCPAY'): Promise<SkillResponse<XeroBill>>;
export declare function createXeroContact(userId: string, name: string, email?: string): Promise<SkillResponse<XeroContact>>;
export declare function updateXeroContact(userId: string, contactId: string, fields: Partial<XeroContact>): Promise<SkillResponse<XeroContact>>;
export declare function getXeroContact(userId: string, contactId: string): Promise<SkillResponse<XeroContact>>;
