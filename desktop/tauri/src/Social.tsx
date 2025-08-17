import React, { useState } from "react";

const Social: React.FC = () => {
  const [postContent, setPostContent] = useState("");
  const [isPosting, setIsPosting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const handlePost = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsPosting(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await fetch("/api/social/post", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ text: postContent }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || "Failed to post to social media.");
      }

      const result = await response.json();
      setSuccess(result.message);
      setPostContent("");
    } catch (err: any) {
      setError(err.message || "An unknown error occurred.");
    } finally {
      setIsPosting(false);
    }
  };

  return (
    <div style={{ padding: "20px", fontFamily: "Arial, sans-serif" }}>
      <h1>Social Media Management</h1>
      <p>Create and post to your social media accounts.</p>

      <form
        onSubmit={handlePost}
        style={{ margin: "20px 0", display: "flex", flexDirection: "column", gap: "10px" }}
      >
        <textarea
          value={postContent}
          onChange={(e) => setPostContent(e.target.value)}
          placeholder="What's on your mind?"
          style={{
            width: "100%",
            minHeight: "100px",
            padding: "10px",
            fontSize: "1em",
            border: "1px solid #ccc",
            borderRadius: "4px",
          }}
          disabled={isPosting}
        />
        <button
          type="submit"
          disabled={isPosting}
          style={{
            padding: "10px 15px",
            cursor: "pointer",
            border: "none",
            backgroundColor: "purple",
            color: "white",
            borderRadius: "4px",
            alignSelf: "flex-start",
          }}
        >
          {isPosting ? "Posting..." : "Post to Twitter"}
        </button>
      </form>

      {error && (
        <div style={{ color: "red", marginBottom: "20px" }}>
          Error: {error}
        </div>
      )}

      {success && (
        <div style={{ color: "green", marginBottom: "20px" }}>
          {success}
        </div>
      )}
    </div>
  );
};

const SocialPage = () => {
  return (
    <div>
      <Social />
    </div>
  );
};

export default SocialPage;
