/**
 * AlertDialog Component
 *
 * This is an alias for the Dialog component to maintain compatibility.
 * The shadcn/ui alert-dialog component is not installed, so we use Dialog instead.
 */

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

// Export Dialog components as AlertDialog
export const AlertDialog = Dialog;
export const AlertDialogContent = DialogContent;
export const AlertDialogDescription = DialogDescription;
export const AlertDialogFooter = DialogFooter;
export const AlertDialogHeader = DialogHeader;
export const AlertDialogTitle = DialogTitle;
export const AlertDialogTrigger = DialogTrigger;

// AlertDialogAction is just a Button
export const AlertDialogAction = Button;

// AlertDialogCancel is a Button with outline variant
export const AlertDialogCancel = Button;
