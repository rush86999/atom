import { Platform, StatusBar, Dimensions } from 'react-native';
import SIZES from '@lib/theme/sizes';

const StatusHeight = StatusBar.currentHeight;
const HeaderHeight = SIZES.BASE * 3.5 + (StatusHeight || 0);
const iPhoneX = () =>
  Platform.OS === 'ios' &&
  (Dimensions.get('window').height === 812 ||
    Dimensions.get('window').width === 812);

// eslint-disable-next-line import/no-anonymous-default-export
export default {
  StatusHeight,
  HeaderHeight,
  iPhoneX,
};
