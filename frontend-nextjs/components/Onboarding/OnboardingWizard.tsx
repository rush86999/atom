
import React, { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { FaRobot, FaCheckCircle, FaRocket, FaPlug, FaKey } from "react-icons/fa";
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
    { title: "Connect", description: "AI Configuration" },
    { title: "Ready", description: "Let's go" },
];

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// P1.2 — providers offered in the inline API-key card. Must stay in sync with
// the valid_providers list on the backend store endpoint (byok_endpoints.py).
const API_KEY_PROVIDERS = [
    { id: "openai", label: "OpenAI", placeholder: "sk-..." },
    { id: "anthropic", label: "Anthropic", placeholder: "sk-ant-..." },
    { id: "deepseek", label: "DeepSeek", placeholder: "sk-..." },
    { id: "glm", label: "GLM (z.ai)", placeholder: "..." },
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

    // P1.2 — Card A (Ollama) state.
    const [ollamaReachable, setOllamaReachable] = useState<boolean | null>(null);
    const [ollamaInstallUrl, setOllamaInstallUrl] = useState<string>("https://ollama.com/download");
    const [ollamaConnecting, setOllamaConnecting] = useState(false);

    // P1.2 — Card B (API key) state.
    const [apiKeyProvider, setApiKeyProvider] = useState<string>("openai");
    const [apiKeyValue, setApiKeyValue] = useState<string>("");
    const [apiKeySaving, setApiKeySaving] = useState(false);

    const handleNext = async () => {
        if (activeStep === steps.length - 1) {
            await completeOnboarding();
            return;
        }
        // Single-step advance. The previous implementation called setActiveStep(1)
        // followed by setActiveStep(2) when activeStep===0, which skipped the
        // Profile step entirely and made step 2 (BYOK fork) unreachable from the UI.
        setActiveStep(activeStep + 1);
    };

    // P1.2 — probe Ollama when the user reaches step 2 so Card A renders the
    // right state (1-click enable vs install-ollama instructions).
    useEffect(() => {
        if (activeStep !== 2 || ollamaReachable !== null) return;
        let cancelled = false;
        (async () => {
            try {
                const token = localStorage.getItem("token");
                const res = await fetch(`${API_BASE}/api/onboarding/probe-ollama`, {
                    headers: token ? { "Authorization": `Bearer ${token}` } : {},
                });
                if (!res.ok) {
                    if (!cancelled) setOllamaReachable(false);
                    return;
                }
                const data = await res.json();
                const reachable = !!(data?.data?.reachable ?? data?.reachable);
                if (!cancelled) {
                    setOllamaReachable(reachable);
                    if (data?.data?.install_url) setOllamaInstallUrl(data.data.install_url);
                }
            } catch {
                if (!cancelled) setOllamaReachable(false);
            }
        })();
        return () => { cancelled = true; };
    }, [activeStep, ollamaReachable]);

    // P1.2 — Card A: store the Ollama provider via the existing keys endpoint.
    // Ollama doesn't need a real secret; we send a placeholder that the BYOK
    // store layer will hash/encrypt exactly like any other key.
    const handleEnableOllama = async () => {
        setOllamaConnecting(true);
        try {
            const token = localStorage.getItem("token");
            const res = await fetch(`${API_BASE}/api/ai/providers/ollama/keys`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...(token ? { "Authorization": `Bearer ${token}` } : {}),
                },
                body: JSON.stringify({
                    api_key: "ollama-local-no-key-required",
                    key_name: "Ollama (local)",
                    environment: "production",
                }),
            });
            if (!res.ok) {
                const detail = await res.json().catch(() => ({}));
                throw new Error(detail?.detail || `HTTP ${res.status}`);
            }
            toast({
                title: "Ollama connected",
                description: "Local Ollama is now your default AI provider.",
                variant: "success",
            });
            onUpdate({ onboarding_completed: false, provider_configured: "ollama" });
            // Advance to Ready step after a successful connect.
            setActiveStep(3);
        } catch (err: any) {
            toast({
                title: "Could not enable Ollama",
                description: err?.message || "Please try the API key path instead.",
                variant: "error",
            });
        } finally {
            setOllamaConnecting(false);
        }
    };

    // P1.2 — Card B: store the user-provided API key via the existing keys endpoint.
    const handleSaveApiKey = async () => {
        if (apiKeyValue.trim().length < 10) {
            toast({
                title: "Key too short",
                description: "API keys must be at least 10 characters.",
                variant: "error",
            });
            return;
        }
        setApiKeySaving(true);
        try {
            const token = localStorage.getItem("token");
            const res = await fetch(`${API_BASE}/api/ai/providers/${apiKeyProvider}/keys`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...(token ? { "Authorization": `Bearer ${token}` } : {}),
                },
                body: JSON.stringify({
                    api_key: apiKeyValue.trim(),
                    key_name: `${apiKeyProvider} (onboarding)`,
                    environment: "production",
                }),
            });
            if (!res.ok) {
                const detail = await res.json().catch(() => ({}));
                throw new Error(detail?.detail || `HTTP ${res.status}`);
            }
            toast({
                title: "API key saved",
                description: `${apiKeyProvider} is now configured. You can start chatting.`,
                variant: "success",
            });
            onUpdate({ onboarding_completed: false, provider_configured: apiKeyProvider });
            setApiKeyValue("");
            setActiveStep(3);
        } catch (err: any) {
            toast({
                title: "Failed to save key",
                description: err?.message || "Please verify the key and try again.",
                variant: "error",
            });
        } finally {
            setApiKeySaving(false);
        }
    };

    const completeOnboarding = async () => {
        try {
            const token = localStorage.getItem("token");
            const res = await fetch(`${API_BASE}/api/onboarding/update`, {
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
                                                "border-gray-200 dark:border-gray-700 text-gray-400"
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
                    <div className="absolute left-10 right-10 top-[88px] h-[2px] bg-gray-100 dark:bg-gray-800 -z-0 hidden sm:block" />
                </div>

                <div className="min-h-[200px] py-4">
                    {activeStep === 0 && (
                        <div className="flex flex-col items-center text-center space-y-4">
                            <FaRobot className="w-16 h-16 text-purple-600 animate-bounce" />
                            <h2 className="text-2xl font-bold">Hello, {user?.first_name || "there"}!</h2>
                            <p className="text-gray-600 dark:text-gray-400 max-w-sm">
                                Atom is here to help you automate your work with the power of AI Agents.
                            </p>
                        </div>
                    )}

                    {activeStep === 1 && (
                        <div className="space-y-4 px-4">
                            <div className="space-y-2">
                                <h3 className="text-lg font-semibold">Tell us about yourself</h3>
                                <p className="text-sm text-gray-500 dark:text-gray-400">This helps Atom personalize your experience.</p>
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
                        <div className="space-y-4 px-4">
                            <div className="space-y-1 text-center">
                                <h3 className="text-xl font-bold">Connect Your Intelligence</h3>
                                <p className="text-sm text-gray-500 dark:text-gray-400">
                                    Pick one to start chatting in under a minute. You can change this later in Settings → AI.
                                </p>
                            </div>

                            {/* Card A: Use local Ollama (free, 1-click) */}
                            <div className="rounded-lg border border-gray-200 dark:border-gray-800 p-4">
                                <div className="flex items-start justify-between gap-3">
                                    <div className="flex items-start gap-3 flex-1">
                                        <FaPlug className="w-5 h-5 text-purple-600 mt-0.5" />
                                        <div>
                                            <p className="font-semibold text-sm">Use local Ollama (free)</p>
                                            <p className="text-xs text-muted-foreground mt-1">
                                                No API key, no billing. Runs fully on your machine.
                                            </p>
                                        </div>
                                    </div>
                                    {ollamaReachable === true && (
                                        <span className="shrink-0 inline-flex items-center text-xs rounded-full bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300 px-2 py-0.5">
                                            <FaCheckCircle className="mr-1" /> Detected
                                        </span>
                                    )}
                                </div>
                                <div className="mt-3">
                                    {ollamaReachable === null && (
                                        <p className="text-xs text-muted-foreground">Checking for Ollama…</p>
                                    )}
                                    {ollamaReachable === true && (
                                        <Button
                                            type="button"
                                            size="sm"
                                            onClick={handleEnableOllama}
                                            disabled={ollamaConnecting}
                                        >
                                            {ollamaConnecting ? "Connecting…" : "Enable Ollama"}
                                        </Button>
                                    )}
                                    {ollamaReachable === false && (
                                        <div className="text-xs text-muted-foreground space-y-1">
                                            <p>Ollama not detected on this machine.</p>
                                            <a
                                                href={ollamaInstallUrl}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="inline-flex items-center text-purple-600 hover:underline"
                                            >
                                                Install Ollama →
                                            </a>
                                            <p className="text-[11px] text-gray-400">
                                                After installing, restart Ollama and refresh this dialog.
                                            </p>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Card B: Enter an API key */}
                            <div className="rounded-lg border border-gray-200 dark:border-gray-800 p-4">
                                <div className="flex items-start gap-3">
                                    <FaKey className="w-5 h-5 text-blue-600 mt-0.5" />
                                    <div className="flex-1">
                                        <p className="font-semibold text-sm">Enter an API key</p>
                                        <p className="text-xs text-muted-foreground mt-1">
                                            Bring your own key — encrypted at rest.
                                        </p>
                                    </div>
                                </div>
                                <div className="mt-3 grid grid-cols-1 sm:grid-cols-[140px_1fr] gap-2">
                                    <select
                                        className="h-9 rounded-md border border-gray-200 dark:border-gray-800 bg-transparent px-2 text-sm"
                                        value={apiKeyProvider}
                                        onChange={(e) => setApiKeyProvider(e.target.value)}
                                    >
                                        {API_KEY_PROVIDERS.map((p) => (
                                            <option key={p.id} value={p.id}>{p.label}</option>
                                        ))}
                                    </select>
                                    <Input
                                        type="password"
                                        placeholder={API_KEY_PROVIDERS.find(p => p.id === apiKeyProvider)?.placeholder || "API key"}
                                        value={apiKeyValue}
                                        onChange={(e) => setApiKeyValue(e.target.value)}
                                    />
                                </div>
                                <div className="mt-3 flex justify-end">
                                    <Button
                                        type="button"
                                        size="sm"
                                        onClick={handleSaveApiKey}
                                        disabled={apiKeySaving || apiKeyValue.trim().length < 10}
                                    >
                                        {apiKeySaving ? "Saving…" : "Save key & continue"}
                                    </Button>
                                </div>
                            </div>

                            <p className="text-xs text-gray-400 text-center">
                                Prefer to skip? You can configure a provider any time from Settings → AI.
                            </p>
                        </div>
                    )}

                    {activeStep === 3 && (
                        <div className="flex flex-col items-center text-center space-y-4">
                            <FaRocket className="w-16 h-16 text-green-500" />
                            <h2 className="text-2xl font-bold">You're Ready!</h2>
                            <p className="text-gray-600 dark:text-gray-400 max-w-sm">
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
