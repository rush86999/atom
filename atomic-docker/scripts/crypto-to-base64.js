import crypto from 'crypto';

const salt = crypto.randomBytes(16);
const base64 = Buffer.from(salt).toString('base64');
console.log(base64); // prints something like '2f8Xl0GqZ9L6yY1gQ9L4jw=='
