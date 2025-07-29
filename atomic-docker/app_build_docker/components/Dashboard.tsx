import React, { useState, useEffect } from "react";
import { Box, Heading, Text } from "@chakra-ui/react";

const Dashboard = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      const res = await fetch("/api/dashboard");
      const json = await res.json();
      setData(json);
    };
    fetchData();
  }, []);

  if (!data) {
    return (
      <Box>
        <Heading>Dashboard</Heading>
        <Text>Loading...</Text>
      </Box>
    );
  }

  return (
    <Box>
      <Heading>Dashboard</Heading>
      <Box mt={4}>
        <Heading size="md">Calendar</Heading>
        {data.calendar.map((event) => (
          <Text key={event.id}>
            {event.time} - {event.title}
          </Text>
        ))}
      </Box>
      <Box mt={4}>
        <Heading size="md">Tasks</Heading>
        {data.tasks.map((task) => (
          <Text key={task.id}>
            {task.title} - {task.due_date}
          </Text>
        ))}
      </Box>
      <Box mt={4}>
        <Heading size="md">Social</Heading>
        {data.social.map((post) => (
          <Text key={post.id}>
            {post.platform}: {post.post}
          </Text>
        ))}
      </Box>
    </Box>
  );
};

export default Dashboard;
