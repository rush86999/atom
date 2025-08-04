export enum WizardState {
  DISABLED = 'DISABLED',
  COMPLETED = 'COMPLETED',
  ENABLED = 'ENABLED',
}

export const getStepState = (
  index: number,
  completed: number,
  activeIndex: number
) => {
  let state = WizardState.DISABLED;
  if (typeof completed === 'number' && completed >= index) {
    state = WizardState.COMPLETED;
  } else if (
    activeIndex === index ||
    (typeof completed === 'number' && completed < index) ||
    completed === undefined
  ) {
    state = WizardState.ENABLED;
  }

  return state;
};
