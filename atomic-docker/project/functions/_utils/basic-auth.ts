export const basicAuth = (fn) => async (req, res) => {
  try {
    const authorizationToken = req.headers['authorization'];

    const encodedCreds = authorizationToken.split(' ')[1];
    const verifyToken = Buffer.from(encodedCreds, 'base64')
      .toString()
      .split(':')[1];

    if (verifyToken !== process.env.BASIC_AUTH) {
      return res.status(401).send('Unauthorized');
    }
  } catch (e) {
    console.log(e, ' unable to verify basic auth data ');
  }
};
