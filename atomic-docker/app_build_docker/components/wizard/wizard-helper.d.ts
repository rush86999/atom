export declare enum WizardState {
    DISABLED = "DISABLED",
    COMPLETED = "COMPLETED",
    ENABLED = "ENABLED"
}
export declare const getStepState: (index: number, completed: number, activeIndex: number) => WizardState;
