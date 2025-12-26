
import React, { useState } from "react";
import { useRouter } from "next/router";
import { FaRobot, FaCheckCircle, FaRocket } from "react-icons/fa";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "../ui/dialog";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { Label } from "../ui/label";
import { useToast } from "../ui/use-toast";
import { cn } from "../../lib/utils";

interface OnboardingWizardProps {
    isOpen: boolean;
    onClose: () => void;
    user: any;
    onUpdate: (data: any) => void;
}

const steps = [
    { title: "Welcome", description: "Start here" },
    { title: "Profile", description: "Set up details" },
    { title: "Ready", description: "Let's go" },
];

export const OnboardingWizard: React.FC<OnboardingWizardProps> = ({
    isOpen,
    onClose,
    user,
    onUpdate,
}) => {
    const router = useRouter();
    const { toast } = useToast();
    const [activeStep, setActiveStep] = useState(0);

    const [profileData, setProfileData] = useState({
        role: user?.specialty || "",
        goal: "",
    });

    const handleNext = async () => {
        if (activeStep === 0) {
            setActiveStep(1);
        } else if (activeStep === 1) {
            // Validation could go here
            if (!profileData.role) {
                toast({
                    title: "Role required",
                    description: "Please tell us your primary role.",
                    variant: "error",
                });
                return;
            }
            setActiveStep(2);
        } else {
            await completeOnboarding();
        }
    };

    const completeOnboarding = async () => {
        try {
            const token = localStorage.getItem("token");
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5059'}/api/onboarding/update`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": `Bearer ${token}`
                },
                body: JSON.stringify({
                    completed: true,
                    step: "completed",
                    // specific profile data could be sent to another endpoint or added to update DTO if backend supported it
                })
            });

            if (res.ok) {
                toast({
                    title: "You're all set!",
                    description: "Welcome to Atom. Let's build something amazing.",
                    variant: "success",
                });
                onUpdate({ onboarding_completed: true });
                onClose();
            }
        } catch (err) {
            console.error("Failed to update onboarding status", err);
            toast({
                title: "Error",
                description: "Something went wrong. Please try again.",
                variant: "error", // Use 'destructive' if 'error' variant doesn't exist in toast component, checking Toast.tsx showed default/success/error/warning
            });
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="sm:max-w-[600px]">
                <DialogHeader>
                    <DialogTitle>Welcome to Atom</DialogTitle>
                    <DialogDescription>
                        Your AI-powered automation workspace
                    </DialogDescription>
                </DialogHeader>

                {/* Stepper Visualization */}
                <div className="flex items-center justify-between mb-8 px-4 mt-4">
                    {steps.map((step, index) => {
                        const isActive = index === activeStep;
                        const isCompleted = index < activeStep;
                        return (
                            <div key={index} className="flex flex-col items-center relative z-10">
                                <div
                                    className={cn(
                                        "w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold border-2 transition-colors duration-200",
                                        isActive ? "border-purple-600 bg-purple-600 text-white" :
                                            isCompleted ? "border-green-500 bg-green-500 text-white" :
                                                "border-gray-200 text-gray-400"
                                    )}
                                >
                                    {isCompleted ? <FaCheckCircle /> : index + 1}
                                </div>
                                <span className={cn(
                                    "text-xs mt-2 font-medium",
                                    isActive ? "text-purple-600" :
                                        isCompleted ? "text-green-500" : "text-gray-400"
                                )}>
                                    {step.title}
                                </span>
                            </div>
                        );
                    })}
                    {/* Progress Bar Background (Simplified) */}
                    <div className="absolute left-10 right-10 top-[88px] h-[2px] bg-gray-100 -z-0 hidden sm:block" />
                </div>

                <div className="min-h-[200px] py-4">
                    {activeStep === 0 && (
                        <div className="flex flex-col items-center text-center space-y-4">
                            <FaRobot className="w-16 h-16 text-purple-600 animate-bounce" />
                            <h2 className="text-2xl font-bold">Hello, {user?.first_name || "there"}!</h2>
                            <p className="text-gray-600 max-w-sm">
                                Atom is here to help you automate your work with the power of AI Agents.
                            </p>
                        </div>
                    )}

                    {activeStep === 1 && (
                        <div className="space-y-4 px-4">
                            <div className="space-y-2">
                                <h3 className="text-lg font-semibold">Tell us about yourself</h3>
                                <p className="text-sm text-gray-500">This helps Atom personalize your experience.</p>
                            </div>

                            <div className="space-y-4">
                                <div className="space-y-2">
                                    <Label htmlFor="role">What is your primary role?</Label>
                                    <Input
                                        id="role"
                                        placeholder="e.g. Developer, Marketer, Founder"
                                        value={profileData.role}
                                        onChange={(e) => setProfileData({ ...profileData, role: e.target.value })}
                                    />
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="goal">What do you want to automate first?</Label>
                                    <Input
                                        id="goal"
                                        placeholder="e.g. Lead processing, Email replies"
                                        value={profileData.goal}
                                        onChange={(e) => setProfileData({ ...profileData, goal: e.target.value })}
                                    />
                                </div>
                            </div>
                        </div>
                    )}

                    {activeStep === 2 && (
                        <div className="flex flex-col items-center text-center space-y-4">
                            <FaRocket className="w-16 h-16 text-green-500" />
                            <h2 className="text-2xl font-bold">You're Ready!</h2>
                            <p className="text-gray-600 max-w-sm">
                                Your workspace is ready. You can start by exploring templates or chatting with Atom to build a workflow.
                            </p>
                        </div>
                    )}
                </div>

                <DialogFooter className="flex justify-between sm:justify-between w-full">
                    <Button
                        variant="ghost"
                        onClick={() => setActiveStep(Math.max(0, activeStep - 1))}
                        disabled={activeStep === 0}
                        className={activeStep === 0 ? "invisible" : ""}
                    >
                        Back
                    </Button>
                    <Button onClick={handleNext}>
                        {activeStep === steps.length - 1 ? "Start Automating" : "Next"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
