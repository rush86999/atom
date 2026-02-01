import React, { useState } from 'react';
import {
    Search,
    Plus,
    MoreVertical,
    Eye,
    Edit,
    Download,
    Mail,
    Trash2,
    User
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { XeroInvoice, XeroContact } from '../types';

interface XeroInvoicesProps {
    invoices: XeroInvoice[];
    contacts: XeroContact[];
    onCreateInvoice: (invoice: any) => Promise<void>;
    loading?: boolean;
}

export const XeroInvoices: React.FC<XeroInvoicesProps> = ({
    invoices,
    contacts,
    onCreateInvoice,
    loading = false
}) => {
    const [searchQuery, setSearchQuery] = useState('');
    const [statusFilter, setStatusFilter] = useState('ALL');
    const [contactFilter, setContactFilter] = useState('ALL');
    const [isModalOpen, setIsModalOpen] = useState(false);

    const [invoiceForm, setInvoiceForm] = useState({
        type: 'ACCREC',
        contactID: '',
        date: new Date().toISOString().split('T')[0],
        dueDate: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        lineItems: [{
            description: '',
            quantity: 1,
            unitAmount: 0,
            accountCode: '200',
            taxType: 'OUTPUT'
        }],
        reference: '',
        currencyCode: 'USD'
    });

    const filteredInvoices = invoices.filter(invoice => {
        const matchesSearch = !searchQuery ||
            invoice.invoiceNumber.toLowerCase().includes(searchQuery.toLowerCase()) ||
            invoice.contact.name.toLowerCase().includes(searchQuery.toLowerCase());

        const matchesStatus = statusFilter === 'ALL' || invoice.status === statusFilter;
        const matchesContact = contactFilter === 'ALL' || invoice.contact.contactID === contactFilter;

        return matchesSearch && matchesStatus && matchesContact;
    });

    const getStatusBadgeVariant = (status: string) => {
        const variants: { [key: string]: string } = {
            DRAFT: 'secondary',
            SUBMITTED: 'secondary',
            AUTHORISED: 'default', // purple-ish usually, default is black/primary
            PAID: 'default', // green usually
            PARTIALLYPAID: 'outline',
            VOIDED: 'destructive',
            DELETED: 'destructive'
        };
        // We'll use custom classes for colors since Shadcn badges are limited
        return variants[status] || 'secondary';
    };

    const getStatusColorClass = (status: string) => {
        switch (status) {
            case 'PAID': return 'bg-green-500 hover:bg-green-600';
            case 'AUTHORISED': return 'bg-blue-500 hover:bg-blue-600';
            case 'VOIDED':
            case 'DELETED': return 'bg-red-500 hover:bg-red-600';
            case 'DRAFT': return 'bg-gray-500 hover:bg-gray-600';
            default: return '';
        }
    };

    const formatCurrency = (amount: number, currency: string = 'USD') => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: currency
        }).format(amount);
    };

    const formatDate = (dateString: string) => {
        return new Date(dateString).toLocaleDateString();
    };

    const handleSubmit = async () => {
        await onCreateInvoice(invoiceForm);
        setIsModalOpen(false);
        // Reset form
        setInvoiceForm({
            type: 'ACCREC',
            contactID: '',
            date: new Date().toISOString().split('T')[0],
            dueDate: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            lineItems: [{
                description: '',
                quantity: 1,
                unitAmount: 0,
                accountCode: '200',
                taxType: 'OUTPUT'
            }],
            reference: '',
            currencyCode: 'USD'
        });
    };

    return (
        <div className="space-y-4">
            <div className="flex flex-col sm:flex-row gap-4">
                <div className="relative flex-1">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search invoices..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-8"
                    />
                </div>
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-[180px]">
                        <SelectValue placeholder="Status" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="ALL">All Status</SelectItem>
                        <SelectItem value="DRAFT">Draft</SelectItem>
                        <SelectItem value="SUBMITTED">Submitted</SelectItem>
                        <SelectItem value="AUTHORISED">Authorised</SelectItem>
                        <SelectItem value="PAID">Paid</SelectItem>
                        <SelectItem value="PARTIALLYPAID">Partially Paid</SelectItem>
                        <SelectItem value="VOIDED">Voided</SelectItem>
                    </SelectContent>
                </Select>
                <Select value={contactFilter} onValueChange={setContactFilter}>
                    <SelectTrigger className="w-[200px]">
                        <SelectValue placeholder="Contact" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="ALL">All Contacts</SelectItem>
                        {contacts.map((contact) => (
                            <SelectItem key={contact.contactID} value={contact.contactID}>
                                {contact.name}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <Button onClick={() => setIsModalOpen(true)}>
                    <Plus className="mr-2 h-4 w-4" />
                    New Invoice
                </Button>
            </div>

            <div className="rounded-md border">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Invoice #</TableHead>
                            <TableHead>Customer</TableHead>
                            <TableHead>Date</TableHead>
                            <TableHead>Due Date</TableHead>
                            <TableHead>Amount</TableHead>
                            <TableHead>Paid</TableHead>
                            <TableHead>Due</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {filteredInvoices.map((invoice) => (
                            <TableRow key={invoice.invoiceID}>
                                <TableCell className="font-medium">{invoice.invoiceNumber}</TableCell>
                                <TableCell>
                                    <div className="flex items-center gap-2">
                                        <User className="h-4 w-4 text-muted-foreground" />
                                        <span>{invoice.contact.name}</span>
                                    </div>
                                </TableCell>
                                <TableCell>{formatDate(invoice.date)}</TableCell>
                                <TableCell>{formatDate(invoice.dueDate)}</TableCell>
                                <TableCell>{formatCurrency(invoice.total, invoice.currencyCode)}</TableCell>
                                <TableCell>{formatCurrency(invoice.amountPaid, invoice.currencyCode)}</TableCell>
                                <TableCell>{formatCurrency(invoice.amountDue, invoice.currencyCode)}</TableCell>
                                <TableCell>
                                    <Badge className={getStatusColorClass(invoice.status)}>
                                        {invoice.status}
                                    </Badge>
                                </TableCell>
                                <TableCell className="text-right">
                                    <DropdownMenu>
                                        <DropdownMenuTrigger asChild>
                                            <Button variant="ghost" className="h-8 w-8 p-0">
                                                <span className="sr-only">Open menu</span>
                                                <MoreVertical className="h-4 w-4" />
                                            </Button>
                                        </DropdownMenuTrigger>
                                        <DropdownMenuContent align="end">
                                            <DropdownMenuItem>
                                                <Eye className="mr-2 h-4 w-4" />
                                                View Details
                                            </DropdownMenuItem>
                                            <DropdownMenuItem>
                                                <Edit className="mr-2 h-4 w-4" />
                                                Edit Invoice
                                            </DropdownMenuItem>
                                            <DropdownMenuItem>
                                                <Download className="mr-2 h-4 w-4" />
                                                Download PDF
                                            </DropdownMenuItem>
                                            <DropdownMenuItem>
                                                <Mail className="mr-2 h-4 w-4" />
                                                Send Invoice
                                            </DropdownMenuItem>
                                            <DropdownMenuItem className="text-red-600">
                                                <Trash2 className="mr-2 h-4 w-4" />
                                                Delete Invoice
                                            </DropdownMenuItem>
                                        </DropdownMenuContent>
                                    </DropdownMenu>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </div>

            <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
                <DialogContent className="max-w-3xl">
                    <DialogHeader>
                        <DialogTitle>Create New Invoice</DialogTitle>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Invoice Type</Label>
                                <Select
                                    value={invoiceForm.type}
                                    onValueChange={(value) => setInvoiceForm({ ...invoiceForm, type: value })}
                                >
                                    <SelectTrigger>
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="ACCREC">Accounts Receivable (Invoice)</SelectItem>
                                        <SelectItem value="ACCPAY">Accounts Payable (Bill)</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <Label>Customer</Label>
                                <Select
                                    value={invoiceForm.contactID}
                                    onValueChange={(value) => setInvoiceForm({ ...invoiceForm, contactID: value })}
                                >
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select contact" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {contacts.filter(c => c.isCustomer).map((contact) => (
                                            <SelectItem key={contact.contactID} value={contact.contactID}>
                                                {contact.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Invoice Date</Label>
                                <Input
                                    type="date"
                                    value={invoiceForm.date}
                                    onChange={(e) => setInvoiceForm({ ...invoiceForm, date: e.target.value })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Due Date</Label>
                                <Input
                                    type="date"
                                    value={invoiceForm.dueDate}
                                    onChange={(e) => setInvoiceForm({ ...invoiceForm, dueDate: e.target.value })}
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label>Reference</Label>
                            <Input
                                value={invoiceForm.reference}
                                onChange={(e) => setInvoiceForm({ ...invoiceForm, reference: e.target.value })}
                                placeholder="Invoice reference or PO number"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label>Line Items</Label>
                            {invoiceForm.lineItems.map((item, index) => (
                                <div key={index} className="flex gap-2 items-end">
                                    <div className="flex-1">
                                        <Input
                                            placeholder="Description"
                                            value={item.description}
                                            onChange={(e) => {
                                                const newItems = [...invoiceForm.lineItems];
                                                newItems[index].description = e.target.value;
                                                setInvoiceForm({ ...invoiceForm, lineItems: newItems });
                                            }}
                                        />
                                    </div>
                                    <div className="w-24">
                                        <Input
                                            type="number"
                                            placeholder="Qty"
                                            value={item.quantity}
                                            onChange={(e) => {
                                                const newItems = [...invoiceForm.lineItems];
                                                newItems[index].quantity = Number(e.target.value);
                                                setInvoiceForm({ ...invoiceForm, lineItems: newItems });
                                            }}
                                        />
                                    </div>
                                    <div className="w-32">
                                        <Input
                                            type="number"
                                            placeholder="Amount"
                                            value={item.unitAmount}
                                            onChange={(e) => {
                                                const newItems = [...invoiceForm.lineItems];
                                                newItems[index].unitAmount = Number(e.target.value);
                                                setInvoiceForm({ ...invoiceForm, lineItems: newItems });
                                            }}
                                        />
                                    </div>
                                </div>
                            ))}
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setInvoiceForm({
                                    ...invoiceForm,
                                    lineItems: [...invoiceForm.lineItems, {
                                        description: '',
                                        quantity: 1,
                                        unitAmount: 0,
                                        accountCode: '200',
                                        taxType: 'OUTPUT'
                                    }]
                                })}
                                className="mt-2"
                            >
                                <Plus className="mr-2 h-4 w-4" />
                                Add Line Item
                            </Button>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsModalOpen(false)}>
                            Cancel
                        </Button>
                        <Button onClick={handleSubmit} disabled={loading}>
                            {loading ? 'Creating...' : 'Create Invoice'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};
