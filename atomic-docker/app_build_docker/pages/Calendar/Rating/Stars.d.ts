import { IStarProps } from '@pages/Calendar/Rating/Star';
interface IStarsProps extends IStarProps {
    maxStars: number;
    starSize: number;
}
declare const Stars: (props: IStarsProps) => JSX.Element;
export default Stars;
