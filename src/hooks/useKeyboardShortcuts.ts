import { useEffect, startTransition } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../store';
import { View } from '../types';

interface UseKeyboardShortcutsProps {
  onVoiceCommand: () => void;
}

const useKeyboardShortcuts = ({ onVoiceCommand }: UseKeyboardShortcutsProps) => {
  const navigate = useNavigate();
  const { setCurrentView } = useAppStore();

  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
        event.preventDefault();
        onVoiceCommand();
      }

      if (event.altKey && event.key >= '1' && event.key <= '9') {
        event.preventDefault();
        const views: View[] = ['dashboard', 'tasks', 'agents', 'calendar', 'communications', 'settings'];
        const index = parseInt(event.key) - 1;
        if (views[index]) {
          startTransition(() => {
            setCurrentView(views[index]);
            navigate(`/${views[index]}`);
          });
        }
      }
    };

    document.addEventListener('keydown', handleKeyPress);
    return () => document.removeEventListener('keydown', handleKeyPress);
  }, [navigate, setCurrentView, onVoiceCommand]);
};

export default useKeyboardShortcuts;
