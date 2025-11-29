export interface XeroConfig {
    tenantId?: string;
    accessToken?: string;
    refreshToken?: string;
    environment: 'production' | 'sandbox';
}

export interface XeroInvoice {
    invoiceID: string;
    invoiceNumber: string;
    type: string;
    contact: {
        contactID: string;
        name: string;
        emailAddress: string;
        phones: Array<{
            phoneNumber: string;
            phoneType: string;
        }>;
    };
    date: string;
    dueDate: string;
    status: string;
    lineAmountTypes: {
        subtotal: number;
        total: number;
        totalTax: number;
    };
    currencyCode: string;
    total: number;
    amountDue: number;
    amountPaid: number;
    url: string;
    hasAttachments: boolean;
    isSent: boolean;
    isPaid: boolean;
    creditNotes: Array<{
        creditNoteID: string;
        creditNoteNumber: string;
        amount: number;
    }>;
    payments: Array<{
        paymentID: string;
        amount: number;
        date: string;
        status: string;
    }>;
    createdDateUTC: string;
    updatedDateUTC: string;
    reference?: string;
    lineItems: Array<{
        lineItemID: string;
        description: string;
        quantity: number;
        unitAmount: number;
        accountCode: string;
        taxType: string;
        taxAmount: number;
        lineAmount: number;
        tracking?: Array<{
            trackingCategoryID: string;
            trackingOptionID: string;
            name: string;
        }>;
    }>;
}

export interface XeroContact {
    contactID: string;
    contactNumber?: string;
    contactStatus: string;
    name: string;
    firstName?: string;
    lastName?: string;
    emailAddress?: string;
    skypeUserName?: string;
    bankAccountDetails?: {
        accountName: string;
        accountNumber: string;
        sortCode: string;
        bankName: string;
    };
    taxNumber?: string;
    accountsReceivableTaxType?: string;
    accountsPayableTaxType?: string;
    phones: Array<{
        phoneNumber: string;
        phoneType: string;
        phoneAreaCode?: string;
        phoneCountryCode?: string;
    }>;
    addresses: Array<{
        addressType: string;
        addressLine1: string;
        addressLine2?: string;
        addressLine3?: string;
        addressLine4?: string;
        city: string;
        region: string;
        postalCode: string;
        country: string;
        attentionTo?: string;
    }>;
    isCustomer: boolean;
    isSupplier: boolean;
    defaultCurrency: string;
    updatedDateUTC: string;
    contactGroups: Array<{
        contactGroupID: string;
        name: string;
        status: string;
    }>;
    website?: string;
    discount?: number;
    xeroNetworkKey?: string;
    salesTrackingCategories: Array<{
        trackingCategoryID: string;
        name: string;
        trackingOptionID: string;
        trackingOptionName: string;
        status: string;
    }>;
    purchasingTrackingCategories?: Array<{
        trackingCategoryID: string;
        name: string;
        trackingOptionID: string;
        trackingOptionName: string;
        status: string;
    }>;
    attachments?: Array<{
        id: string;
        fileName: string;
        url: string;
        mimeType: string;
        fileSize: number;
    }>;
}

export interface XeroBankAccount {
    bankAccountID: string;
    code: string;
    name: string;
    type: string;
    bankAccountNumber: string;
    status: string;
    bankName: string;
    bankBranch: string;
    currencyCode: string;
    bankAccountNumber?: string;
    sortCode?: string;
    accountNumber?: string;
    bsb?: string;
    routingNumber?: string;
    includeInBankFeeds: boolean;
    showInExpenseClaims: boolean;
    displayInBankRegister: boolean;
    enableBankFeeds: boolean;
    bankAccountType: string;
    bankAccountClass: string;
    bankAccountStatus: string;
    url: string;
    numberOfAttachments?: number;
    updatedDateUTC: string;
    lastReconciliationDate?: string;
}

export interface XeroTransaction {
    transactionID: string;
    type: string;
    contact?: {
        contactID: string;
        name: string;
    };
    lineItems: Array<{
        lineItemID: string;
        description: string;
        quantity: number;
        unitAmount: number;
        accountCode: string;
        taxType: string;
        taxAmount: number;
        lineAmount: number;
        tracking?: Array<{
            trackingCategoryID: string;
            trackingOptionID: string;
            name: string;
        }>;
    }>;
    date: string;
    status: string;
    lineAmountTypes: {
        subtotal: number;
        total: number;
        totalTax: number;
    };
    currencyCode: string;
    currencyRate: number;
    total: number;
    url: string;
    reference?: string;
    hasAttachments: boolean;
    createdDateUTC: string;
    updatedDateUTC: string;
    bankTransaction?: {
        bankTransactionID: string;
        amount: number;
        date: string;
        status: string;
        reference: string;
        details: string;
    };
    sourceTransactionID?: string;
    sourceSystem?: string;
    sourceTransactionType?: string;
    reconciliationStatus?: string;
}

export interface XeroFinancialReport {
    reportID: string;
    reportName: string;
    reportTitles: Array<{
        title: string;
    }>;
    reportDate: string;
    rows: Array<{
        rowType: string;
        title?: string;
        cells: Array<{
            value: string;
        }>;
    }>;
    columns: Array<{
        columnName: string;
    }>;
    summary: Array<{
        columnName: string;
        value: string;
    }>;
    updatedDateUTC: string;
}
