import React, { useState } from "react";

const Social: React.FC = () => {
  const [platform, setPlatform] = useState("twitter");
  const [topic, setTopic] = useState("");
  const [postContent, setPostContent] = useState("");
  const [isPosting, setIsPosting] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [scheduledAt, setScheduledAt] = useState<string | null>(null);
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
        body: JSON.stringify({ text: postContent, platform: platform, scheduledAt: scheduledAt }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || `Failed to post to ${platform}.`);
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

  const handleGenerate = async () => {
    setIsGenerating(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await fetch("/api/social/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ topic }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || "Failed to generate content.");
      }

      const result = await response.json();
      setPostContent(result.content);
    } catch (err: any) {
      setError(err.message || "An unknown error occurred.");
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div style={{ padding: "20px", fontFamily: "Arial, sans-serif" }}>
      <h1>Social Media Management</h1>
      <p>Create and post to your social media accounts.</p>

      <div style={{ display: 'flex', gap: '20px' }}>
        <form
        onSubmit={handlePost}
        style={{ margin: "20px 0", display: "flex", flexDirection: "column", gap: "10px" }}
      >
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
            <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="Enter a topic to generate a post"
                style={{ flexGrow: 1, padding: "10px", fontSize: "1em", border: "1px solid #ccc", borderRadius: "4px" }}
                disabled={isGenerating}
            />
            <button
                type="button"
                onClick={handleGenerate}
                disabled={isGenerating}
                style={{
                    padding: "10px 15px",
                    cursor: "pointer",
                    border: "none",
                    backgroundColor: "blue",
                    color: "white",
                    borderRadius: "4px",
                }}
            >
                {isGenerating ? "Generating..." : "Generate"}
            </button>
        </div>
        <select value={platform} onChange={(e) => setPlatform(e.target.value)} style={{ padding: "10px", fontSize: "1em", border: "1px solid #ccc", borderRadius: "4px" }}>
            <option value="twitter">Twitter</option>
            <option value="linkedin">LinkedIn</option>
        </select>
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
        {platform === 'twitter' && (
            <div style={{ textAlign: 'right', fontSize: '0.9em', color: postContent.length > 280 ? 'red' : '#555' }}>
                {280 - postContent.length} characters remaining
            </div>
        )}
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <label htmlFor="schedule">Schedule for later:</label>
            <input
                type="datetime-local"
                id="schedule"
                name="schedule"
                onChange={(e) => setScheduledAt(e.target.value)}
                style={{ padding: '10px', fontSize: '1em', border: '1px solid #ccc', borderRadius: '4px' }}
            />
        </div>
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
          {isPosting ? "Posting..." : `Post to ${platform.charAt(0).toUpperCase() + platform.slice(1)}`}
        </button>
      </form>

      <div style={{ flex: 1, border: '1px solid #ccc', borderRadius: '8px', padding: '16px' }}>
        <h2>Preview</h2>
        <div style={{ whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>
            {postContent}
        </div>
      </div>
      </div>

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

      <div style={{ marginTop: '40px' }}>
        <h2>History</h2>
        {/* In a real app, this would be fetched from an API */}
        <div style={{ border: '1px solid #ccc', borderRadius: '8px', padding: '16px', marginBottom: '10px' }}>
            <p><strong>Status:</strong> Sent</p>
            <p><strong>Platform:</strong> Twitter</p>
            <p>This is a tweet that has already been posted.</p>
            <p><small>Posted on: 2025-08-16 17:00:00</small></p>
        </div>
        <div style={{ border: '1px solid #ccc', borderRadius: '8px', padding: '16px' }}>
            <p><strong>Status:</strong> Scheduled</p>
            <p><strong>Platform:</strong> LinkedIn</p>
            <p>This is a LinkedIn post that is scheduled for the future.</p>
            <p><small>Scheduled for: 2025-08-17 10:00:00</small></p>
        </div>
      </div>
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
