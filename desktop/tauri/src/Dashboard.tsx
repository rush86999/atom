import React, { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/tauri";

const Dashboard = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      const result = await invoke("dashboard");
      setData(result);
    };
    fetchData();
  }, []);

  if (!data) {
    return (
      <div>
        <h2>Dashboard</h2>
        <p>Loading...</p>
      </div>
    );
  }

  return (
    <div>
      <h2>Dashboard</h2>
      <div>
        <h3>Calendar</h3>
        {data.calendar.map((event) => (
          <p key={event.id}>
            {event.time} - {event.title}
          </p>
        ))}
      </div>
      <div>
        <h3>Tasks</h3>
        {data.tasks.map((task) => (
          <p key={task.id}>
            {task.title} - {task.due_date}
          </p>
        ))}
      </div>
      <div>
        <h3>Social</h3>
        {data.social.map((post) => (
          <p key={post.id}>
            {post.platform}: {post.post}
          </p>
        ))}
      </div>
    </div>
  );
};

export default Dashboard;
