import { WizardState } from './wizard-helper';

export type WizardItemPropsType = {
  label: string;
  index: number;
};

export type WizardItemDisplayPropsType = {
  state: WizardState;
  label: string;
  index: number;
};

export type WizardPropsType = {
  items: WizardItemPropsType[];
  completed: number;
  activeIndex: number;
};
