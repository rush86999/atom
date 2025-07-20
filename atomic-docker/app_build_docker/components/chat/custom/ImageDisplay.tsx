import React from 'react';

type Props = {
    imageUrl: string;
    altText?: string;
};

const ImageDisplay = ({ imageUrl, altText = 'Image' }: Props) => {
    return (
        <div className="my-2">
            <img
                src={imageUrl}
                alt={altText}
                className="rounded-lg max-w-full h-auto"
            />
        </div>
    );
};

export default ImageDisplay;
