export const updateTask = async (task: Task): Promise<Task> => {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({ ...task, version: task.version + 1, _optimistic: false });
    }, 500);
  });
};