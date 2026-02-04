import React, { useState } from 'react';
import {
    Search,
    Plus,
    MoreVertical,
    Eye,
    Edit,
    Mail,
    FileText,
    Trash2,
    Phone
} from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { Checkbox } from "@/components/ui/checkbox";
import { XeroContact } from '../types';

interface XeroContactsProps {
    contacts: XeroContact[];
    onCreateContact: (contact: any) => Promise<void>;
    loading?: boolean;
}

export const XeroContacts: React.FC<XeroContactsProps> = ({
    contacts,
    onCreateContact,
    loading = false
}) => {
    const [searchQuery, setSearchQuery] = useState('');
    const [isModalOpen, setIsModalOpen] = useState(false);

    const [contactForm, setContactForm] = useState({
        name: '',
        firstName: '',
        lastName: '',
        emailAddress: '',
        isCustomer: true,
        isSupplier: false,
        defaultCurrency: 'USD',
        phones: [],
        addresses: [],
        taxNumber: ''
    });

    const filteredContacts = contacts.filter(contact =>
        !searchQuery ||
        contact.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        contact.emailAddress?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const handleSubmit = async () => {
        await onCreateContact(contactForm);
        setIsModalOpen(false);
        setContactForm({
            name: '',
            firstName: '',
            lastName: '',
            emailAddress: '',
            isCustomer: true,
            isSupplier: false,
            defaultCurrency: 'USD',
            phones: [],
            addresses: [],
            taxNumber: ''
        });
    };

    return (
        <div className="space-y-4">
            <div className="flex justify-between gap-4">
                <div className="relative flex-1">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search contacts..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-8"
                    />
                </div>
                <Button onClick={() => setIsModalOpen(true)}>
                    <Plus className="mr-2 h-4 w-4" />
                    Add Contact
                </Button>
            </div>

            <div className="rounded-md border">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead>Name</TableHead>
                            <TableHead>Email</TableHead>
                            <TableHead>Phone</TableHead>
                            <TableHead>Type</TableHead>
                            <TableHead>Currency</TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {filteredContacts.map((contact) => (
                            <TableRow key={contact.contactID}>
                                <TableCell>
                                    <div>
                                        <div className="font-medium">{contact.name}</div>
                                        {contact.contactNumber && (
                                            <div className="text-xs text-muted-foreground">#{contact.contactNumber}</div>
                                        )}
                                    </div>
                                </TableCell>
                                <TableCell>
                                    {contact.emailAddress && (
                                        <div className="flex items-center gap-2">
                                            <Mail className="h-4 w-4 text-muted-foreground" />
                                            <span>{contact.emailAddress}</span>
                                        </div>
                                    )}
                                </TableCell>
                                <TableCell>
                                    {contact.phones.length > 0 && (
                                        <div className="flex items-center gap-2">
                                            <Phone className="h-4 w-4 text-muted-foreground" />
                                            <span>{contact.phones[0].phoneNumber}</span>
                                        </div>
                                    )}
                                </TableCell>
                                <TableCell>
                                    <div className="flex gap-2">
                                        {contact.isCustomer && <Badge variant="secondary" className="bg-green-100 text-green-800 hover:bg-green-200">Customer</Badge>}
                                        {contact.isSupplier && <Badge variant="secondary" className="bg-blue-100 text-blue-800 hover:bg-blue-200">Supplier</Badge>}
                                    </div>
                                </TableCell>
                                <TableCell>
                                    <Badge variant="outline">{contact.defaultCurrency}</Badge>
                                </TableCell>
                                <TableCell>
                                    <Badge variant={contact.contactStatus === 'ACTIVE' ? 'default' : 'destructive'} className={contact.contactStatus === 'ACTIVE' ? 'bg-green-500 hover:bg-green-600' : ''}>
                                        {contact.contactStatus}
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
                                                Edit Contact
                                            </DropdownMenuItem>
                                            <DropdownMenuItem>
                                                <Mail className="mr-2 h-4 w-4" />
                                                Send Email
                                            </DropdownMenuItem>
                                            <DropdownMenuItem>
                                                <FileText className="mr-2 h-4 w-4" />
                                                Create Invoice
                                            </DropdownMenuItem>
                                            <DropdownMenuItem className="text-red-600">
                                                <Trash2 className="mr-2 h-4 w-4" />
                                                Delete Contact
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
                <DialogContent className="max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Add New Contact</DialogTitle>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>First Name</Label>
                                <Input
                                    value={contactForm.firstName}
                                    onChange={(e) => setContactForm({ ...contactForm, firstName: e.target.value })}
                                    placeholder="First name"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Last Name</Label>
                                <Input
                                    value={contactForm.lastName}
                                    onChange={(e) => setContactForm({ ...contactForm, lastName: e.target.value })}
                                    placeholder="Last name"
                                />
                            </div>
                        </div>
                        <div className="space-y-2">
                            <Label>Company Name</Label>
                            <Input
                                value={contactForm.name}
                                onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })}
                                placeholder="Company name (if applicable)"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Email</Label>
                            <Input
                                type="email"
                                value={contactForm.emailAddress}
                                onChange={(e) => setContactForm({ ...contactForm, emailAddress: e.target.value })}
                                placeholder="Email address"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Tax Number</Label>
                            <Input
                                value={contactForm.taxNumber}
                                onChange={(e) => setContactForm({ ...contactForm, taxNumber: e.target.value })}
                                placeholder="Tax number or VAT ID"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Contact Type</Label>
                            <div className="flex gap-4">
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="customer"
                                        checked={contactForm.isCustomer}
                                        onCheckedChange={(checked) => setContactForm({ ...contactForm, isCustomer: checked as boolean })}
                                    />
                                    <Label htmlFor="customer">Customer</Label>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <Checkbox
                                        id="supplier"
                                        checked={contactForm.isSupplier}
                                        onCheckedChange={(checked) => setContactForm({ ...contactForm, isSupplier: checked as boolean })}
                                    />
                                    <Label htmlFor="supplier">Supplier</Label>
                                </div>
                            </div>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsModalOpen(false)}>
                            Cancel
                        </Button>
                        <Button onClick={handleSubmit} disabled={loading}>
                            {loading ? 'Adding...' : 'Add Contact'}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};
