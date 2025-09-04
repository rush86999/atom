import React from 'react';

interface BaseProps {
  title?: string;
  meta_title?: string;
  description?: string;
  image?: string;
  noindex?: boolean;
  canonical?: string;
  children: React.ReactNode;
}

const Base: React.FC<BaseProps> = ({
  title,
  meta_title,
  description,
  image,
  noindex,
  canonical,
  children
}) => {
  return (
    <>
      <head>
        <title>{title || 'Atom - Your Personal Assistant'}</title>
        <meta name="description" content={description || 'One assistant to manage your entire life'} />
        {meta_title && <meta property="og:title" content={meta_title} />}
        {description && <meta property="og:description" content={description} />}
        {image && <meta property="og:image" content={image} />}
        {noindex && <meta name="robots" content="noindex, nofollow" />}
        {canonical && <link rel="canonical" href={canonical} />}
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body>
        <div className="min-h-screen bg-gray-50">
          {children}
        </div>
      </body>
    </>
  );
};

export default Base;
