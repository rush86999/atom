interface Props {
    visible: boolean;
    onClose: () => void;
    onRatingChanged: (rating: number) => void;
    starSize: number;
    maxStars?: number;
    starRating?: number;
}
declare const RatingBottomModal: (props: Props) => JSX.Element | null;
export default RatingBottomModal;
