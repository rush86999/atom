"""
ATOM QuickBooks Financial Integration Service
Advanced accounting and financial management integration with Stripe payments
"""

import os
import json
import logging
import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import httpx
import aiohttp
from collections import defaultdict, Counter
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field
import hashlib
import hmac
import base64
from urllib.parse import urlencode

# Import existing ATOM services
try:
    from atom_enterprise_security_service import atom_enterprise_security_service, SecurityLevel, ComplianceStandard
    from atom_workflow_automation_service import atom_workflow_automation_service, AutomationPriority, AutomationStatus
    from ai_enhanced_service import ai_enhanced_service, AIRequest, AIResponse, AITaskType, AIModelType, AIServiceType
    from atom_ai_integration import atom_ai_integration
    from atom_slack_integration import atom_slack_integration
    from atom_teams_integration import atom_teams_integration
    from atom_google_chat_integration import atom_google_chat_integration
    from atom_discord_integration import atom_discord_integration
    from atom_telegram_integration import atom_telegram_integration
    from atom_whatsapp_integration import atom_whatsapp_integration
    from atom_zoom_integration import atom_zoom_integration
except ImportError as e:
    logging.warning(f"Enterprise services not available: {e}")

# Configure logging
logger = logging.getLogger(__name__)

class TransactionType(Enum):
    """Transaction types"""
    INVOICE = "invoice"
    PAYMENT = "payment"
    EXPENSE = "expense"
    BILL = "bill"
    PURCHASE_ORDER = "purchase_order"
    CREDIT_NOTE = "credit_note"
    REFUND = "refund"
    TRANSFER = "transfer"
    JOURNAL_ENTRY = "journal_entry"

class AccountType(Enum):
    """Account types"""
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    REVENUE = "revenue"
    EXPENSE = "expense"
    BANK = "bank"
    CREDIT_CARD = "credit_card"
    ACCOUNTS_RECEIVABLE = "accounts_receivable"
    ACCOUNTS_PAYABLE = "accounts_payable"

class FinancialReportType(Enum):
    """Financial report types"""
    PROFIT_AND_LOSS = "profit_and_loss"
    BALANCE_SHEET = "balance_sheet"
    CASH_FLOW = "cash_flow"
    TRIAL_BALANCE = "trial_balance"
    AGED_RECEIVABLES = "aged_receivables"
    AGED_PAYABLES = "aged_payables"
    SALES_REPORT = "sales_report"
    EXPENSE_REPORT = "expense_report"
    TAX_REPORT = "tax_report"

class PaymentStatus(Enum):
    """Payment statuses"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    CANCELLED = "cancelled"

@dataclass
class Transaction:
    """Transaction data model"""
    transaction_id: str
    transaction_type: TransactionType
    account_id: str
    amount: float
    currency: str
    date: datetime
    description: str
    reference: str
    customer_id: Optional[str]
    vendor_id: Optional[str]
    category: str
    tags: List[str]
    attachments: List[Dict[str, Any]]
    status: PaymentStatus
    metadata: Dict[str, Any]

@dataclass
class Invoice:
    """Invoice data model"""
    invoice_id: str
    customer_id: str
    amount: float
    currency: str
    due_date: datetime
    issue_date: datetime
    status: PaymentStatus
    line_items: List[Dict[str, Any]]
    tax_amount: float
    discount_amount: float
    payment_terms: str
    notes: str
    attachments: List[Dict[str, Any]]
    metadata: Dict[str, Any]

@dataclass
class Expense:
    """Expense data model"""
    expense_id: str
    amount: float
    currency: str
    date: datetime
    vendor_id: str
    category: str
    description: str
    receipt_attachments: List[Dict[str, Any]]
    payment_method: str
    project_id: Optional[str]
    employee_id: Optional[str]
    tags: List[str]
    status: PaymentStatus
    metadata: Dict[str, Any]

@dataclass
class FinancialReport:
    """Financial report data model"""
    report_id: str
    report_type: FinancialReportType
    period: str
    start_date: datetime
    end_date: datetime
    data: Dict[str, Any]
    insights: List[str]
    recommendations: List[str]
    generated_at: datetime
    metadata: Dict[str, Any]

class AtomQuickBooksIntegrationService:
    """Advanced QuickBooks Financial Integration Service"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db = config.get('database')
        self.cache = config.get('cache')
        
        # QuickBooks API configuration
        self.quickbooks_config = {
            'client_id': config.get('quickbooks_client_id'),
            'client_secret': config.get('quickbooks_client_secret'),
            'redirect_uri': config.get('quickbooks_redirect_uri'),
            'environment': config.get('quickbooks_environment', 'sandbox'),
            'api_version': config.get('quickbooks_api_version', 'v3'),
            'base_url': 'https://sandbox-quickbooks.api.intuit.com/v3' if config.get('quickbooks_environment', 'sandbox') == 'sandbox' else 'https://quickbooks.api.intuit.com/v3',
            'company_id': config.get('quickbooks_company_id'),
            'access_token': config.get('quickbooks_access_token'),
            'refresh_token': config.get('quickbooks_refresh_token'),
            'enable_stripe_integration': config.get('enable_stripe_integration', True),
            'stripe_config': config.get('stripe_config', {}),
            'auto_categorization': config.get('auto_categorization', True),
            'fraud_detection': config.get('fraud_detection', True),
            'real_time_sync': config.get('real_time_sync', True),
            'expense_tracking': config.get('expense_tracking', True),
            'tax_calculation': config.get('tax_calculation', True),
            'financial_analytics': config.get('financial_analytics', True)
        }
        
        # API endpoints
        self.api_endpoints = {
            'company_info': '/companyinfo/{company_id}',
            'accounts': '/accounts',
            'customers': '/customers',
            'vendors': '/vendors',
            'invoices': '/invoice',
            'payments': '/payment',
            'expenses': '/expense',
            'bills': '/bill',
            'transactions': '/query',
            'reports': '/reports',
            'tax_rates': '/taxrate',
            'purchase_orders': '/purchaseorder',
            'credit_memos': '/creditmemo',
            'journal_entries': '/journalentry'
        }
        
        # Integration state
        self.is_initialized = False
        self.webhook_handlers: Dict[str, Callable] = {}
        self.payment_workflows: Dict[str, Dict[str, Any]] = {}
        self.expense_rules: Dict[str, Dict[str, Any]] = {}
        self.tax_rates: Dict[str, Dict[str, Any]] = {}
        
        # Stripe integration
        self.stripe_integration = None
        if self.quickbooks_config['enable_stripe_integration']:
            self.stripe_integration = self._initialize_stripe_integration()
        
        # Enterprise integration
        self.enterprise_security = config.get('security_service') or atom_enterprise_security_service
        self.enterprise_automation = config.get('automation_service') or atom_workflow_automation_service
        self.ai_service = config.get('ai_service') or ai_enhanced_service
        
        # Platform integrations
        self.platform_integrations = {
            'slack': atom_slack_integration,
            'teams': atom_teams_integration,
            'google_chat': atom_google_chat_integration,
            'discord': atom_discord_integration,
            'telegram': atom_telegram_integration,
            'whatsapp': atom_whatsapp_integration,
            'zoom': atom_zoom_integration
        }
        
        # Analytics and monitoring
        self.analytics_metrics = {
            'total_transactions': 0,
            'total_invoices': 0,
            'total_payments': 0,
            'total_expenses': 0,
            'revenue': 0.0,
            'expenses': 0.0,
            'profit': 0.0,
            'transaction_volume_today': 0,
            'payment_success_rate': 0.0,
            'average_invoice_amount': 0.0,
            'average_payment_time': 0.0,
            'expense_trends': defaultdict(list),
            'revenue_trends': defaultdict(list),
            'transaction_types': defaultdict(int),
            'payment_methods': defaultdict(int),
            'customer_revenue': defaultdict(float),
            'vendor_expenses': defaultdict(float)
        }
        
        # Performance metrics
        self.performance_metrics = {
            'api_response_time': 0.0,
            'stripe_processing_time': 0.0,
            'fraud_detection_time': 0.0,
            'categorization_time': 0.0,
            'report_generation_time': 0.0,
            'sync_time': 0.0,
            'webhook_processing_time': 0.0
        }
        
        logger.info("QuickBooks Integration Service initialized")
    
    async def initialize(self) -> bool:
        """Initialize QuickBooks Integration Service"""
        try:
            # Test QuickBooks API connection
            await self._test_quickbooks_connection()
            
            # Initialize Stripe integration
            if self.stripe_integration:
                await self._initialize_stripe_connection()
            
            # Setup webhooks
            await self._setup_webhooks()
            
            # Setup payment workflows
            await self._setup_payment_workflows()
            
            # Setup expense tracking
            if self.quickbooks_config['expense_tracking']:
                await self._setup_expense_tracking()
            
            # Setup tax calculation
            if self.quickbooks_config['tax_calculation']:
                await self._setup_tax_calculation()
            
            # Setup enterprise features
            await self._setup_enterprise_features()
            
            # Setup security and compliance
            await self._setup_security_and_compliance()
            
            # Load existing financial data
            await self._load_existing_financial_data()
            
            # Start real-time sync
            if self.quickbooks_config['real_time_sync']:
                await self._start_real_time_sync()
            
            self.is_initialized = True
            logger.info("QuickBooks Integration Service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing QuickBooks Integration Service: {e}")
            return False
    
    async def create_invoice(self, invoice_data: Dict[str, Any], platform: str = None) -> Dict[str, Any]:
        """Create new invoice in QuickBooks"""
        try:
            start_time = time.time()
            
            # Update analytics
            self.analytics_metrics['total_invoices'] += 1
            self.analytics_metrics['revenue'] += invoice_data.get('amount', 0.0)
            
            # Security and compliance check
            if self.quickbooks_config['enable_enterprise_features']:
                security_check = await self._perform_security_check(invoice_data)
                if not security_check['passed']:
                    return {'success': False, 'error': security_check['reason']}
            
            # AI analysis for invoice optimization
            if self.quickbooks_config['auto_categorization']:
                ai_analysis = await self._analyze_invoice_with_ai(invoice_data)
                invoice_data.update(ai_analysis)
            
            # Prepare invoice payload for QuickBooks
            invoice_payload = {
                'Invoice': {
                    'CustomerRef': {
                        'value': invoice_data.get('customer_id')
                    },
                    'TxnDate': invoice_data.get('issue_date', datetime.utcnow()).strftime('%Y-%m-%d'),
                    'DueDate': invoice_data.get('due_date', datetime.utcnow()).strftime('%Y-%m-%d'),
                    'Line': invoice_data.get('line_items', []),
                    'TxnTaxDetail': {
                        'TotalTax': invoice_data.get('tax_amount', 0)
                    },
                    'CustomerMemo': invoice_data.get('notes', ''),
                    'TotalAmt': invoice_data.get('amount', 0.0),
                    'ApplyTaxAfterDiscount': True,
                    'CustomField': invoice_data.get('custom_fields', [])
                }
            }
            
            # Create invoice via QuickBooks API
            headers = await self._get_auth_headers()
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.quickbooks_config['base_url']}{self.api_endpoints['invoices']}?minorversion=65",
                    headers=headers,
                    json=invoice_payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    invoice = response.json().get('Invoice', {})
                    
                    # Update performance metrics
                    creation_time = time.time() - start_time
                    self.performance_metrics['api_response_time'] = creation_time
                    
                    # Update analytics
                    self.analytics_metrics['average_invoice_amount'] = (
                        (self.analytics_metrics['average_invoice_amount'] * (self.analytics_metrics['total_invoices'] - 1) + 
                         invoice.get('TotalAmt', 0.0)) / self.analytics_metrics['total_invoices']
                    )
                    
                    # Store invoice locally
                    await self._cache_invoice(invoice)
                    
                    # Sync with Stripe if enabled
                    if self.stripe_integration:
                        await self._create_stripe_payment_intent(invoice)
                    
                    # Notify relevant platforms
                    if platform and platform in self.platform_integrations:
                        await self._notify_platform_invoice_created(invoice, platform)
                    
                    # Trigger workflows
                    await self._trigger_payment_workflows(invoice, 'created')
                    
                    logger.info(f"Invoice created successfully: {invoice.get('Id')}")
                    return {
                        'success': True,
                        'invoice': invoice,
                        'invoice_id': invoice.get('Id'),
                        'creation_time': creation_time
                    }
                else:
                    error_msg = f"Failed to create invoice: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    return {'success': False, 'error': error_msg}
                    
        except Exception as e:
            logger.error(f"Error creating invoice: {e}")
            return {'success': False, 'error': str(e)}
    
    async def create_payment(self, payment_data: Dict[str, Any], platform: str = None) -> Dict[str, Any]:
        """Create payment in QuickBooks"""
        try:
            start_time = time.time()
            
            # Update analytics
            self.analytics_metrics['total_payments'] += 1
            
            # Security and compliance check
            if self.quickbooks_config['enable_enterprise_features']:
                security_check = await self._perform_security_check(payment_data)
                if not security_check['passed']:
                    return {'success': False, 'error': security_check['reason']}
            
            # Fraud detection
            if self.quickbooks_config['fraud_detection']:
                fraud_check = await self._perform_fraud_detection(payment_data)
                if fraud_check['is_fraudulent']:
                    return {'success': False, 'error': f"Fraud detected: {fraud_check['reason']}"}
            
            # Prepare payment payload for QuickBooks
            payment_payload = {
                'Payment': {
                    'CustomerRef': {
                        'value': payment_data.get('customer_id')
                    },
                    'TxnDate': payment_data.get('date', datetime.utcnow()).strftime('%Y-%m-%d'),
                    'TotalAmt': payment_data.get('amount', 0.0),
                    'CurrencyRef': {
                        'value': payment_data.get('currency', 'USD')
                    },
                    'PaymentMethodRef': {
                        'value': payment_data.get('payment_method_id')
                    },
                    'Line': [{
                        'LinkedTxn': [{
                            'TxnId': payment_data.get('invoice_id'),
                            'TxnType': 'Invoice'
                        }],
                        'Amount': payment_data.get('amount', 0.0)
                    }],
                    'PrivateNote': payment_data.get('notes', '')
                }
            }
            
            # Process Stripe payment if applicable
            if self.stripe_integration and payment_data.get('stripe_payment_intent_id'):
                stripe_result = await self._process_stripe_payment(payment_data)
                if not stripe_result['success']:
                    return stripe_result
                payment_data['stripe_charge_id'] = stripe_result.get('charge_id')
            
            # Create payment via QuickBooks API
            headers = await self._get_auth_headers()
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.quickbooks_config['base_url']}{self.api_endpoints['payments']}?minorversion=65",
                    headers=headers,
                    json=payment_payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    payment = response.json().get('Payment', {})
                    
                    # Update performance metrics
                    processing_time = time.time() - start_time
                    self.performance_metrics['api_response_time'] = processing_time
                    
                    # Update analytics
                    self.analytics_metrics['payment_success_rate'] = (
                        (self.analytics_metrics['payment_success_rate'] * (self.analytics_metrics['total_payments'] - 1) + 100) / 
                        self.analytics_metrics['total_payments']
                    )
                    
                    # Store payment locally
                    await self._cache_payment(payment)
                    
                    # Notify relevant platforms
                    if platform and platform in self.platform_integrations:
                        await self._notify_platform_payment_created(payment, platform)
                    
                    # Trigger workflows
                    await self._trigger_payment_workflows(payment, 'completed')
                    
                    logger.info(f"Payment created successfully: {payment.get('Id')}")
                    return {
                        'success': True,
                        'payment': payment,
                        'payment_id': payment.get('Id'),
                        'processing_time': processing_time
                    }
                else:
                    error_msg = f"Failed to create payment: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    
                    # Update analytics for failed payment
                    self.analytics_metrics['payment_success_rate'] = (
                        (self.analytics_metrics['payment_success_rate'] * (self.analytics_metrics['total_payments'] - 1) + 0) / 
                        self.analytics_metrics['total_payments']
                    )
                    
                    return {'success': False, 'error': error_msg}
                    
        except Exception as e:
            logger.error(f"Error creating payment: {e}")
            return {'success': False, 'error': str(e)}
    
    async def create_expense(self, expense_data: Dict[str, Any], platform: str = None) -> Dict[str, Any]:
        """Create expense in QuickBooks"""
        try:
            start_time = time.time()
            
            # Update analytics
            self.analytics_metrics['total_expenses'] += 1
            self.analytics_metrics['expenses'] += expense_data.get('amount', 0.0)
            
            # Security and compliance check
            if self.quickbooks_config['enable_enterprise_features']:
                security_check = await self._perform_security_check(expense_data)
                if not security_check['passed']:
                    return {'success': False, 'error': security_check['reason']}
            
            # Auto-categorization
            if self.quickbooks_config['auto_categorization']:
                category_suggestion = await self._categorize_expense(expense_data)
                expense_data['category'] = category_suggestion
            
            # Prepare expense payload for QuickBooks
            expense_payload = {
                'Purchase': {  # Using Purchase for expenses
                    'AccountRef': {
                        'value': expense_data.get('account_id')
                    },
                    'TxnDate': expense_data.get('date', datetime.utcnow()).strftime('%Y-%m-%d'),
                    'TotalAmt': expense_data.get('amount', 0.0),
                    'CurrencyRef': {
                        'value': expense_data.get('currency', 'USD')
                    },
                    'PaymentMethodRef': {
                        'value': expense_data.get('payment_method_id')
                    },
                    'EntityRef': {
                        'value': expense_data.get('vendor_id'),
                        'type': 'Vendor'
                    },
                    'Line': [{
                        'Amount': expense_data.get('amount', 0.0),
                        'Description': expense_data.get('description', ''),
                        'AccountBasedExpenseLineDetail': {
                            'AccountRef': {
                                'value': expense_data.get('account_id')
                            },
                            'ClassRef': {
                                'value': expense_data.get('class_id')
                            } if expense_data.get('class_id') else None
                        }
                    }],
                    'PrivateNote': expense_data.get('notes', ''),
                    'ReceiptRef': {
                        'value': receipt['id']
                    } for receipt in expense_data.get('receipt_attachments', [])
                } if expense_data.get('receipt_attachments') else {},
                }
            }
            
            # Create expense via QuickBooks API
            headers = await self._get_auth_headers()
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.quickbooks_config['base_url']}{self.api_endpoints['expenses']}?minorversion=65",
                    headers=headers,
                    json=expense_payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    expense = response.json().get('Purchase', {})
                    
                    # Update performance metrics
                    creation_time = time.time() - start_time
                    self.performance_metrics['api_response_time'] = creation_time
                    
                    # Update expense trends
                    date_key = expense.get('TxnDate', '')[:7]  # YYYY-MM
                    self.analytics_metrics['expense_trends'][date_key].append(expense.get('TotalAmt', 0.0))
                    
                    # Store expense locally
                    await self._cache_expense(expense)
                    
                    # Notify relevant platforms
                    if platform and platform in self.platform_integrations:
                        await self._notify_platform_expense_created(expense, platform)
                    
                    # Trigger workflows
                    await self._trigger_payment_workflows(expense, 'expense_created')
                    
                    logger.info(f"Expense created successfully: {expense.get('Id')}")
                    return {
                        'success': True,
                        'expense': expense,
                        'expense_id': expense.get('Id'),
                        'creation_time': creation_time
                    }
                else:
                    error_msg = f"Failed to create expense: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    return {'success': False, 'error': error_msg}
                    
        except Exception as e:
            logger.error(f"Error creating expense: {e}")
            return {'success': False, 'error': str(e)}
    
    async def generate_financial_report(self, report_type: FinancialReportType, 
                                     start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Generate financial report"""
        try:
            start_time = time.time()
            
            # Prepare report query
            if report_type == FinancialReportType.PROFIT_AND_LOSS:
                report_data = await self._generate_profit_loss_report(start_date, end_date)
            elif report_type == FinancialReportType.BALANCE_SHEET:
                report_data = await self._generate_balance_sheet_report(start_date, end_date)
            elif report_type == FinancialReportType.CASH_FLOW:
                report_data = await self._generate_cash_flow_report(start_date, end_date)
            elif report_type == FinancialReportType.TRIAL_BALANCE:
                report_data = await self._generate_trial_balance_report(start_date, end_date)
            elif report_type == FinancialReportType.AGED_RECEIVABLES:
                report_data = await self._generate_aged_receivables_report(start_date, end_date)
            elif report_type == FinancialReportType.AGED_PAYABLES:
                report_data = await self._generate_aged_payables_report(start_date, end_date)
            elif report_type == FinancialReportType.SALES_REPORT:
                report_data = await self._generate_sales_report(start_date, end_date)
            elif report_type == FinancialReportType.EXPENSE_REPORT:
                report_data = await self._generate_expense_report(start_date, end_date)
            elif report_type == FinancialReportType.TAX_REPORT:
                report_data = await self._generate_tax_report(start_date, end_date)
            else:
                return {'success': False, 'error': 'Unsupported report type'}
            
            # Generate AI-powered insights and recommendations
            if self.quickbooks_config['financial_analytics']:
                ai_insights = await self._generate_financial_insights(report_data, report_type)
                report_data['insights'] = ai_insights['insights']
                report_data['recommendations'] = ai_insights['recommendations']
            
            # Create report object
            report = FinancialReport(
                report_id=f"report_{int(time.time())}",
                report_type=report_type,
                period=f"{start_date.date()} to {end_date.date()}",
                start_date=start_date,
                end_date=end_date,
                data=report_data,
                insights=report_data.get('insights', []),
                recommendations=report_data.get('recommendations', []),
                generated_at=datetime.utcnow(),
                metadata={'generated_by': 'atom_quickbooks_integration'}
            )
            
            # Update performance metrics
            generation_time = time.time() - start_time
            self.performance_metrics['report_generation_time'] = generation_time
            
            return {
                'success': True,
                'report': asdict(report),
                'generation_time': generation_time
            }
            
        except Exception as e:
            logger.error(f"Error generating financial report: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _analyze_invoice_with_ai(self, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze invoice with AI for optimization"""
        try:
            start_time = time.time()
            
            # Prepare AI request for invoice analysis
            ai_request = AIRequest(
                request_id=f"invoice_analysis_{int(time.time())}",
                task_type=AITaskType.CONTENT_ANALYSIS,
                model_type=AIModelType.GPT_4,
                service_type=AIServiceType.OPENAI,
                input_data={
                    'text': f"Invoice data: {json.dumps(invoice_data, default=str)}",
                    'context': 'invoice_optimization',
                    'analysis_type': 'pricing_and_terms'
                },
                context={
                    'platform': 'quickbooks',
                    'task': 'invoice_analysis'
                },
                platform='quickbooks'
            )
            
            ai_response = await self.ai_service.process_ai_request(ai_request)
            
            if ai_response.ok and ai_response.output_data:
                analysis_result = ai_response.output_data
                
                ai_suggestions = {
                    'suggested_pricing_adjustment': analysis_result.get('suggested_pricing_adjustment', 0.0),
                    'optimal_payment_terms': analysis_result.get('optimal_payment_terms', '30'),
                    'suggested_discount': analysis_result.get('suggested_discount', 0.0),
                    'customer_payment_risk': analysis_result.get('customer_payment_risk', 'low'),
                    'invoice_optimization_tips': analysis_result.get('optimization_tips', []),
                    'estimated_payment_time': analysis_result.get('estimated_payment_time', 30)
                }
            else:
                ai_suggestions = {
                    'suggested_pricing_adjustment': 0.0,
                    'optimal_payment_terms': '30',
                    'suggested_discount': 0.0,
                    'customer_payment_risk': 'low',
                    'invoice_optimization_tips': [],
                    'estimated_payment_time': 30
                }
            
            # Update performance metrics
            analysis_time = time.time() - start_time
            self.performance_metrics['categorization_time'] = analysis_time
            
            return ai_suggestions
            
        except Exception as e:
            logger.error(f"Error analyzing invoice with AI: {e}")
            return {
                'suggested_pricing_adjustment': 0.0,
                'optimal_payment_terms': '30',
                'suggested_discount': 0.0,
                'customer_payment_risk': 'low',
                'invoice_optimization_tips': [],
                'estimated_payment_time': 30
            }
    
    async def _categorize_expense(self, expense_data: Dict[str, Any]) -> str:
        """Auto-categorize expense using AI"""
        try:
            start_time = time.time()
            
            # Prepare AI request for expense categorization
            ai_request = AIRequest(
                request_id=f"expense_categorization_{int(time.time())}",
                task_type=AITaskType.CONTENT_ANALYSIS,
                model_type=AIModelType.GPT_4,
                service_type=AIServiceType.OPENAI,
                input_data={
                    'text': f"Expense data: {json.dumps(expense_data, default=str)}",
                    'context': 'expense_categorization',
                    'available_categories': [
                        'Office Supplies', 'Software', 'Hardware', 'Travel', 'Meals',
                        'Marketing', 'Rent', 'Utilities', 'Insurance', 'Legal',
                        'Professional Services', 'Training', 'Entertainment', 'Other'
                    ]
                },
                context={
                    'platform': 'quickbooks',
                    'task': 'expense_categorization'
                },
                platform='quickbooks'
            )
            
            ai_response = await self.ai_service.process_ai_request(ai_request)
            
            if ai_response.ok and ai_response.output_data:
                category = ai_response.output_data.get('suggested_category', 'Other')
            else:
                category = 'Other'
            
            # Update performance metrics
            categorization_time = time.time() - start_time
            self.performance_metrics['categorization_time'] = categorization_time
            
            return category
            
        except Exception as e:
            logger.error(f"Error categorizing expense: {e}")
            return 'Other'
    
    async def _initialize_stripe_integration(self):
        """Initialize Stripe integration"""
        try:
            from atom_stripe_integration import atom_stripe_integration
            self.stripe_integration = atom_stripe_integration
            logger.info("Stripe integration initialized")
            
        except ImportError:
            logger.warning("Stripe integration not available")
            self.stripe_integration = None
    
    async def _test_quickbooks_connection(self):
        """Test QuickBooks API connection"""
        try:
            headers = await self._get_auth_headers()
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.quickbooks_config['base_url']}{self.api_endpoints['company_info'].format(company_id=self.quickbooks_config['company_id'])}",
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    logger.info("QuickBooks API connection test successful")
                    return True
                else:
                    raise Exception(f"QuickBooks API test failed: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"QuickBooks connection test failed: {e}")
            raise
    
    async def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for QuickBooks API"""
        if self.quickbooks_config['access_token']:
            return {
                'Authorization': f"Bearer {self.quickbooks_config['access_token']}",
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        else:
            raise Exception("No access token available")
    
    async def _cache_invoice(self, invoice: Dict[str, Any]):
        """Cache invoice data locally"""
        try:
            if self.cache:
                cache_key = f"quickbooks_invoice:{invoice.get('Id')}"
                await self.cache.set(cache_key, invoice, ttl=3600)  # 1 hour
        except Exception as e:
            logger.error(f"Error caching invoice: {e}")
    
    async def _cache_payment(self, payment: Dict[str, Any]):
        """Cache payment data locally"""
        try:
            if self.cache:
                cache_key = f"quickbooks_payment:{payment.get('Id')}"
                await self.cache.set(cache_key, payment, ttl=3600)  # 1 hour
        except Exception as e:
            logger.error(f"Error caching payment: {e}")
    
    async def _cache_expense(self, expense: Dict[str, Any]):
        """Cache expense data locally"""
        try:
            if self.cache:
                cache_key = f"quickbooks_expense:{expense.get('Id')}"
                await self.cache.set(cache_key, expense, ttl=3600)  # 1 hour
        except Exception as e:
            logger.error(f"Error caching expense: {e}")
    
    async def _perform_fraud_detection(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform fraud detection on payment"""
        try:
            start_time = time.time()
            
            # Simple fraud detection rules
            risk_score = 0
            risk_factors = []
            
            # Check for unusual amount
            if payment_data.get('amount', 0) > 10000:
                risk_score += 30
                risk_factors.append('High amount')
            
            # Check for unusual time
            payment_time = payment_data.get('date', datetime.utcnow())
            if payment_time.hour < 6 or payment_time.hour > 22:
                risk_score += 20
                risk_factors.append('Unusual payment time')
            
            # Check for rapid payments from same customer
            if payment_data.get('rapid_sequence', False):
                risk_score += 40
                risk_factors.append('Rapid payment sequence')
            
            # Update performance metrics
            detection_time = time.time() - start_time
            self.performance_metrics['fraud_detection_time'] = detection_time
            
            # Determine if fraudulent
            is_fraudulent = risk_score > 50
            
            return {
                'is_fraudulent': is_fraudulent,
                'risk_score': risk_score,
                'risk_factors': risk_factors,
                'detection_time': detection_time
            }
            
        except Exception as e:
            logger.error(f"Error performing fraud detection: {e}")
            return {'is_fraudulent': False, 'risk_score': 0, 'risk_factors': []}
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get QuickBooks Integration service status"""
        try:
            return {
                'service': 'quickbooks_integration',
                'status': 'active' if self.is_initialized else 'inactive',
                'quickbooks_config': {
                    'environment': self.quickbooks_config['environment'],
                    'company_id': self.quickbooks_config['company_id'],
                    'stripe_integration': self.quickbooks_config['enable_stripe_integration'],
                    'auto_categorization': self.quickbooks_config['auto_categorization'],
                    'fraud_detection': self.quickbooks_config['fraud_detection'],
                    'real_time_sync': self.quickbooks_config['real_time_sync'],
                    'expense_tracking': self.quickbooks_config['expense_tracking'],
                    'tax_calculation': self.quickbooks_config['tax_calculation'],
                    'financial_analytics': self.quickbooks_config['financial_analytics']
                },
                'analytics_metrics': self.analytics_metrics,
                'performance_metrics': self.performance_metrics,
                'uptime': time.time() - (self._start_time if hasattr(self, '_start_time') else time.time())
            }
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {'error': str(e), 'service': 'quickbooks_integration'}
    
    async def close(self):
        """Close QuickBooks Integration Service"""
        try:
            logger.info("QuickBooks Integration Service closed")
            
        except Exception as e:
            logger.error(f"Error closing QuickBooks Integration Service: {e}")

# Global QuickBooks Integration service instance
atom_quickbooks_integration_service = AtomQuickBooksIntegrationService({
    'quickbooks_client_id': os.getenv('QUICKBOOKS_CLIENT_ID', 'your-client-id'),
    'quickbooks_client_secret': os.getenv('QUICKBOOKS_CLIENT_SECRET', 'your-client-secret'),
    'quickbooks_redirect_uri': os.getenv('QUICKBOOKS_REDIRECT_URI', 'https://your-domain.com/callback'),
    'quickbooks_environment': os.getenv('QUICKBOOKS_ENVIRONMENT', 'sandbox'),
    'quickbooks_company_id': os.getenv('QUICKBOOKS_COMPANY_ID', 'your-company-id'),
    'quickbooks_access_token': os.getenv('QUICKBOOKS_ACCESS_TOKEN', 'your-access-token'),
    'quickbooks_refresh_token': os.getenv('QUICKBOOKS_REFRESH_TOKEN', 'your-refresh-token'),
    'enable_stripe_integration': True,
    'stripe_config': {
        'secret_key': os.getenv('STRIPE_SECRET_KEY', 'sk_test_...'),
        'publishable_key': os.getenv('STRIPE_PUBLISHABLE_KEY', 'pk_test_...'),
        'webhook_secret': os.getenv('STRIPE_WEBHOOK_SECRET', 'whsec_...')
    },
    'auto_categorization': True,
    'fraud_detection': True,
    'real_time_sync': True,
    'expense_tracking': True,
    'tax_calculation': True,
    'financial_analytics': True,
    'database': None,  # Would be actual database connection
    'cache': None,  # Would be actual cache client
    'security_service': atom_enterprise_security_service,
    'automation_service': atom_workflow_automation_service,
    'ai_service': ai_enhanced_service
})