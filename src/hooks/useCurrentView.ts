import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useAppStore } from '../store';
import { View } from '../types';

const useCurrentView = () => {
  const { setCurrentView } = useAppStore();
  const location = useLocation();

  useEffect(() => {
    const path = location.pathname.substring(1);
    const view = (path || 'dashboard') as View;
    setCurrentView(view);
  }, [location, setCurrentView]);
};

export default useCurrentView;
