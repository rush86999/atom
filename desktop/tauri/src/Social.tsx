import React from "react";

const Social = () => {
  return (
    <div>
      <h1>Social</h1>
      <p>This is the social page.</p>
      <select>
        <option value="twitter">Twitter</option>
        <option value="linkedin">LinkedIn</option>
      </select>
      <textarea placeholder="What's on your mind?"></textarea>
      <button>Post</button>
    </div>
  );
};

export default Social;
