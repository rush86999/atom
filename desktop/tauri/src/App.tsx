import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Chat from './Chat';
import ProjectHealth from './ProjectHealth';

function App() {
  return (
    <Router>
      <div className="App">
        <Routes>
          <Route path="/" element={<Chat />} />
          <Route path="/project-health" element={<ProjectHealth />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
