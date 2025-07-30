import React, { useState } from "react";

const Referral = () => {
  const [referralCode, setReferralCode] = useState("");

  const generateReferralCode = async () => {
    // In a real application, you would make an API call to generate the referral code.
    // For now, we'll just generate a random string.
    const code = Math.random().toString(36).substring(2, 15);
    setReferralCode(code);
  };

  return (
    <div>
      <h1>Referral Program</h1>
      <p>Share your referral code with your friends to earn rewards!</p>
      <div>
        <input type="text" value={referralCode} readOnly />
        <button onClick={generateReferralCode}>Generate Code</button>
      </div>
    </div>
  );
};

export default Referral;
